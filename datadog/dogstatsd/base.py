#!/usr/bin/env python

# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
DogStatsd is a Python client for DogStatsd, a Statsd fork for Datadog.
"""
# stdlib
from random import random
import logging
import os
import socket
import errno
import time
from threading import Lock

# datadog
from datadog.dogstatsd.context import (
    TimedContextManagerDecorator,
    DistributedContextManagerDecorator,
)
from datadog.dogstatsd.route import get_default_route
from datadog.util.compat import text
from datadog.util.format import normalize_tags
from datadog.version import __version__
from typing import Optional, List, Text, Union

# Logging
log = logging.getLogger("datadog.dogstatsd")

# Default config
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8125

# Tag name of entity_id
ENTITY_ID_TAG_NAME = "dd.internal.entity_id"

# Default buffer settings
UDP_OPTIMAL_PAYLOAD_LENGTH = 1432
UDS_OPTIMAL_PAYLOAD_LENGTH = 8192

# Mapping of each "DD_" prefixed environment variable to a specific tag name
DD_ENV_TAGS_MAPPING = {
    "DD_ENTITY_ID": ENTITY_ID_TAG_NAME,
    "DD_ENV": "env",
    "DD_SERVICE": "service",
    "DD_VERSION": "version",
}

# Telemetry minimum flush interval in seconds
DEFAULT_TELEMETRY_MIN_FLUSH_INTERVAL = 10


class DogStatsd(object):
    OK, WARNING, CRITICAL, UNKNOWN = (0, 1, 2, 3)

    def __init__(
        self,
        host=DEFAULT_HOST,  # type: Text
        port=DEFAULT_PORT,  # type: int
        max_buffer_size=None,  # type: None
        namespace=None,  # type: Optional[Text]
        constant_tags=None,  # type: Optional[List[str]]
        use_ms=False,  # type: bool
        use_default_route=False,  # type: bool
        socket_path=None,  # type: Optional[Text]
        default_sample_rate=1,  # type: float
        disable_telemetry=False,  # type: bool
        telemetry_min_flush_interval=(DEFAULT_TELEMETRY_MIN_FLUSH_INTERVAL),  # type: int
        telemetry_host=None,  # type: Text
        telemetry_port=None,  # type: Union[str, int]
        telemetry_socket_path=None,  # type: Text
        max_buffer_len=0,  # type: int
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

        :param host: the host of the DogStatsd server.
        :type host: string

        :param port: the port of the DogStatsd server.
        :type port: integer

        :max_buffer_size: Deprecated option, do not use it anymore.
        :type max_buffer_type: None

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
        """

        self.lock = Lock()

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
        self._max_payload_size = max_buffer_len
        if socket_path is not None:
            self.socket_path = socket_path  # type: Optional[text]
            self.host = None
            self.port = None
            transport = "uds"
            if not self._max_payload_size:
                self._max_payload_size = UDS_OPTIMAL_PAYLOAD_LENGTH
        else:
            self.socket_path = None
            self.host = self.resolve_host(host, use_default_route)
            self.port = int(port)
            transport = "udp"
            if not self._max_payload_size:
                self._max_payload_size = UDP_OPTIMAL_PAYLOAD_LENGTH

        self.telemetry_socket_path = telemetry_socket_path
        self.telemetry_host = None
        self.telemetry_port = None
        if not telemetry_socket_path and telemetry_host:
            self.telemetry_socket_path = None
            self.telemetry_host = self.resolve_host(telemetry_host, use_default_route)
            self.telemetry_port = int(telemetry_port)

        # Socket
        self.socket = None
        self.telemetry_socket = None
        self._send = self._send_to_server
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
        self.use_ms = use_ms
        self.default_sample_rate = default_sample_rate

        # init telemetry version
        self._client_tags = [
            "client:py",
            "client_version:{}".format(__version__),
            "client_transport:{}".format(transport),
        ]
        self._reset_telemetry()
        self._telemetry_flush_interval = telemetry_min_flush_interval
        self._telemetry = not disable_telemetry

    def disable_telemetry(self):
        self._telemetry = False

    def enable_telemetry(self):
        self._telemetry = True

    def _dedicated_telemetry_destination(self):
        return bool(self.telemetry_socket_path or self.telemetry_host)

    def __enter__(self):
        self.open_buffer()
        return self

    def __exit__(self, type, value, traceback):
        self.close_buffer()

    @staticmethod
    def resolve_host(host, use_default_route):
        """
        Resolve the DogStatsd host.

        :param host: host
        :type host: string
        :param use_default_route: use the system default route as host (overrides the `host` parameter)
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
        with self.lock:
            if telemetry and self._dedicated_telemetry_destination():
                if not self.telemetry_socket:
                    if self.telemetry_socket_path is not None:
                        self.telemetry_socket = self._get_uds_socket(self.telemetry_socket_path)
                    else:
                        self.telemetry_socket = self._get_udp_socket_socket(self.telemetry_host, self.telemetry_port)

                return self.telemetry_socket

            if not self.socket:
                if self.socket_path is not None:
                    self.socket = self._get_uds_socket(self.socket_path)
                else:
                    self.socket = self._get_udp_socket(self.host, self.port)

            return self.socket

    @staticmethod
    def _get_uds_socket(socket_path):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.setblocking(0)
        sock.connect(socket_path)
        return sock

    @staticmethod
    def _get_udp_socket(host, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(0)
        sock.connect((host, port))
        return sock

    def open_buffer(self, max_buffer_size=None):
        """
        Open a buffer to send a batch of metrics.

        You can also use this as a context manager.

        >>> with DogStatsd() as batch:
        >>>     batch.gauge("users.online", 123)
        >>>     batch.gauge("active.connections", 1001)
        """
        if max_buffer_size is not None:
            log.warning("The parameter max_buffer_size is now deprecated and is not used anymore")
        self._current_buffer_total_size = 0
        self.buffer = []
        self._send = self._send_to_buffer

    def close_buffer(self):
        """
        Flush the buffer and switch back to single metric packets.
        """
        self._send = self._send_to_server

        if self.buffer:
            # Only send packets if there are packets to send
            self._flush_buffer()

    def gauge(
        self,
        metric,  # type: Text
        value,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
    ):  # type(...) -> None
        """
        Record the value of a gauge, optionally setting a list of tags and a
        sample rate.

        >>> statsd.gauge("users.online", 123)
        >>> statsd.gauge("active.connections", 1001, tags=["protocol:http"])
        """
        return self._report(metric, "g", value, tags, sample_rate)

    def increment(
        self,
        metric,  # type: Text
        value=1,  # type: float
        tags=None,  # type: Optional[List[str]]
        sample_rate=None,  # type: Optional[float]
    ):  # type: (...) -> None
        """
        Increment a counter, optionally setting a value, tags and a sample
        rate.

        >>> statsd.increment("page.views")
        >>> statsd.increment("files.transferred", 124)
        """
        self._report(metric, "c", value, tags, sample_rate)

    def decrement(self, metric, value=1, tags=None, sample_rate=None):
        """
        Decrement a counter, optionally setting a value, tags and a sample
        rate.

        >>> statsd.decrement("files.remaining")
        >>> statsd.decrement("active.connections", 2)
        """
        metric_value = -value if value else value
        self._report(metric, "c", metric_value, tags, sample_rate)

    def histogram(self, metric, value, tags=None, sample_rate=None):
        """
        Sample a histogram value, optionally setting tags and a sample rate.

        >>> statsd.histogram("uploaded.file.size", 1445)
        >>> statsd.histogram("album.photo.count", 26, tags=["gender:female"])
        """
        self._report(metric, "h", value, tags, sample_rate)

    def distribution(self, metric, value, tags=None, sample_rate=None):
        """
        Send a global distribution value, optionally setting tags and a sample rate.

        >>> statsd.distribution("uploaded.file.size", 1445)
        >>> statsd.distribution("album.photo.count", 26, tags=["gender:female"])
        """
        self._report(metric, "d", value, tags, sample_rate)

    def timing(self, metric, value, tags=None, sample_rate=None):
        """
        Record a timing, optionally setting tags and a sample rate.

        >>> statsd.timing("query.response.time", 1234)
        """
        self._report(metric, "ms", value, tags, sample_rate)

    def timed(self, metric=None, tags=None, sample_rate=None, use_ms=None):
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

    def set(self, metric, value, tags=None, sample_rate=None):
        """
        Sample a set value.

        >>> statsd.set("visitors.uniques", 999)
        """
        self._report(metric, "s", value, tags, sample_rate)

    def close_socket(self):
        """
        Closes connected socket if connected.
        """
        with self.lock:
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

    def _serialize_metric(self, metric, metric_type, value, tags, sample_rate=1):
        # Create/format the metric packet
        return "%s%s:%s|%s%s%s" % (
            (self.namespace + ".") if self.namespace else "",
            metric,
            value,
            metric_type,
            ("|@" + text(sample_rate)) if sample_rate != 1 else "",
            ("|#" + ",".join(normalize_tags(tags))) if tags else "",
        )

    def _report(self, metric, metric_type, value, tags, sample_rate):
        """
        Create a metric packet and send it.

        More information about the packets' format: http://docs.datadoghq.com/guides/dogstatsd/
        """
        if value is None:
            return

        if self._enabled is not True:
            return

        if self._telemetry:
            self.metrics_count += 1

        if sample_rate is None:
            sample_rate = self.default_sample_rate

        if sample_rate != 1 and random() > sample_rate:
            return

        # Resolve the full tag list
        tags = self._add_constant_tags(tags)
        payload = self._serialize_metric(metric, metric_type, value, tags, sample_rate)

        # Send it
        self._send(payload)

    def _reset_telemetry(self):
        self.metrics_count = 0
        self.events_count = 0
        self.service_checks_count = 0
        self.bytes_sent = 0
        self.bytes_dropped = 0
        self.packets_sent = 0
        self.packets_dropped = 0
        self._last_flush_time = time.time()

    def _flush_telemetry(self):
        telemetry_tags = ",".join(self._add_constant_tags(self._client_tags))
        return "\n".join(
            (
                "datadog.dogstatsd.client.metrics:%s|c|#%s" % (self.metrics_count, telemetry_tags),
                "datadog.dogstatsd.client.events:%s|c|#%s" % (self.events_count, telemetry_tags),
                "datadog.dogstatsd.client.service_checks:%s|c|#%s" % (self.service_checks_count, telemetry_tags),
                "datadog.dogstatsd.client.bytes_sent:%s|c|#%s" % (self.bytes_sent, telemetry_tags),
                "datadog.dogstatsd.client.bytes_dropped:%s|c|#%s" % (self.bytes_dropped, telemetry_tags),
                "datadog.dogstatsd.client.packets_sent:%s|c|#%s" % (self.packets_sent, telemetry_tags),
                "datadog.dogstatsd.client.packets_dropped:%s|c|#%s" % (self.packets_dropped, telemetry_tags),
            )
        )

    def _is_telemetry_flush_time(self):
        return self._telemetry and self._last_flush_time + self._telemetry_flush_interval < time.time()

    def _send_to_server(self, packet):
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
                self.bytes_dropped += len(telemetry)
                self.packets_dropped += 1

    def _xmit_packet(self, packet, is_telemetry):
        try:
            if is_telemetry and self._dedicated_telemetry_destination():
                mysocket = self.telemetry_socket or self.get_socket(telemetry=True)
            else:
                # If set, use socket directly
                mysocket = self.socket or self.get_socket()

            mysocket.send(packet.encode(self.encoding))

            if not is_telemetry and self._telemetry:
                self.packets_sent += 1
                self.bytes_sent += len(packet)

            return True
        except socket.timeout:
            # dogstatsd is overflowing, drop the packets (mimicks the UDP behaviour)
            pass
        except (socket.herror, socket.gaierror) as se:
            log.warning(
                "Error submitting packet: %s, dropping the packet and closing the socket",
                se,
            )
            self.close_socket()
        except socket.error as se:
            if se.errno == errno.EAGAIN:
                log.debug("Socket send would block: %s, dropping the packet", se)
            else:
                log.warning(
                    "Error submitting packet: %s, dropping the packet and closing the socket",
                    se,
                )
                self.close_socket()
        except Exception as e:
            log.error("Unexpected error: %s", str(e))
        if not is_telemetry and self._telemetry:
            self.bytes_dropped += len(packet)
            self.packets_dropped += 1
        return False

    def _send_to_buffer(self, packet):
        if self._should_flush(len(packet)):
            self._flush_buffer()
        self.buffer.append(packet)
        # Update the current buffer length, including line break to anticipate the final packet size
        self._current_buffer_total_size += len(packet) + 1

    def _should_flush(self, length_to_be_added):
        if self._current_buffer_total_size + length_to_be_added > self._max_payload_size:
            return True
        return False

    def _flush_buffer(self):
        self._send_to_server("\n".join(self.buffer))
        self._current_buffer_total_size = 0
        self.buffer = []

    def _escape_event_content(self, string):
        return string.replace("\n", "\\n")

    def _escape_service_check_message(self, string):
        return string.replace("\n", "\\n").replace("m:", "m\\:")

    def event(
        self,
        title,
        text,
        alert_type=None,
        aggregation_key=None,
        source_type_name=None,
        date_happened=None,
        priority=None,
        tags=None,
        hostname=None,
    ):
        """
        Send an event. Attributes are the same as the Event API.
            http://docs.datadoghq.com/api/

        >>> statsd.event("Man down!", "This server needs assistance.")
        >>> statsd.event("The web server restarted", "The web server is up again", alert_type="success")  # NOQA
        """
        title = self._escape_event_content(title)
        text = self._escape_event_content(text)

        # Append all client level tags to every event
        tags = self._add_constant_tags(tags)

        string = u"_e{%d,%d}:%s|%s" % (len(title), len(text), title, text)
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

        if len(string) > 8 * 1024:
            raise Exception(u'Event "%s" payload is too big (more than 8KB), ' "event discarded" % title)

        if self._telemetry:
            self.events_count += 1
        self._send(string)

    def service_check(self, check_name, status, tags=None, timestamp=None, hostname=None, message=None):
        """
        Send a service check run.

        >>> statsd.service_check("my_service.check_name", DogStatsd.WARNING)
        """
        message = self._escape_service_check_message(message) if message is not None else ""

        string = u"_sc|{0}|{1}".format(check_name, status)

        # Append all client level tags to every status check
        tags = self._add_constant_tags(tags)

        if timestamp:
            string = u"{0}|d:{1}".format(string, timestamp)
        if hostname:
            string = u"{0}|h:{1}".format(string, hostname)
        if tags:
            string = u"{0}|#{1}".format(string, ",".join(tags))
        if message:
            string = u"{0}|m:{1}".format(string, message)

        if self._telemetry:
            self.service_checks_count += 1
        self._send(string)

    def _add_constant_tags(self, tags):
        if self.constant_tags:
            if tags:
                return tags + self.constant_tags
            else:
                return self.constant_tags
        return tags


statsd = DogStatsd()
