#!/usr/bin/env python

# Unless explicitly stated otherwise all files in this repository are licensed under
# the BSD-3-Clause License. This product includes software developed at Datadog
# (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
DogStatsd is a Python client for DogStatsd, a Statsd fork for Datadog.
"""
# Standard libraries
from random import random
import logging
import os
import socket
import errno
import struct
import threading
import time
from threading import Lock, RLock
import weakref

try:
    import queue
except ImportError:
    # pypy has the same module, but capitalized.
    import Queue as queue  # type: ignore[no-redef]


# pylint: disable=unused-import
from typing import Optional, List, Text, Union
# pylint: enable=unused-import

# Datadog libraries
from datadog.dogstatsd.aggregator import Aggregator
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.context import (
    TimedContextManagerDecorator,
    DistributedContextManagerDecorator,
)
from datadog.dogstatsd.route import get_default_route
from datadog.dogstatsd.container import Cgroup
from datadog.util.compat import is_p3k, text
from datadog.util.format import normalize_tags, validate_cardinality
from datadog.version import __version__

# Logging
log = logging.getLogger("datadog.dogstatsd")

# Default config
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8125

# Socket prefixes
UNIX_ADDRESS_SCHEME = "unix://"
UNIX_ADDRESS_DATAGRAM_SCHEME = "unixgram://"
UNIX_ADDRESS_STREAM_SCHEME = "unixstream://"

# Buffering-related values (in seconds)
DEFAULT_BUFFERING_FLUSH_INTERVAL = 0.3
MIN_FLUSH_INTERVAL = 0.0001

# Env var to enable/disable sending the container ID field
ORIGIN_DETECTION_ENABLED = "DD_ORIGIN_DETECTION_ENABLED"

# Environment variable containing external data used for Origin Detection.
EXTERNAL_DATA_ENV_VAR = "DD_EXTERNAL_ENV"

# Default buffer settings based on socket type
UDP_OPTIMAL_PAYLOAD_LENGTH = 1432
UDS_OPTIMAL_PAYLOAD_LENGTH = 8192

# Socket options
MIN_SEND_BUFFER_SIZE = 32 * 1024

# Mapping of each "DD_" prefixed environment variable to a specific tag name
DD_ENV_TAGS_MAPPING = {
    "DD_ENTITY_ID": "dd.internal.entity_id",
    "DD_ENV": "env",
    "DD_SERVICE": "service",
    "DD_VERSION": "version",
}

# Telemetry minimum flush interval in seconds
DEFAULT_TELEMETRY_MIN_FLUSH_INTERVAL = 10

# Telemetry pre-computed formatting string. Pre-computation
# increases throughput of composing the result by 2-15% from basic
# '%'-based formatting with a `join`.
TELEMETRY_FORMATTING_STR = "\n".join(
    [
        "datadog.dogstatsd.client.metrics:%s|c|#%s",
        "datadog.dogstatsd.client.events:%s|c|#%s",
        "datadog.dogstatsd.client.service_checks:%s|c|#%s",
        "datadog.dogstatsd.client.bytes_sent:%s|c|#%s",
        "datadog.dogstatsd.client.bytes_dropped:%s|c|#%s",
        "datadog.dogstatsd.client.bytes_dropped_queue:%s|c|#%s",
        "datadog.dogstatsd.client.bytes_dropped_writer:%s|c|#%s",
        "datadog.dogstatsd.client.packets_sent:%s|c|#%s",
        "datadog.dogstatsd.client.packets_dropped:%s|c|#%s",
        "datadog.dogstatsd.client.packets_dropped_queue:%s|c|#%s",
        "datadog.dogstatsd.client.packets_dropped_writer:%s|c|#%s",
    ]
) + "\n"

Stop = object()

SUPPORTS_FORKING = hasattr(os, "register_at_fork") and not os.environ.get("DD_DOGSTATSD_DISABLE_FORK_SUPPORT", None)
TRACK_INSTANCES = not os.environ.get("DD_DOGSTATSD_DISABLE_INSTANCE_TRACKING", None)

_instances = weakref.WeakSet()  # type: weakref.WeakSet


def pre_fork():
    """Prepare all client instances for a process fork.

    If SUPPORTS_FORKING is true, this will be called automatically before os.fork().
    """
    for c in _instances:
        c.pre_fork()


def post_fork_parent():
    """Restore all client instances after a fork.

    If SUPPORTS_FORKING is true, this will be called automatically after os.fork().
    """
    for c in _instances:
        c.post_fork_parent()


def post_fork_child():
    for c in _instances:
        c.post_fork_child()


if SUPPORTS_FORKING:
    os.register_at_fork(  # type: ignore
        before=pre_fork,
        after_in_child=post_fork_child,
        after_in_parent=post_fork_parent,
    )


# pylint: disable=useless-object-inheritance,too-many-instance-attributes
# pylint: disable=too-many-arguments,too-many-locals
class DogStatsd(object):
    OK, WARNING, CRITICAL, UNKNOWN = (0, 1, 2, 3)

    # Cardinality
    CARDINALITY_NONE = "none"
    CARDINALITY_LOW = "low"
    CARDINALITY_ORCHESTRATOR = "orchestrator"
    CARDINALITY_HIGH = "high"

    def __init__(
        self,
        host=DEFAULT_HOST,                      # type: Text
        port=DEFAULT_PORT,                      # type: int
        max_buffer_size=None,                   # type: None
        flush_interval=DEFAULT_BUFFERING_FLUSH_INTERVAL,  # type: float
        disable_aggregation=True,               # type: bool
        disable_buffering=True,                 # type: bool
        namespace=None,                         # type: Optional[Text]
        constant_tags=None,                     # type: Optional[List[str]]
        use_ms=False,                           # type: bool
        use_default_route=False,                # type: bool
        socket_path=None,                       # type: Optional[Text]
        default_sample_rate=1,                  # type: float
        disable_telemetry=False,                # type: bool
        telemetry_min_flush_interval=(DEFAULT_TELEMETRY_MIN_FLUSH_INTERVAL),  # type: int
        telemetry_host=None,                    # type: Text
        telemetry_port=None,                    # type: Union[str, int]
        telemetry_socket_path=None,             # type: Text
        max_buffer_len=0,                       # type: int
        max_metric_samples_per_context=0,       # type: int
        container_id=None,                      # type: Optional[Text]
        origin_detection_enabled=True,          # type: bool
        cardinality=None,                       # type: Optional[Text]
        socket_timeout=0,                       # type: Optional[float]
        telemetry_socket_timeout=0,             # type: Optional[float]
        disable_background_sender=True,         # type: bool
        sender_queue_size=0,                    # type: int
        sender_queue_timeout=0,                 # type: Optional[float]
        track_instance=True,                    # type: bool
    ):  # type: (...) -> None
        """
        Initialize a DogStatsd object.

        >>> statsd = DogStatsd()

        :envvar DD_AGENT_HOST: the host of the DogStatsd server.
        If set, it overrides default value.
        :type DD_AGENT_HOST: string

        :envvar DD_DOGSTATSD_PORT: the port of the DogStatsd server.
        If set, it overrides default value.
        :type DD_DOGSTATSD_PORT: integer

        :envvar DATADOG_TAGS: Tags to attach to every metric reported by dogstatsd client.
        :type DATADOG_TAGS: comma-delimited string

        :envvar DD_ENTITY_ID: Tag to identify the client entity.
        :type DD_ENTITY_ID: string

        :envvar DD_ENV: the env of the service running the dogstatsd client.
        If set, it is appended to the constant (global) tags of the statsd client.
        :type DD_ENV: string

        :envvar DD_SERVICE: the name of the service running the dogstatsd client.
        If set, it is appended to the constant (global) tags of the statsd client.
        :type DD_SERVICE: string

        :envvar DD_VERSION: the version of the service running the dogstatsd client.
        If set, it is appended to the constant (global) tags of the statsd client.
        :type DD_VERSION: string

        :envvar DD_DOGSTATSD_DISABLE: Disable any statsd metric collection (default False)
        :type DD_DOGSTATSD_DISABLE: boolean

        :envvar DD_TELEMETRY_HOST: the host for the dogstatsd server we wish to submit
        telemetry stats to. If set, it overrides default value.
        :type DD_TELEMETRY_HOST: string

        :envvar DD_TELEMETRY_PORT: the port for the dogstatsd server we wish to submit
        telemetry stats to. If set, it overrides default value.
        :type DD_TELEMETRY_PORT: integer

        :envvar DD_ORIGIN_DETECTION_ENABLED: Enable/disable sending the container ID field
        for origin detection.
        :type DD_ORIGIN_DETECTION_ENABLED: boolean

        :envvar DD_DOGSTATSD_DISABLE_FORK_SUPPORT: Don't install global fork hooks with os.register_at_fork.
        Global fork hooks then need to be called manually before and after calling os.fork.
        :type DD_DOGSTATSD_DISABLE_FORK_SUPPORT: boolean

        :envvar DD_DOGSTATSD_DISABLE_INSTANCE_TRACKING: Don't register instances of this class with global fork hooks.
        :type DD_DOGSTATSD_DISABLE_INSTANCE_TRACKING: boolean

        :param host: the host of the DogStatsd server.
        :type host: string

        :param port: the port of the DogStatsd server.
        :type port: integer

        :max_buffer_size: Deprecated option, do not use it anymore.
        :type max_buffer_type: None

        :flush_interval: Amount of time in seconds that the flush thread will
        wait before trying to flush the buffered metrics to the server. If set,
        it overrides the default value.
        :type flush_interval: float

        :disable_aggregation: If true, metrics (Count, Gauge, Set) are no longer aggregated by the client
        :type disable_aggregation: bool

        :max_metric_samples_per_context: Sets the maximum amount of samples for Histogram, Distribution
        and Timings metrics (default 0). This feature should be used alongside aggregation. This feature
        is experimental.
        :type max_metric_samples_per_context: int

        :disable_buffering: If set, metrics are no longered buffered by the client and
        all data is sent synchronously to the server
        :type disable_buffering: bool

        :param namespace: Namespace to prefix all metric names
        :type namespace: string

        :param constant_tags: Tags to attach to all metrics
        :type constant_tags: list of strings

        :param use_ms: Report timed values in milliseconds instead of seconds (default False)
        :type use_ms: boolean

        :param use_default_route: Dynamically set the DogStatsd host to the default route
        (Useful when running the client in a container) (Linux only)
        :type use_default_route: boolean

        :param socket_path: Communicate with dogstatsd through a UNIX socket instead of
        UDP. If set, disables UDP transmission (Linux only)
        :type socket_path: string

        :param default_sample_rate: Sample rate to use by default for all metrics
        :type default_sample_rate: float

        :param max_buffer_len: Maximum number of bytes to buffer before sending to the server
        if sending metrics in batch. If not specified it will be adjusted to a optimal value
        depending on the connection type.
        :type max_buffer_len: integer

        :param disable_telemetry: Should client telemetry be disabled
        :type disable_telemetry: boolean

        :param telemetry_min_flush_interval: Minimum flush interval for telemetry in seconds
        :type telemetry_min_flush_interval: integer

        :param telemetry_host: the host for the dogstatsd server we wish to submit
        telemetry stats to. Optional. If telemetry is enabled and this is not specified
        the default host will be used.
        :type host: string

        :param telemetry_port: the port for the dogstatsd server we wish to submit
        telemetry stats to. Optional. If telemetry is enabled and this is not specified
        the default host will be used.
        :type port: integer

        :param telemetry_socket_path: Submit client telemetry to dogstatsd through a UNIX
        socket instead of UDP. If set, disables UDP transmission (Linux only)
        :type telemetry_socket_path: string

        :param container_id: Allows passing the container ID, this will be used by the Agent to enrich
        metrics with container tags.
        This feature requires Datadog Agent version >=6.35.0 && <7.0.0 or Agent versions >=7.35.0.
        When configured, the provided container ID is prioritized over the container ID discovered
        via Origin Detection.
        Default: None.
        :type container_id: string

        :param origin_detection_enabled: Enable/disable the client origin detection.
        This feature requires Datadog Agent version >=6.35.0 && <7.0.0 or Agent versions >=7.35.0.
        When enabled, the client tries to discover its container ID and sends it to the Agent
        to enrich the metrics with container tags.
        Origin detection can be disabled by configuring the environment variabe DD_ORIGIN_DETECTION_ENABLED=false
        The client tries to read the container ID by parsing the file /proc/self/cgroup.
        This is not supported on Windows.
        Default: True.
        More on this: https://docs.datadoghq.com/developers/dogstatsd/?tab=kubernetes#origin-detection-over-udp
        :type origin_detection_enabled: boolean

        :param cardinality: Set the cardinality of the client. Optional.
        This feature requires Datadog Agent version >=7.64.0.
        When configured, the provided cardinality is sent to the Agent to enrich the metrics with
        specific cardinality tags from Origin Detection.
        Default: None.
        More on this: https://docs.datadoghq.com/containers/kubernetes/tag/?tab=datadogoperator#out-of-the-box-tags
        :type cardinality: string

        :param socket_timeout: Set timeout for socket operations, in seconds. Optional.
        If sets to zero, never wait if operation can not be completed immediately. If set to None, wait forever.
        This option does not affect hostname resolution when using UDP.
        :type socket_timeout: float

        :param telemetry_socket_timeout: Set timeout for the telemetry socket operations. Optional.
        Effective only if either telemetry_host or telemetry_socket_path are set.
        If sets to zero, never wait if operation can not be completed immediately. If set to None, wait forever.
        This option does not affect hostname resolution when using UDP.
        :type telemetry_socket_timeout: float

        :param disable_background_sender: Use a background thread to communicate with the dogstatsd server. Optional.
        When enabled, a background thread will be used to send metric payloads to the Agent.
        Applications should call stop() before exiting to make sure all pending payloads are sent.
        Default: True.
        :type disable_background_sender: boolean

        :param sender_queue_size: Set the maximum number of packets to queue for the sender. Optional
        How may packets to queue before blocking or dropping the packet if the packet queue is already full.
        Default: 0 (unlimited).
        :type sender_queue_size: integer

        :param sender_queue_timeout: Set timeout for packet queue operations, in seconds. Optional.
        How long the application thread is willing to wait for the queue clear up before dropping the metric packet.
        If set to None, wait forever.
        If set to zero drop the packet immediately if the queue is full.
        Default: 0 (no wait)
        :type sender_queue_timeout: float

        :param track_instance: Keep track of this instance and automatically handle cleanup when os.fork() is called,
        if supported.
        Default: True.
        :type track_instance: boolean
        """

        self._socket_lock = Lock()

        # Check for deprecated option
        if max_buffer_size is not None:
            log.warning("The parameter max_buffer_size is now deprecated and is not used anymore")
        # Check host and port env vars
        agent_host = os.environ.get("DD_AGENT_HOST")
        if agent_host and host == DEFAULT_HOST:
            host = agent_host

        dogstatsd_port = os.environ.get("DD_DOGSTATSD_PORT")
        if dogstatsd_port and port == DEFAULT_PORT:
            try:
                port = int(dogstatsd_port)
            except ValueError:
                log.warning(
                    "Port number provided in DD_DOGSTATSD_PORT env var is not an integer: \
                %s, using %s as port number",
                    dogstatsd_port,
                    port,
                )

        # Assuming environment variables always override
        telemetry_host = os.environ.get("DD_TELEMETRY_HOST", telemetry_host)
        telemetry_port = os.environ.get("DD_TELEMETRY_PORT", telemetry_port) or port

        # Check enabled
        if os.environ.get("DD_DOGSTATSD_DISABLE") not in {"True", "true", "yes", "1"}:
            self._enabled = True
        else:
            self._enabled = False

        # Connection
        self._max_buffer_len = max_buffer_len
        self.socket_timeout = socket_timeout
        if socket_path is not None:
            self.socket_path = socket_path  # type: Optional[text]
            self.host = None
            self.port = None
        else:
            self.socket_path = None
            self.host = self.resolve_host(host, use_default_route)
            self.port = int(port)

        self.telemetry_socket_path = telemetry_socket_path
        self.telemetry_host = None
        self.telemetry_port = None
        self.telemetry_socket_timeout = telemetry_socket_timeout
        if not telemetry_socket_path and telemetry_host:
            self.telemetry_socket_path = None
            self.telemetry_host = self.resolve_host(telemetry_host, use_default_route)
            self.telemetry_port = int(telemetry_port)

        # Socket
        self.socket = None
        self.telemetry_socket = None
        self.encoding = "utf-8"

        # Options
        env_tags = [tag for tag in os.environ.get("DATADOG_TAGS", "").split(",") if tag]
        # Inject values of DD_* environment variables as global tags.
        for var, tag_name in DD_ENV_TAGS_MAPPING.items():
            value = os.environ.get(var, "")
            if value:
                env_tags.append("{name}:{value}".format(name=tag_name, value=value))
        if constant_tags is None:
            constant_tags = []
        self.constant_tags = constant_tags + env_tags
        if namespace is not None:
            namespace = text(namespace)
        self.namespace = namespace
        self.use_ms = use_ms  # type: bool
        self.default_sample_rate = default_sample_rate
        self.cardinality = cardinality

        # Origin detection
        self._container_id = None
        origin_detection_enabled = self._is_origin_detection_enabled(
            container_id, origin_detection_enabled
        )
        self._set_container_id(container_id, origin_detection_enabled)
        self._external_data = os.environ.get(EXTERNAL_DATA_ENV_VAR, None)

        # init telemetry version
        self._client_tags = [
            "client:py",
            "client_version:{}".format(__version__),
        ]
        self._reset_telemetry()
        self._telemetry_flush_interval = telemetry_min_flush_interval
        self._telemetry = not disable_telemetry
        self._last_flush_time = time.time()

        self._current_buffer_total_size = 0
        self._buffer = []  # type: List[Text]
        self._buffer_lock = RLock()

        self._reset_buffer()

        # This lock is used for all cases where client configuration is being changed: buffering,
        # aggregation, sender mode.
        self._config_lock = RLock()

        self._disable_buffering = disable_buffering
        self._disable_aggregation = disable_aggregation

        self._flush_interval = flush_interval
        self._flush_thread = None
        self._flush_thread_stop = threading.Event()
        self.aggregator = Aggregator(max_metric_samples_per_context, self.cardinality)
        # Indicates if the process is about to fork, so we shouldn't start any new threads yet.
        self._forking = False

        if not self._disable_buffering:
            self._send = self._send_to_buffer
        else:
            self._send = self._send_to_server

        if not self._disable_aggregation or not self._disable_buffering:
            self._start_flush_thread()
        else:
            log.debug("Statsd buffering and aggregation is disabled")

        self._queue = None
        self._sender_thread = None
        self._sender_enabled = False

        if not disable_background_sender:
            self.enable_background_sender(sender_queue_size, sender_queue_timeout)

        if TRACK_INSTANCES and track_instance:
            _instances.add(self)

    @property
    def socket_path(self):
        return self._socket_path

    @socket_path.setter
    def socket_path(self, path):
        with self._socket_lock:
            self._socket_path = path

    @property
    def socket(self):
        return self._socket

    @socket.setter
    def socket(self, new_socket):
        self._socket = new_socket
        if new_socket:
            try:
                self._socket_kind = new_socket.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
                if new_socket.family == socket.AF_UNIX:
                    if self._socket_kind == socket.SOCK_STREAM:
                        self._transport = "uds-stream"
                    else:
                        self._transport = "uds"
                    self._max_payload_size = self._max_buffer_len or UDS_OPTIMAL_PAYLOAD_LENGTH
                else:
                    self._transport = "udp"
                    self._max_payload_size = self._max_buffer_len or UDP_OPTIMAL_PAYLOAD_LENGTH
                return
            except AttributeError:  # _socket can't have a type if it doesn't have sockopts
                log.info("Unexpected socket provided with no support for getsockopt")
        self._socket_kind = None
        self._transport = "udp"
        # When the socket is None, we use the UDP optimal payload length
        self._max_payload_size = UDP_OPTIMAL_PAYLOAD_LENGTH

    @property
    def telemetry_socket(self):
        return self._telemetry_socket

    @telemetry_socket.setter
    def telemetry_socket(self, t_socket):
        self._telemetry_socket = t_socket
        if t_socket:
            try:
                self._telemetry_socket_kind = t_socket.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
                return
            except AttributeError:  # _telemetry_socket can't have a kind if it doesn't have sockopts
                log.info("Unexpected telemetry socket provided with no support for getsockopt")
        self._telemetry_socket_kind = None

    def enable_background_sender(self, sender_queue_size=0, sender_queue_timeout=0):
        """
        Use a background thread to communicate with the dogstatsd server.
        When enabled, a background thread will be used to send metric payloads to the Agent.

        Applications should call stop() before exiting to make sure all pending payloads are sent.

        Compatible with os.fork() starting with Python 3.7. On earlier versions, compatible if applications
        arrange to call pre_fork(), post_fork_parent() and post_fork_child() module functions around calls
        to os.fork().

        :param sender_queue_size: Set the maximum number of packets to queue for the sender.
            How many packets to queue before blocking or dropping the packet if the packet queue is already full.
            Default: 0 (unlimited).
        :type sender_queue_size: integer, optional
        :param sender_queue_timeout: Set timeout for packet queue operations, in seconds.
            How long the application thread is willing to wait for the queue clear up before dropping the metric packet.
            If set to None, wait forever. If set to zero drop the packet immediately if the queue is full.
            Default: 0 (no wait).
        :type sender_queue_timeout: float, optional
        """

        with self._config_lock:
            self._sender_enabled = True
            self._sender_queue_size = sender_queue_size
            if sender_queue_timeout is None:
                self._queue_blocking = True
                self._queue_timeout = None
            else:
                self._queue_blocking = sender_queue_timeout > 0
                self._queue_timeout = max(0, sender_queue_timeout)

            self._start_sender_thread()

    def disable_background_sender(self):
        """Disable background sender mode.

        This call will block until all previously queued payloads are sent.
        """
        with self._config_lock:
            self._sender_enabled = False
            self._stop_sender_thread()

    def disable_telemetry(self):
        self._telemetry = False

    def enable_telemetry(self):
        self._telemetry = True

    # Note: Invocations of this method should be thread-safe
    def _start_flush_thread(self):
        if self._disable_aggregation and self.disable_buffering:
            log.debug("Statsd periodic buffer and aggregation flush is disabled")
            return

        if self._flush_interval <= MIN_FLUSH_INTERVAL:
            log.debug(
                "the set flush interval is less then the minimum"
            )
            return

        if self._forking:
            return

        if self._flush_thread is not None:
            return

        def _flush_thread_loop(self, flush_interval):
            while not self._flush_thread_stop.is_set():
                time.sleep(flush_interval)
                if not self._disable_aggregation:
                    self.flush_aggregated_metrics()
                if not self._disable_buffering:
                    self.flush_buffered_metrics()
        self._flush_thread = threading.Thread(
            name="{}_flush_thread".format(self.__class__.__name__),
            target=_flush_thread_loop,
            args=(self, self._flush_interval,),
        )
        self._flush_thread.daemon = True
        self._flush_thread.start()
        log.debug(
            "Statsd flush thread registered with period of %s",
            self._flush_interval,
        )

    # Note: Invocations of this method should be thread-safe
    def _stop_flush_thread(self):
        if not self._flush_thread:
            return
        try:
            if not self._disable_aggregation:
                self.flush_aggregated_metrics()
            if not self.disable_buffering:
                self.flush_buffered_metrics()
        finally:
            pass

        self._flush_thread_stop.set()
        self._flush_thread.join()
        self._flush_thread = None
        self._flush_thread_stop.clear()

    def _dedicated_telemetry_destination(self):
        return bool(self.telemetry_socket_path or self.telemetry_host)

    # Context manager helper
    def __enter__(self):
        self.open_buffer()
        return self

    # Context manager helper
    def __exit__(self, exc_type, value, traceback):
        self.close_buffer()

    @property
    def disable_buffering(self):
        with self._config_lock:
            return self._disable_buffering

    @disable_buffering.setter
    def disable_buffering(self, is_disabled):
        with self._config_lock:
            # If the toggle didn't change anything, this method is a noop
            if self._disable_buffering == is_disabled:
                return

            self._disable_buffering = is_disabled

            # If buffering (and aggregation) has been disabled, flush and kill the background thread
            # otherwise start up the flushing thread and enable the buffering.
            if is_disabled:
                self._send = self._send_to_server
                if self._disable_aggregation and self.disable_buffering:
                    self._stop_flush_thread()
                log.debug("Statsd buffering is disabled")
            else:
                self._send = self._send_to_buffer
                self._start_flush_thread()

    def disable_aggregation(self):
        with self._config_lock:
            # If the toggle didn't change anything, this method is a noop
            if self._disable_aggregation:
                return

            self._disable_aggregation = True

            # If aggregation and buffering has been disabled, flush and kill the background thread
            # otherwise start up the flushing thread and enable aggregation.
            if self._disable_aggregation and self.disable_buffering:
                self._stop_flush_thread()
            log.debug("Statsd aggregation is disabled")

    def enable_aggregation(self, flush_interval=DEFAULT_BUFFERING_FLUSH_INTERVAL, max_samples_per_context=0):
        with self._config_lock:
            if not self._disable_aggregation:
                return
            self.aggregator.set_max_samples_per_context(max_samples_per_context)
            self._disable_aggregation = False
            self._flush_interval = flush_interval
            if self._disable_buffering:
                self._send = self._send_to_server
            self._start_flush_thread()

    @staticmethod
    def resolve_host(host, use_default_route):
        """
        Resolve the DogStatsd host.

        :param host: host
        :type host: string
        :param use_default_route: Use the system default route as host (overrides `host` parameter)
        :type use_default_route: bool
        """
        if not use_default_route:
            return host

        return get_default_route()

    def get_socket(self, telemetry=False):
        """
        Return a connected socket.

        Note: connect the socket before assigning it to the class instance to
        avoid bad thread race conditions.
        """
        with self._socket_lock:
            if telemetry and self._dedicated_telemetry_destination():
                if not self.telemetry_socket:
                    if self.telemetry_socket_path is not None:
                        self.telemetry_socket = self._get_uds_socket(
                            self.telemetry_socket_path,
                            self.telemetry_socket_timeout,
                        )
                    else:
                        self.telemetry_socket = self._get_udp_socket(
                            self.telemetry_host,
                            self.telemetry_port,
                            self.telemetry_socket_timeout,
                        )

                return self.telemetry_socket

            if not self.socket:
                if self.socket_path is not None:
                    self.socket = self._get_uds_socket(self.socket_path, self.socket_timeout)
                else:
                    self.socket = self._get_udp_socket(
                        self.host,
                        self.port,
                        self.socket_timeout,
                    )

            return self.socket

    def set_socket_timeout(self, timeout):
        """
        Set timeout for socket operations, in seconds.

        If set to zero, never wait if operation can not be completed immediately. If set to None, wait forever.
        This option does not affect hostname resolution when using UDP.
        """
        with self._socket_lock:
            self.socket_timeout = timeout
            if self.socket:
                self.socket.settimeout(timeout)

    @classmethod
    def _ensure_min_send_buffer_size(cls, sock, min_size=MIN_SEND_BUFFER_SIZE):
        # Increase the receiving buffer size where needed (e.g. MacOS has 4k RX
        # buffers which is half of the max packet size that the client will send.
        if os.name == 'posix':
            try:
                recv_buff_size = sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
                if recv_buff_size <= min_size:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, min_size)
                    log.debug("Socket send buffer increased to %dkb", min_size / 1024)
            finally:
                pass

    @classmethod
    def _get_uds_socket(cls, socket_path, timeout):
        valid_socket_kinds = [socket.SOCK_DGRAM, socket.SOCK_STREAM]
        if socket_path.startswith(UNIX_ADDRESS_DATAGRAM_SCHEME):
            valid_socket_kinds = [socket.SOCK_DGRAM]
            socket_path = socket_path[len(UNIX_ADDRESS_DATAGRAM_SCHEME):]
        elif socket_path.startswith(UNIX_ADDRESS_STREAM_SCHEME):
            valid_socket_kinds = [socket.SOCK_STREAM]
            socket_path = socket_path[len(UNIX_ADDRESS_STREAM_SCHEME):]
        elif socket_path.startswith(UNIX_ADDRESS_SCHEME):
            socket_path = socket_path[len(UNIX_ADDRESS_SCHEME):]

        last_error = ValueError("Invalid socket path")
        for socket_kind in valid_socket_kinds:
            # py2 stores socket kinds differently than py3, determine the name independently from version
            sk_name = {socket.SOCK_STREAM: "stream", socket.SOCK_DGRAM: "datagram"}[socket_kind]

            try:
                sock = socket.socket(socket.AF_UNIX, socket_kind)
                sock.settimeout(timeout)
                cls._ensure_min_send_buffer_size(sock)
                sock.connect(socket_path)
                log.debug("Connected to socket %s with kind %s", socket_path, sk_name)
                return sock
            except Exception as e:
                if sock is not None:
                    sock.close()
                log.debug("Failed to connect to %s with kind %s: %s", socket_path, sk_name, e)
                if e.errno == errno.EPROTOTYPE:
                    last_error = e
                    continue
                raise e
        raise last_error

    @classmethod
    def _get_udp_socket(cls, host, port, timeout):
        log.debug("Connecting to %s:%s", host, port)
        addrinfo = socket.getaddrinfo(host, port, 0, socket.SOCK_DGRAM)
        # Override gai.conf order for backwrads compatibility: prefer
        # v4, so that a v4-only service on hosts with both addresses
        # still works.
        addrinfo.sort(key=lambda v: v[0] == socket.AF_INET, reverse=True)
        lastaddr = len(addrinfo) - 1
        for i, (af, ty, proto, _, addr) in enumerate(addrinfo):
            sock = None
            try:
                sock = socket.socket(af, ty, proto)
                sock.settimeout(timeout)
                cls._ensure_min_send_buffer_size(sock)
                sock.connect(addr)
                log.debug("Connected to: %s", addr)
                return sock
            except Exception as e:
                if sock is not None:
                    sock.close()
                log.debug("Failed to connect to %s: %s", addr, e)
                if i < lastaddr:
                    continue
                raise e
        else:
            raise ValueError("getaddrinfo returned no addresses to connect to")

    def open_buffer(self, max_buffer_size=None):
        """
        Open a buffer to send a batch of metrics.

        To take advantage of automatic flushing, you should use the context manager instead

        >>> with DogStatsd() as batch:
        >>>     batch.gauge("users.online", 123)
        >>>     batch.gauge("active.connections", 1001)

        Note: This method must be called before close_buffer() matching invocation.
        """

        self._config_lock.acquire()

        self._send = self._send_to_buffer

        if max_buffer_size is not None:
            log.warning("The parameter max_buffer_size is now deprecated and is not used anymore")

    def close_buffer(self):
        """
        Flush the buffer and switch back to single metric packets.

        Note: This method must be called after a matching open_buffer()
        invocation.
        """
        try:
            self.flush_buffered_metrics()
        finally:
            if self._disable_buffering:
                self._send = self._send_to_server

            self._config_lock.release()

    def _reset_buffer(self):
        with self._buffer_lock:
            self._current_buffer_total_size = 0
            self._buffer = []

    def flush(self):
        self.flush_buffered_metrics()

    def flush_buffered_metrics(self):
        """
        Flush the metrics buffer by sending the data to the server.
        """
        with self._buffer_lock:
            # Only send packets if there are packets to send
            if self._buffer:
                self._send_to_server("\n".join(self._buffer))
                self._reset_buffer()

    def flush_aggregated_metrics(self):
        """
        Flush the aggregated metrics
        """
        metrics = self.aggregator.flush_aggregated_metrics()
        for m in metrics:
            self._report(m.name, m.metric_type, m.value, m.tags, m.rate, m.timestamp, cardinality=m.cardinality)

        sampled_metrics = self.aggregator.flush_aggregated_sampled_metrics()
        for m in sampled_metrics:
            self._report(m.name, m.metric_type, m.value, m.tags, m.rate, m.timestamp, False)

    def gauge(
        self,
        metric,  # type: Text
        value,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Record the value of a gauge, optionally setting a list of tags and a
        sample rate.

        >>> statsd.gauge("users.online", 123)
        >>> statsd.gauge("active.connections", 1001, tags=["protocol:http"])
        """
        if self._disable_aggregation:
            self._report(metric, "g", value, tags, sample_rate, cardinality=cardinality)
        else:
            self.aggregator.gauge(metric, value, tags, sample_rate, cardinality=cardinality)

    # Minimum Datadog Agent version: 7.40.0
    def gauge_with_timestamp(
        self,
        metric,  # type: Text
        value,  # type: float
        timestamp,  # type: int
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """u
        Record the value of a gauge with a Unix timestamp (in seconds),
        optionally setting a list of tags and a sample rate.

        Minimum Datadog Agent version: 7.40.0

        >>> statsd.gauge("users.online", 123, 1713804588)
        >>> statsd.gauge("active.connections", 1001, 1713804588, tags=["protocol:http"])
        """
        if self._disable_aggregation:
            self._report(metric, "g", value, tags, sample_rate, timestamp, cardinality=cardinality)
        else:
            self.aggregator.gauge(metric, value, tags, sample_rate, timestamp, cardinality=cardinality)

    def count(
        self,
        metric,  # type: Text
        value,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Count tracks how many times something happened per second, tags and a sample
        rate.

        >>> statsd.count("page.views", 123)
        """
        if self._disable_aggregation:
            self._report(metric, "c", value, tags, sample_rate, cardinality=cardinality)
        else:
            self.aggregator.count(metric, value, tags, sample_rate, cardinality=cardinality)

    # Minimum Datadog Agent version: 7.40.0
    def count_with_timestamp(
        self,
        metric,  # type: Text
        value,  # type: float
        timestamp=0,  # type: int
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Count how many times something happened at a given Unix timestamp in seconds,
        tags and a sample rate.

        Minimum Datadog Agent version: 7.40.0

        >>> statsd.count("files.transferred", 124, timestamp=1713804588)
        """
        if self._disable_aggregation:
            self._report(metric, "c", value, tags, sample_rate, timestamp, cardinality=cardinality)
        else:
            self.aggregator.count(metric, value, tags, sample_rate, timestamp, cardinality=cardinality)

    def increment(
        self,
        metric,  # type: Text
        value=1,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Increment a counter, optionally setting a value, tags and a sample
        rate.

        >>> statsd.increment("page.views")
        >>> statsd.increment("files.transferred", 124)
        """
        if self._disable_aggregation:
            self._report(metric, "c", value, tags, sample_rate, cardinality=cardinality)
        else:
            self.aggregator.count(metric, value, tags, sample_rate, cardinality=cardinality)

    def decrement(
        self,
        metric,  # type: Text
        value=1,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Decrement a counter, optionally setting a value, tags and a sample
        rate.

        >>> statsd.decrement("files.remaining")
        >>> statsd.decrement("active.connections", 2)
        """
        metric_value = -value if value else value
        if self._disable_aggregation:
            self._report(metric, "c", metric_value, tags, sample_rate, cardinality=cardinality)
        else:
            self.aggregator.count(metric, metric_value, tags, sample_rate, cardinality=cardinality)

    def histogram(
        self,
        metric,  # type: Text
        value,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Sample a histogram value, optionally setting tags and a sample rate.

        >>> statsd.histogram("uploaded.file.size", 1445)
        >>> statsd.histogram("album.photo.count", 26, tags=["gender:female"])
        """
        if not self._disable_aggregation and self.aggregator.max_samples_per_context != 0:
            self.aggregator.histogram(metric, value, tags, sample_rate, cardinality=cardinality)
        else:
            self._report(metric, "h", value, tags, sample_rate, cardinality=cardinality)

    def distribution(
        self,
        metric,  # type: Text
        value,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Send a global distribution value, optionally setting tags and a sample rate.

        >>> statsd.distribution("uploaded.file.size", 1445)
        >>> statsd.distribution("album.photo.count", 26, tags=["gender:female"])
        """
        if not self._disable_aggregation and self.aggregator.max_samples_per_context != 0:
            self.aggregator.distribution(metric, value, tags, sample_rate, cardinality=cardinality)
        else:
            self._report(metric, "d", value, tags, sample_rate, cardinality=cardinality)

    def timing(
        self,
        metric,  # type: Text
        value,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        cardinality=None,  # type: Optional[str]
    ):  # type(...) -> None
        """
        Record a timing, optionally setting tags and a sample rate.

        >>> statsd.timing("query.response.time", 1234)
        """
        if not self._disable_aggregation and self.aggregator.max_samples_per_context != 0:
            self.aggregator.timing(metric, value, tags, sample_rate, cardinality=cardinality)
        else:
            self._report(metric, "ms", value, tags, sample_rate, cardinality=cardinality)

    def timed(
        self,
        metric=None,  # type: Optional[Text]
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
        use_ms=None,  # type: Optional[bool]
    ):  # type(...) -> TimedContextManagerDecorator
        """
        A decorator or context manager that will measure the distribution of a
        function's/context's run time. Optionally specify a list of tags or a
        sample rate. If the metric is not defined as a decorator, the module
        name and function name will be used. The metric is required as a context
        manager.
        ::

            @statsd.timed("user.query.time", sample_rate=0.5)
            def get_user(user_id):
                # Do what you need to ...
                pass

            # Is equivalent to ...
            with statsd.timed("user.query.time", sample_rate=0.5):
                # Do what you need to ...
                pass

            # Is equivalent to ...
            start = time.time()
            try:
                get_user(user_id)
            finally:
                statsd.timing("user.query.time", time.time() - start)
        """
        return TimedContextManagerDecorator(self, metric, tags, sample_rate, use_ms)

    def distributed(self, metric=None, tags=None, sample_rate=None, use_ms=None):
        """
        A decorator or context manager that will measure the distribution of a
        function's/context's run time using custom metric distribution.
        Optionally specify a list of tags or a sample rate. If the metric is not
        defined as a decorator, the module name and function name will be used.
        The metric is required as a context manager.
        ::

            @statsd.distributed("user.query.time", sample_rate=0.5)
            def get_user(user_id):
                # Do what you need to ...
                pass

            # Is equivalent to ...
            with statsd.distributed("user.query.time", sample_rate=0.5):
                # Do what you need to ...
                pass

            # Is equivalent to ...
            start = time.time()
            try:
                get_user(user_id)
            finally:
                statsd.distribution("user.query.time", time.time() - start)
        """
        return DistributedContextManagerDecorator(self, metric, tags, sample_rate, use_ms)

    def set(self, metric, value, tags=None, sample_rate=None, cardinality=None):
        """
        Sample a set value.

        >>> statsd.set("visitors.uniques", 999)
        """
        if self._disable_aggregation:
            self._report(metric, "s", value, tags, sample_rate, cardinality=cardinality)
        else:
            self.aggregator.set(metric, value, tags, sample_rate, cardinality=cardinality)

    def close_socket(self):
        """
        Closes connected socket if connected.
        """
        with self._socket_lock:
            if self.socket:
                try:
                    self.socket.close()
                except OSError as e:
                    log.error("Unexpected error: %s", str(e))
                self.socket = None

            if self.telemetry_socket:
                try:
                    self.telemetry_socket.close()
                except OSError as e:
                    log.error("Unexpected error: %s", str(e))
                self.telemetry_socket = None

    def _serialize_metric(
        self, metric, metric_type, value, tags, sample_rate=1, timestamp=0, cardinality=None
    ):
        # Create/format the metric packet
        return "%s%s:%s|%s%s%s%s%s%s%s" % (
            (self.namespace + ".") if self.namespace else "",
            metric,
            value,
            metric_type,
            ("|@" + text(sample_rate)) if sample_rate != 1 else "",
            ("|#" + ",".join(normalize_tags(tags))) if tags else "",
            ("|c:" + self._container_id if self._container_id else ""),
            ("|e:" + self._external_data if self._external_data else ""),
            ("|card:" + cardinality if cardinality else ""),
            ("|T" + text(timestamp)) if timestamp > 0 else "",
        )

    def _report(self, metric, metric_type, value, tags, sample_rate, timestamp=0, sampling=True, cardinality=None):
        """
        Create a metric packet and send it.

        More information about the packets' format:
        https://docs.datadoghq.com/developers/dogstatsd/datagram_shell/?tab=metrics#the-dogstatsd-protocol
        """
        if value is None:
            return

        if self._enabled is not True:
            return

        if self._telemetry:
            self.metrics_count += 1

        if sampling:
            if sample_rate is None:
                sample_rate = self.default_sample_rate

            if sample_rate != 1 and random() > sample_rate:
                return
        # timestamps (protocol v1.3) only allowed on gauges and counts
        allows_timestamp = metric_type == MetricType.GAUGE or metric_type == MetricType.COUNT

        if not allows_timestamp or timestamp < 0:
            timestamp = 0

        if cardinality is None:
            cardinality = self.cardinality

        validate_cardinality(cardinality)

        # Resolve the full tag list
        tags = self._add_constant_tags(tags)
        payload = self._serialize_metric(
            metric, metric_type, value, tags, sample_rate, timestamp, cardinality
        )

        # Send it
        self._send(payload)

    def _reset_telemetry(self):
        self.metrics_count = 0
        self.events_count = 0
        self.service_checks_count = 0
        self.bytes_sent = 0
        self.bytes_dropped_queue = 0
        self.bytes_dropped_writer = 0
        self.packets_sent = 0
        self.packets_dropped_queue = 0
        self.packets_dropped_writer = 0
        self._last_flush_time = time.time()

    # Aliases for backwards compatibility.
    @property
    def packets_dropped(self):
        return self.packets_dropped_queue + self.packets_dropped_writer

    @property
    def bytes_dropped(self):
        return self.bytes_dropped_queue + self.bytes_dropped_writer

    def _flush_telemetry(self):
        tags = self._client_tags[:]
        tags.append("client_transport:{}".format(self._transport))
        tags.extend(self.constant_tags)
        telemetry_tags = ",".join(tags)

        return TELEMETRY_FORMATTING_STR % (
            self.metrics_count,
            telemetry_tags,
            self.events_count,
            telemetry_tags,
            self.service_checks_count,
            telemetry_tags,
            self.bytes_sent,
            telemetry_tags,
            self.bytes_dropped_queue + self.bytes_dropped_writer,
            telemetry_tags,
            self.bytes_dropped_queue,
            telemetry_tags,
            self.bytes_dropped_writer,
            telemetry_tags,
            self.packets_sent,
            telemetry_tags,
            self.packets_dropped_queue + self.packets_dropped_writer,
            telemetry_tags,
            self.packets_dropped_queue,
            telemetry_tags,
            self.packets_dropped_writer,
            telemetry_tags,
        )

    def _is_telemetry_flush_time(self):
        return self._telemetry and \
            self._last_flush_time + self._telemetry_flush_interval < time.time()

    def _send_to_server(self, packet):
        # Skip the lock if the queue is None. There is no race with enable_background_sender.
        if self._queue is not None:
            # Prevent a race with disable_background_sender.
            with self._buffer_lock:
                if self._queue is not None:
                    try:
                        self._queue.put(packet + '\n', self._queue_blocking, self._queue_timeout)
                    except queue.Full:
                        self.packets_dropped_queue += 1
                        self.bytes_dropped_queue += 1
                    return

        self._xmit_packet_with_telemetry(packet + '\n')

    def _xmit_packet_with_telemetry(self, packet):
        self._xmit_packet(packet, False)

        if self._is_telemetry_flush_time():
            telemetry = self._flush_telemetry()
            if self._xmit_packet(telemetry, True):
                self._reset_telemetry()
                self.packets_sent += 1
                self.bytes_sent += len(telemetry)
            else:
                # Telemetry packet has been dropped, keep telemetry data for the next flush
                self._last_flush_time = time.time()
                self.bytes_dropped_writer += len(telemetry)
                self.packets_dropped_writer += 1

    def _xmit_packet(self, packet, is_telemetry):
        socket_kind = None
        try:
            if is_telemetry and self._dedicated_telemetry_destination():
                mysocket = self.telemetry_socket or self.get_socket(telemetry=True)
                socket_kind = self._telemetry_socket_kind
            else:
                # If set, use socket directly
                mysocket = self.socket or self.get_socket()
                socket_kind = self._socket_kind

            encoded_packet = packet.encode(self.encoding)
            if socket_kind == socket.SOCK_STREAM:
                with self._socket_lock:
                    mysocket.sendall(struct.pack('<I', len(encoded_packet)))
                    mysocket.sendall(encoded_packet)
            else:
                mysocket.send(encoded_packet)

            if not is_telemetry and self._telemetry:
                self.packets_sent += 1
                self.bytes_sent += len(packet)

            return True
        except socket.timeout:
            # dogstatsd is overflowing, drop the packets (mimics the UDP behaviour)
            pass
        except (socket.herror, socket.gaierror) as socket_err:
            log.warning(
                "Error submitting packet: %s, dropping the packet and closing the socket",
                socket_err,
            )
            self.close_socket()
        except socket.error as socket_err:
            if socket_err.errno == errno.EAGAIN:
                log.debug("Socket send would block: %s, dropping the packet", socket_err)
            elif socket_err.errno == errno.ENOBUFS:
                log.debug("Socket buffer full: %s, dropping the packet", socket_err)
            elif socket_err.errno == errno.EMSGSIZE:
                log.debug(
                    "Packet size too big (size: %d): %s, dropping the packet",
                    len(packet.encode(self.encoding)),
                    socket_err)
            else:
                log.warning(
                    "Error submitting packet: %s, dropping the packet and closing the socket",
                    socket_err,
                )
                self.close_socket()
        except Exception as exc:
            print("Unexpected error: ", exc)
            log.error("Unexpected error: %s", str(exc))

        if not is_telemetry and self._telemetry:
            self.bytes_dropped_writer += len(packet)
            self.packets_dropped_writer += 1

        # if in stream mode we need to shut down the socket; we can't recover from a
        # partial send
        if socket_kind == socket.SOCK_STREAM:
            log.debug("Confirming socket closure after error streaming")
            self.close_socket()

        return False

    def _send_to_buffer(self, packet):
        with self._buffer_lock:
            if self._should_flush(len(packet)):
                self.flush_buffered_metrics()

            self._buffer.append(packet)
            # Update the current buffer length, including line break to anticipate
            # the final packet size
            self._current_buffer_total_size += len(packet) + 1

    def _should_flush(self, length_to_be_added):
        if self._current_buffer_total_size + length_to_be_added + 1 > self._max_payload_size:
            return True
        return False

    @staticmethod
    def _escape_event_content(string):
        return string.replace("\n", "\\n")

    @staticmethod
    def _escape_service_check_message(string):
        return string.replace("\n", "\\n").replace("m:", "m\\:")

    def event(
        self,
        title,
        message,
        alert_type=None,
        aggregation_key=None,
        source_type_name=None,
        date_happened=None,
        priority=None,
        tags=None,
        hostname=None,
        cardinality=None,
    ):
        """
        Send an event. Attributes are the same as the Event API.
            http://docs.datadoghq.com/api/

        >>> statsd.event("Man down!", "This server needs assistance.")
        >>> statsd.event("Web server restart", "The web server is up", alert_type="success")  # NOQA
        """
        title = DogStatsd._escape_event_content(title)
        message = DogStatsd._escape_event_content(message)

        # pylint: disable=undefined-variable
        if not is_p3k():
            if not isinstance(title, unicode):                                       # noqa: F821
                title = unicode(DogStatsd._escape_event_content(title), 'utf8')      # noqa: F821
            if not isinstance(message, unicode):                                     # noqa: F821
                message = unicode(DogStatsd._escape_event_content(message), 'utf8')  # noqa: F821

        # Append all client level tags to every event
        tags = self._add_constant_tags(tags)

        string = u"_e{{{},{}}}:{}|{}".format(
            len(title.encode('utf8', 'replace')),
            len(message.encode('utf8', 'replace')),
            title,
            message,
        )

        if cardinality is None:
            cardinality = self.cardinality

        validate_cardinality(cardinality)

        if date_happened:
            string = "%s|d:%d" % (string, date_happened)
        if hostname:
            string = "%s|h:%s" % (string, hostname)
        if aggregation_key:
            string = "%s|k:%s" % (string, aggregation_key)
        if priority:
            string = "%s|p:%s" % (string, priority)
        if source_type_name:
            string = "%s|s:%s" % (string, source_type_name)
        if alert_type:
            string = "%s|t:%s" % (string, alert_type)
        if tags:
            string = "%s|#%s" % (string, ",".join(tags))
        if self._container_id:
            string = "%s|c:%s" % (string, self._container_id)
        if cardinality:
            string = "%s|card:%s" % (string, cardinality)

        if len(string) > 8 * 1024:
            raise ValueError(
                u'Event "{0}" payload is too big (>=8KB). Event discarded'.format(
                    title
                )
            )

        if self._telemetry:
            self.events_count += 1

        self._send(string)

    def service_check(
        self,
        check_name,
        status,
        tags=None,
        timestamp=None,
        cardinality=None,
        hostname=None,
        message=None,
    ):
        """
        Send a service check run.

        >>> statsd.service_check("my_service.check_name", DogStatsd.WARNING)
        """
        message = DogStatsd._escape_service_check_message(message) if message is not None else ""

        string = u"_sc|{0}|{1}".format(check_name, status)

        # Append all client level tags to every status check
        tags = self._add_constant_tags(tags)

        if cardinality is None:
            cardinality = self.cardinality

        validate_cardinality(cardinality)

        if timestamp:
            string = u"{0}|d:{1}".format(string, timestamp)
        if hostname:
            string = u"{0}|h:{1}".format(string, hostname)
        if tags:
            string = u"{0}|#{1}".format(string, ",".join(tags))
        if message:
            string = u"{0}|m:{1}".format(string, message)
        if self._container_id:
            string = u"{0}|c:{1}".format(string, self._container_id)
        if cardinality:
            string = u"{0}|card:{1}".format(string, cardinality)

        if self._telemetry:
            self.service_checks_count += 1

        self._send(string)

    def _add_constant_tags(self, tags):
        if self.constant_tags:
            if tags:
                return tags + self.constant_tags

            return self.constant_tags
        return tags

    def _is_origin_detection_enabled(self, container_id, origin_detection_enabled):
        """
        Returns whether the client should fill the container field.
        If a user-defined container ID is provided, we don't ignore origin detection
        as dd.internal.entity_id is prioritized over the container field for backward compatibility.
        We try to fill the container field automatically unless DD_ORIGIN_DETECTION_ENABLED is explicitly set to false.
        """
        if not origin_detection_enabled or container_id is not None:
            # origin detection is explicitly disabled
            # or a user-defined container ID was provided
            return False
        value = os.environ.get(ORIGIN_DETECTION_ENABLED, "")
        return value.lower() not in {"no", "false", "0", "n", "off"}

    def _set_container_id(self, container_id, origin_detection_enabled):
        """
        Initializes the container ID.
        It can either be provided by the user or read from cgroups.
        """
        if container_id:
            self._container_id = container_id
            return
        if origin_detection_enabled:
            try:
                reader = Cgroup()
                self._container_id = reader.container_id
            except Exception as e:
                log.debug("Couldn't get container ID: %s", str(e))
                self._container_id = None

    def _start_sender_thread(self):
        if not self._sender_enabled or self._forking:
            return

        if self._queue is not None:
            return

        self._queue = queue.Queue(self._sender_queue_size)

        log.debug("Starting background sender thread")
        self._sender_thread = threading.Thread(
            name="{}_sender_thread".format(self.__class__.__name__),
            target=self._sender_main_loop,
            args=(self._queue,)
        )
        self._sender_thread.daemon = True
        self._sender_thread.start()

    def _stop_sender_thread(self):
        # Lock ensures that nothing gets added to the queue after we disable it.
        with self._buffer_lock:
            if not self._queue:
                return
            self._queue.put(Stop)
            self._queue = None

        self._sender_thread.join()
        self._sender_thread = None

    def _sender_main_loop(self, queue):
        while True:
            item = queue.get()
            if item is Stop:
                queue.task_done()
                return
            self._xmit_packet_with_telemetry(item)
            queue.task_done()

    def wait_for_pending(self):
        """
        Flush the buffer and wait for all queued payloads to be written to the server.
        """

        self.flush_buffered_metrics()

        # Avoid race with disable_background_sender. We don't need a
        # lock, just copy the value so it doesn't change between the
        # check and join later.
        queue = self._queue

        if queue is not None:
            queue.join()

    def pre_fork(self):
        """Prepare client for a process fork.

        Flush any pending payloads and stop all background threads.

        The client should not be used from this point until
        state is restored by calling post_fork_parent() or
        post_fork_child().
        """

        # Hold the config lock across fork. This will make sure that
        # we don't fork in the middle of the concurrent modification
        # of the client's settings. Data protected by other locks may
        # be left in inconsistent state in the child process, which we
        # will clean up in post_fork_child.

        self._config_lock.acquire()
        self._stop_flush_thread()
        self._stop_sender_thread()

    def post_fork_parent(self):
        """Restore the client state after a fork in the parent process."""
        self._start_flush_thread()
        self._start_sender_thread()
        self._config_lock.release()

    def post_fork_child(self):
        """Restore the client state after a fork in the child process."""
        self._config_lock.release()

        # Discard the locks that could have been locked at the time
        # when we forked. This may cause inconsistent internal state,
        # which we will fix in the next steps.
        self._socket_lock = Lock()
        self._buffer_lock = RLock()

        # Reset the buffer so we don't send metrics from the parent
        # process. Also makes sure buffer properties are consistent.
        self._reset_buffer()
        # Execute the socket_path setter to reconcile transport and
        # payload size properties in respect to socket_path value.
        self.socket_path = self.socket_path
        self.close_socket()

        with self._config_lock:
            self._start_flush_thread()
            self._start_sender_thread()

    def stop(self):
        """Stop the client.

        Disable buffering, aggregation, background sender and flush any pending payloads to the server.

        Client remains usable after this method, but sending metrics may block if socket_timeout is enabled.
        """

        self.disable_background_sender()
        self._disable_buffering = True
        self._disable_aggregation = True
        self.flush_aggregated_metrics()
        self.flush_buffered_metrics()
        self.close_socket()


statsd = DogStatsd()
