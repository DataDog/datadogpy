# -*- coding: utf-8 -*-
# pylint: disable=line-too-long,too-many-public-methods

# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Tests for dogstatsd.py
"""
# Standard libraries
from collections import deque
from contextlib import closing, contextmanager
import logging
import struct
from threading import Thread
import errno
import os
import shutil
import socket
import tempfile
import threading
import time
import unittest
import warnings

# Third-party libraries
import mock
from mock import call, Mock, mock_open, patch
import pytest

# Datadog libraries
from datadog import initialize, statsd
from datadog import __version__ as version
from datadog.dogstatsd.base import DEFAULT_BUFFERING_FLUSH_INTERVAL, DEFAULT_HOST, DEFAULT_PORT, DogStatsd, MIN_SEND_BUFFER_SIZE, PENDING_PAYLOAD_EXPIRY_SECONDS, PendingPayload, SenderQueue, Stop, UDP_OPTIMAL_PAYLOAD_LENGTH, SENDER_RETRY_MAX_BACKOFF, UDS_OPTIMAL_PAYLOAD_LENGTH
from datadog.dogstatsd.sender_queue import is_replay_safe, payload_text
from datadog.util.compat import monotonic as sender_queue_clock
from datadog.dogstatsd.context import TimedContextManagerDecorator
from datadog.util.compat import is_higher_py35, is_p3k
from tests.util.contextmanagers import preserve_environment_variable, EnvVars
from tests.unit.dogstatsd.fixtures import load_fixtures


class FakeSocket(object):
    """ A fake socket for testing. """

    FLUSH_GRACE_PERIOD = 0.2

    def __init__(self, flush_interval=DEFAULT_BUFFERING_FLUSH_INTERVAL, socket_kind=socket.SOCK_DGRAM, socket_path=None):
        self.payloads = deque()

        self._flush_interval = flush_interval
        self._flush_wait = False
        self._socket_kind = socket_kind
        self.timeout = () # unit tuple = settimeout was not called

        if socket_path:
            self.family = socket.AF_UNIX
        else:
            self.family = socket.AF_INET

    def sendall(self, payload):
        self.send(payload)

    def send(self, payload):
        if is_p3k():
            assert isinstance(payload, bytes)
        else:
            assert isinstance(payload, str)

        self.payloads.append(payload)

    def recv(self, count=1, reset_wait=False, no_wait=False):
        # Initial receive should wait for the flush thread timeout unless we
        # specifically want either a follow-up wait or no waiting at all
        if not self._flush_wait or reset_wait:
            if not no_wait:
                time.sleep(self._flush_interval+self.FLUSH_GRACE_PERIOD)
            self._flush_wait = True

        payload_len = len(self.payloads)
        if self._socket_kind == socket.SOCK_STREAM:
            if payload_len % 2 != 0 or count > (payload_len / 2):
                return None
        elif count > len(self.payloads):
            return None

        out = []
        for _ in range(count):
            if self._socket_kind == socket.SOCK_DGRAM:
                out.append(self.payloads.popleft().decode('utf-8'))
            else:
                length = struct.unpack('<I', self.payloads.popleft())[0]
                pl = self.payloads.popleft()[:length].decode('utf-8')
                out.append(pl)
        return '\n'.join(out)

    def close(self):
        pass

    def getsockopt(self, *args):
        return self._socket_kind

    def __repr__(self):
        return str(self.payloads)

    def settimeout(self, timeout):
        self.timeout = timeout

class BrokenSocket(FakeSocket):
    def __init__(self, error_number=None):
        super(BrokenSocket, self).__init__()

        self.error_number = error_number

    def send(self, payload):
        error = socket.error("Socket error [Errno {}]".format(self.error_number))
        if self.error_number:
            error.errno = self.error_number

        raise error


class OverflownSocket(BrokenSocket):

    def __init__(self):
        super(OverflownSocket, self).__init__(errno.EAGAIN)


def telemetry_metrics(metrics=1, events=0, service_checks=0, bytes_sent=0, bytes_dropped_writer=0, packets_sent=1, packets_dropped_writer=0, transport="udp", tags="", bytes_dropped_queue=0, packets_dropped_queue=0, bytes_dropped_expired=0, packets_dropped_expired=0):
    tags = "," + tags if tags else ""

    # Expired drops have no dedicated wire metric: they're folded into the
    # *_dropped_queue lines (and totals) reported to the Agent. See
    # DogStatsd._flush_telemetry().
    reported_bytes_dropped_queue = bytes_dropped_queue + bytes_dropped_expired
    reported_packets_dropped_queue = packets_dropped_queue + packets_dropped_expired

    return "\n".join([
        "datadog.dogstatsd.client.metrics:{}|c|#client:py,client_version:{},client_transport:{}{}".format(metrics, version, transport, tags),
        "datadog.dogstatsd.client.events:{}|c|#client:py,client_version:{},client_transport:{}{}".format(events, version, transport, tags),
        "datadog.dogstatsd.client.service_checks:{}|c|#client:py,client_version:{},client_transport:{}{}".format(service_checks, version, transport, tags),
        "datadog.dogstatsd.client.bytes_sent:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_sent, version, transport, tags),
        "datadog.dogstatsd.client.bytes_dropped:{}|c|#client:py,client_version:{},client_transport:{}{}".format(reported_bytes_dropped_queue + bytes_dropped_writer, version, transport, tags),
        "datadog.dogstatsd.client.bytes_dropped_queue:{}|c|#client:py,client_version:{},client_transport:{}{}".format(reported_bytes_dropped_queue, version, transport, tags),
        "datadog.dogstatsd.client.bytes_dropped_writer:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_dropped_writer, version, transport, tags),
        "datadog.dogstatsd.client.packets_sent:{}|c|#client:py,client_version:{},client_transport:{}{}".format(packets_sent, version, transport, tags),
        "datadog.dogstatsd.client.packets_dropped:{}|c|#client:py,client_version:{},client_transport:{}{}".format(reported_packets_dropped_queue + packets_dropped_writer, version, transport, tags),
        "datadog.dogstatsd.client.packets_dropped_queue:{}|c|#client:py,client_version:{},client_transport:{}{}".format(reported_packets_dropped_queue, version, transport, tags),
        "datadog.dogstatsd.client.packets_dropped_writer:{}|c|#client:py,client_version:{},client_transport:{}{}".format(packets_dropped_writer, version, transport, tags),
    ]) + "\n"


class TestDogStatsd(unittest.TestCase):
    METRIC_TYPE_MAP = {
        'gauge': { 'id': 'g' },
        'timing': { 'id': 'ms' },
    }

    def setUp(self):
        """
        Set up a default Dogstatsd instance and mock the proc filesystem.
        """
        #
        self.statsd = DogStatsd(telemetry_min_flush_interval=0)
        self.statsd.socket = FakeSocket()
        self.statsd._reset_telemetry()

        # Mock the proc filesystem
        route_data = load_fixtures('route')
        self._procfs_mock = patch('datadog.util.compat.builtins.open', mock_open())
        self._procfs_mock.start().return_value.readlines.return_value = route_data.split("\n")

    def tearDown(self):
        """
        Unmock the proc filesystem.
        """
        self._procfs_mock.stop()

    @contextmanager
    def _capture_error_logs(self):
        # assertLogs() is Python 3.4+ only, but this suite still runs on
        # Python 2.7 / pypy2.7. Capture ERROR records on the dogstatsd logger
        # with a plain handler instead, so the guard tests work everywhere.
        captured = []

        class _CaptureHandler(logging.Handler):
            def emit(self, record):
                captured.append(record)

        dogstatsd_logger = logging.getLogger("datadog.dogstatsd")
        handler = _CaptureHandler(level=logging.ERROR)
        dogstatsd_logger.addHandler(handler)
        prev_level = dogstatsd_logger.level
        dogstatsd_logger.setLevel(min(prev_level, logging.ERROR))
        try:
            yield captured
        finally:
            dogstatsd_logger.removeHandler(handler)
            dogstatsd_logger.setLevel(prev_level)

    def assert_equal_telemetry(self, expected_payload, actual_payload, telemetry=None, **kwargs):
        if telemetry is None:
            telemetry = telemetry_metrics(bytes_sent=len(expected_payload), **kwargs)

        if expected_payload:
            expected_payload = "\n".join([expected_payload, telemetry])
        else:
            expected_payload = telemetry

        self.maxDiff = None
        return self.assertEqual(expected_payload, actual_payload)

    def send_and_assert(
        self,
        dogstatsd,
        expected_metrics,
        last_telemetry_size=0,
        buffered=False,
    ):
        """
        Send and then asserts that a chain of metrics arrive in the right order
        and with expected telemetry values.
        """

        expected_messages = []
        for metric_type, metric_name, metric_value in expected_metrics:
            # Construct the expected message data
            metric_type_id = TestDogStatsd.METRIC_TYPE_MAP[metric_type]['id']
            expected_messages.append(
                "{}:{}|{}\n".format(metric_name, metric_value, metric_type_id)
            )

            # Send the value
            getattr(dogstatsd, metric_type)(metric_name, metric_value)

        # Sanity check
        if buffered:
            # Ensure that packets didn't arrive immediately if we are expecting
            # buffering behavior
            self.assertIsNone(dogstatsd.socket.recv(2, no_wait=True))

        metrics = 1
        if buffered:
            metrics = len(expected_messages)

        if buffered:
            expected_messages = [ ''.join(expected_messages) ]

        for message in expected_messages:
            packets_sent = 1
            # For all ono-initial packets, our current telemetry stats will
            # contain the metadata for the last telemetry packet as well.
            if last_telemetry_size > 0:
                packets_sent += 1

            expected_metrics=telemetry_metrics(
                metrics=metrics,
                packets_sent=packets_sent,
                bytes_sent=len(message) + last_telemetry_size
            )
            self.assert_equal_telemetry(
                message,
                dogstatsd.socket.recv(2, no_wait=not buffered, reset_wait=True),
                telemetry=expected_metrics,
            )
            last_telemetry_size = len(expected_metrics)

        return last_telemetry_size

    def assert_almost_equal(self, val1, val2, delta):
        """
        Calculates a delta between first and second value and ensures
        that this difference falls within the delta range
        """
        return self.assertTrue(
            0 <= abs(val1 - val2) <= delta,
            "Absolute difference of {} and {} ({}) is not within {}".format(
                val1,
                val2,
                abs(val1-val2),
                delta,
            ),
        )

    def recv(self, *args, **kwargs):
        return self.statsd.socket.recv(*args, **kwargs)

    def test_initialization(self):
        """
        `initialize` overrides `statsd` default instance attributes.
        """
        options = {
            'statsd_host': "myhost",
            'statsd_port': 1234
        }

        # Default values
        self.assertEqual(statsd.host, "localhost")
        self.assertEqual(statsd.port, 8125)

        # After initialization
        initialize(**options)
        self.assertEqual(statsd.host, "myhost")
        self.assertEqual(statsd.port, 1234)

        # Add namespace
        options['statsd_namespace'] = "mynamespace"
        initialize(**options)
        self.assertEqual(statsd.host, "myhost")
        self.assertEqual(statsd.port, 1234)
        self.assertEqual(statsd.namespace, "mynamespace")

        # Set `statsd` host to the system's default route
        initialize(statsd_use_default_route=True, **options)
        self.assertEqual(statsd.host, "172.17.0.1")
        self.assertEqual(statsd.port, 1234)

        # Add UNIX socket
        options['statsd_socket_path'] = '/var/run/dogstatsd.sock'
        initialize(**options)
        self.assertEqual(statsd.socket_path, options['statsd_socket_path'])
        self.assertIsNone(statsd.host)
        self.assertIsNone(statsd.port)

        # Add cardinality
        options['cardinality'] = 'none'
        initialize(**options)
        self.assertEqual(statsd.cardinality, 'none')

    def test_initialization_udp_clears_socket_path(self):
        """
        Selecting a UDP destination via `initialize` clears a previously set
        socket_path (e.g. one inherited from DD_DOGSTATSD_URL=unix://...), so the
        manual host/port override is not silently ignored by get_socket().
        """
        original_socket_path = statsd.socket_path
        try:
            # Simulate a client that picked up a UDS from DD_DOGSTATSD_URL.
            initialize(statsd_socket_path='/var/run/datadog/dsd.socket')
            self.assertEqual(statsd.socket_path, '/var/run/datadog/dsd.socket')

            # A manual UDP override must win: socket_path cleared, host/port set.
            initialize(statsd_host='myhost', statsd_port=1234)
            self.assertIsNone(statsd.socket_path)
            self.assertEqual(statsd.host, 'myhost')
            self.assertEqual(statsd.port, 1234)

            # host-only override on a UDS-configured client backfills the default port
            # (the client had port=None), so the UDP socket is valid.
            initialize(statsd_socket_path='/var/run/datadog/dsd.socket')
            initialize(statsd_host='hostonly')
            self.assertIsNone(statsd.socket_path)
            self.assertEqual(statsd.host, 'hostonly')
            self.assertEqual(statsd.port, DEFAULT_PORT)

            # port-only override likewise backfills the default host
            initialize(statsd_socket_path='/var/run/datadog/dsd.socket')
            initialize(statsd_port=9999)
            self.assertIsNone(statsd.socket_path)
            self.assertEqual(statsd.host, DEFAULT_HOST)
            self.assertEqual(statsd.port, 9999)
        finally:
            statsd.socket_path = original_socket_path

    def test_dogstatsd_initialization_with_env_vars_agent_host(self):
        """
        Dogstatsd can retrieve its config from DD_AGENT_HOST / DD_DOGSTATSD_PORT
        env vars when not provided in the constructor.
        """
        with EnvVars(env_vars={'DD_AGENT_HOST': 'myenvvarhost', 'DD_DOGSTATSD_PORT': '4321'}):
            dogstatsd = DogStatsd()
        self.assertEqual(dogstatsd.host, "myenvvarhost")
        self.assertEqual(dogstatsd.port, 4321)

    def test_dogstatsd_initialization_with_env_vars_dogstatsd_url(self):
        """
        Dogstatsd can retrieve its config from the DD_DOGSTATSD_URL env var, but
        an explicit constructor argument always takes precedence over it.
        """
        # UDP url
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'udp://myenvvarhost:4321'}):
            dogstatsd = DogStatsd()
        self.assertEqual(dogstatsd.host, "myenvvarhost")
        self.assertEqual(dogstatsd.port, 4321)
        self.assertIsNone(dogstatsd.socket_path)

        # UDS url: the full url is stored as the socket path
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'unix:///hello/world.sock'}):
            dogstatsd = DogStatsd()
        self.assertEqual(dogstatsd.socket_path, 'unix:///hello/world.sock')
        self.assertIsNone(dogstatsd.host)
        self.assertIsNone(dogstatsd.port)

        # The unixstream:// and unixgram:// schemes are UDS too
        for uds_url in ('unixstream:///hello/world.sock', 'unixgram:///hello/world.sock'):
            with EnvVars(env_vars={'DD_DOGSTATSD_URL': uds_url}):
                dogstatsd = DogStatsd()
            self.assertEqual(dogstatsd.socket_path, uds_url)
            self.assertIsNone(dogstatsd.host)
            self.assertIsNone(dogstatsd.port)

        # Explicit host wins over the url
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'unix:///hello/world.sock'}):
            dogstatsd = DogStatsd(host="myhost")
        self.assertIsNone(dogstatsd.socket_path)
        self.assertEqual(dogstatsd.host, 'myhost')
        self.assertEqual(dogstatsd.port, DEFAULT_PORT)

        # Explicit port wins over the url
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'unix:///hello/world.sock'}):
            dogstatsd = DogStatsd(port=8240)
        self.assertIsNone(dogstatsd.socket_path)
        self.assertEqual(dogstatsd.host, DEFAULT_HOST)
        self.assertEqual(dogstatsd.port, 8240)

        # Explicit socket_path wins over the url
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'unix:///hello/world.sock'}):
            dogstatsd = DogStatsd(socket_path='/var/run/datadog/dsd.sock')
        self.assertEqual(dogstatsd.socket_path, '/var/run/datadog/dsd.sock')
        self.assertIsNone(dogstatsd.host)
        self.assertIsNone(dogstatsd.port)

        # An explicit default host is NOT clobbered by the url
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'udp://other:9999'}):
            dogstatsd = DogStatsd(host=DEFAULT_HOST)
        self.assertEqual(dogstatsd.host, DEFAULT_HOST)
        self.assertEqual(dogstatsd.port, DEFAULT_PORT)
        self.assertIsNone(dogstatsd.socket_path)

        # Unsupported scheme falls back to defaults without raising
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'http://myenvvarhost:4321'}):
            dogstatsd = DogStatsd()
        self.assertEqual(dogstatsd.host, DEFAULT_HOST)
        self.assertEqual(dogstatsd.port, DEFAULT_PORT)
        self.assertIsNone(dogstatsd.socket_path)

        # A UDP url without a port falls back to the default port
        with EnvVars(env_vars={'DD_DOGSTATSD_URL': 'udp://myenvvarhost'}):
            dogstatsd = DogStatsd()
        self.assertEqual(dogstatsd.host, "myenvvarhost")
        self.assertEqual(dogstatsd.port, DEFAULT_PORT)
        self.assertIsNone(dogstatsd.socket_path)

        # DD_DOGSTATSD_URL takes precedence over DD_AGENT_HOST / DD_DOGSTATSD_PORT
        with EnvVars(env_vars={
            'DD_DOGSTATSD_URL': 'udp://urlhost:1111',
            'DD_AGENT_HOST': 'legacyhost',
            'DD_DOGSTATSD_PORT': '2222',
        }):
            dogstatsd = DogStatsd()
        self.assertEqual(dogstatsd.host, "urlhost")
        self.assertEqual(dogstatsd.port, 1111)

    def test_initialization_closes_socket(self):
        statsd.socket = FakeSocket()
        self.assertIsNotNone(statsd.socket)
        initialize()
        self.assertIsNone(statsd.socket)

    def test_default_route(self):
        """
        Dogstatsd host can be dynamically set to the default route.
        """
        self.assertEqual(
            DogStatsd(use_default_route=True).host,
            "172.17.0.1"
        )

    def test_set(self):
        self.statsd.set('set', 123)
        self.assert_equal_telemetry('set:123|s\n', self.recv(2))

    def test_report(self):
        self.statsd._report('report', 'g', 123.4, tags=None, sample_rate=None)
        self.assert_equal_telemetry('report:123.4|g\n', self.recv(2))

    def test_report_metric_with_unsupported_ts(self):
        self.statsd._reset_telemetry()
        self.statsd._report('report', 'h', 123.5, tags=None, sample_rate=None, timestamp=100)
        self.assert_equal_telemetry('report:123.5|h\n', self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd._report('set', 's', 123, tags=None, sample_rate=None, timestamp=100)
        self.assert_equal_telemetry('set:123|s\n', self.recv(2))

    def test_report_with_cardinality(self):
        self.statsd._report('report', 'g', 123.4, tags=None, sample_rate=None, cardinality="orchestrator")
        self.assert_equal_telemetry('report:123.4|g|card:orchestrator\n', self.recv(2))

    def test_gauge(self):
        self.statsd.gauge('gauge', 123.4)
        self.assert_equal_telemetry('gauge:123.4|g\n', self.recv(2))

    def test_gauge_with_ts(self):
        self.statsd.gauge_with_timestamp("gauge", 123.4, timestamp=1066)
        self.assert_equal_telemetry("gauge:123.4|g|T1066\n", self.recv(2))

    def test_gauge_with_cardinality(self):
        self.statsd.gauge('gauge', 123.4, cardinality="high")
        self.assert_equal_telemetry('gauge:123.4|g|card:high\n', self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.gauge_with_timestamp("gauge", 123.4, timestamp=1066, cardinality="none")
        self.assert_equal_telemetry("gauge:123.4|g|card:none|T1066\n", self.recv(2))

    def test_gauge_with_invalid_ts_should_be_ignored(self):
        self.statsd.gauge_with_timestamp("gauge", 123.4, timestamp=-500)
        self.assert_equal_telemetry("gauge:123.4|g\n", self.recv(2))

    def test_counter(self):
        self.statsd.increment('page.views')
        self.statsd.flush()
        self.assert_equal_telemetry('page.views:1|c\n', self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.increment('page.views', 11)
        self.statsd.flush()
        self.assert_equal_telemetry('page.views:11|c\n', self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.decrement('page.views')
        self.statsd.flush()
        self.assert_equal_telemetry('page.views:-1|c\n', self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.decrement('page.views', 12)
        self.statsd.flush()
        self.assert_equal_telemetry('page.views:-12|c\n', self.recv(2))

    def test_count(self):
        self.statsd.count('page.views', 11)
        self.statsd.flush()
        self.assert_equal_telemetry('page.views:11|c\n', self.recv(2))

    def test_count_with_ts(self):
        self.statsd.count_with_timestamp("page.views", 1, timestamp=1066)
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:1|c|T1066\n", self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.count_with_timestamp("page.views", 11, timestamp=2121)
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:11|c|T2121\n", self.recv(2))

    def test_count_with_cardinality(self):
        self.statsd.count('page.views', 11, cardinality="low")
        self.statsd.flush()
        self.assert_equal_telemetry('page.views:11|c|card:low\n', self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.count_with_timestamp("page.views", 11, timestamp=2121, cardinality="high")
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:11|c|card:high|T2121\n", self.recv(2))

    def test_count_with_invalid_ts_should_be_ignored(self):
        self.statsd.count_with_timestamp("page.views", 1, timestamp=-1066)
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:1|c\n", self.recv(2))

    def test_histogram(self):
        self.statsd.histogram('histo', 123.4)
        self.assert_equal_telemetry('histo:123.4|h\n', self.recv(2))

    def test_histogram_with_cardinality(self):
        self.statsd.histogram('histo', 123.4, cardinality="low")
        self.assert_equal_telemetry('histo:123.4|h|card:low\n', self.recv(2))

    def test_sampled_metrics_with_cardinality_when_aggregation_enabled(self):
        statsd = DogStatsd(
            disable_aggregation=False,
            disable_telemetry=True,
            origin_detection_enabled=False,
            flush_interval=10000,
            max_metric_samples_per_context=10,
        )
        statsd.socket = FakeSocket()

        try:
            statsd.histogram("histo", 1, cardinality="high")
            statsd.distribution("dist", 2, cardinality="high")
            statsd.timing("timer", 3, cardinality="high")
            statsd.flush_aggregated_metrics()

            packets = [statsd.socket.recv(no_wait=True) for _ in range(3)]
            self.assertEqual(
                sorted(
                    [
                        "histo:1|h|card:high\n",
                        "dist:2|d|card:high\n",
                        "timer:3|ms|card:high\n",
                    ]
                ),
                sorted(packets),
            )
        finally:
            statsd.stop()

    def test_pipe_in_tags(self):
        self.statsd.gauge('gt', 123.4, tags=['pipe|in:tag', 'red'])
        self.assert_equal_telemetry('gt:123.4|g|#pipe_in:tag,red\n', self.recv(2))

    def test_tagged_gauge(self):
        self.statsd.gauge('gt', 123.4, tags=['country:china', 'age:45', 'blue'])
        self.assert_equal_telemetry('gt:123.4|g|#country:china,age:45,blue\n', self.recv(2))

    def test_tagged_counter(self):
        self.statsd.increment('ct', tags=[u'country:españa', 'red'])
        self.assert_equal_telemetry(u'ct:1|c|#country:españa,red\n', self.recv(2))

    def test_tagged_histogram(self):
        self.statsd.histogram('h', 1, tags=['red'])
        self.assert_equal_telemetry('h:1|h|#red\n', self.recv(2))

    def test_sample_rate(self):
        # Disabling telemetry since sample_rate imply randomness
        self.statsd._telemetry = False

        self.statsd.increment('c', sample_rate=0)
        self.assertFalse(self.recv())

        for _ in range(10000):
            self.statsd.increment('sampled_counter', sample_rate=0.3)

        self.statsd.flush()

        total_metrics = 0
        payload = self.recv()
        while payload:
            metrics = payload.rstrip('\n').split('\n')
            for metric in metrics:
                self.assertEqual('sampled_counter:1|c|@0.3', metric)
            total_metrics += len(metrics)
            payload = self.recv()

        self.assert_almost_equal(3000, total_metrics, 150)

    def test_default_sample_rate(self):
        # Disabling telemetry since sample_rate imply randomness
        self.statsd._telemetry = False

        self.statsd.default_sample_rate = 0.3
        for _ in range(10000):
            self.statsd.increment('sampled_counter')

        total_metrics = 0
        payload = self.recv()
        while payload:
            metrics = payload.rstrip('\n').split('\n')
            for metric in metrics:
                self.assertEqual('sampled_counter:1|c|@0.3', metric)

            total_metrics += len(metrics)
            payload = self.recv()

        self.assert_almost_equal(3000, total_metrics, 150)

    def test_tags_and_samples(self):
        # Disabling telemetry since sample_rate imply randomness
        self.statsd._telemetry = False

        for _ in range(100):
            self.statsd.gauge('gst', 23, tags=["sampled"], sample_rate=0.9)

        self.assertEqual('gst:23|g|@0.9|#sampled', self.recv().split('\n')[0])

    def test_timing(self):
        self.statsd.timing('t', 123)
        self.assert_equal_telemetry('t:123|ms\n', self.recv(2))

    def test_event(self):
        self.statsd.event(
            'Title',
            u'L1\nL2',
            priority='low',
            date_happened=1375296969,
            cardinality="orchestrator",
        )
        event2 = u'_e{5,6}:Title|L1\\nL2|d:1375296969|p:low|card:orchestrator\n'
        self.assert_equal_telemetry(
            event2,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                bytes_sent=len(event2),
            ),
        )

        self.statsd._reset_telemetry()

        self.statsd.event('Title', u'♬ †øU †øU ¥ºu T0µ ♪',
                          aggregation_key='key', tags=['t1', 't2:v2'])
        event3 = u'_e{5,32}:Title|♬ †øU †øU ¥ºu T0µ ♪|k:key|#t1,t2:v2\n'
        self.assert_equal_telemetry(
            event3,
            self.recv(2, reset_wait=True),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                bytes_sent=len(event3),
            ),
        )

    def test_unicode_event(self):
        self.statsd.event(
                'my.prefix.Delivery - Daily Settlement Summary Report Delivery — Invoice Cloud succeeded',
                'Delivered — destination.csv')
        event = u'_e{89,29}:my.prefix.Delivery - Daily Settlement Summary Report Delivery — Invoice Cloud succeeded|' + \
            u'Delivered — destination.csv\n'
        self.assert_equal_telemetry(
            event,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                bytes_sent=len(event),
            ),
        )

        self.statsd._reset_telemetry()

    # Positional arg names should match threadstats
    def test_event_matching_signature(self):
        self.statsd.event(title="foo", message="bar1")
        event = u'_e{3,4}:foo|bar1\n'
        self.assert_equal_telemetry(
            event,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                bytes_sent=len(event),
            ),
        )

        self.statsd._reset_telemetry()

    def test_event_constant_tags(self):
        self.statsd.constant_tags = ['bar:baz', 'foo']
        self.statsd.event('Title', u'L1\nL2', priority='low', date_happened=1375296969)
        event = u'_e{5,6}:Title|L1\\nL2|d:1375296969|p:low|#bar:baz,foo\n'
        self.assert_equal_telemetry(
            event,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                tags="bar:baz,foo",
                bytes_sent=len(event),
            ),
        )

        self.statsd._reset_telemetry()

        self.statsd.event('Title', u'♬ †øU †øU ¥ºu T0µ ♪',
                          aggregation_key='key', tags=['t1', 't2:v2'])
        event = u'_e{5,32}:Title|♬ †øU †øU ¥ºu T0µ ♪|k:key|#t1,t2:v2,bar:baz,foo\n'
        self.assert_equal_telemetry(
            event,
            self.recv(2, reset_wait=True),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                tags="bar:baz,foo",
                bytes_sent=len(event),
            ),
        )

    def test_event_payload_error(self):
        def func():
            # define an event payload that is > 8 * 1024
            message = ["l" for i in range(8 * 1024)]
            message = "".join(message)
            payload = {"title": "title", "message": message}

            self.statsd.event(**payload)

        # check that the method fails when the payload is too large
        with pytest.raises(ValueError):
            func()

        # check that the method does not fail with a small payload
        self.statsd.event("title", "message")

    def test_service_check(self):
        now = int(time.time())
        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            tags=['key1:val1', 'key2:val2'], timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪",
            cardinality="low",
        )
        check = u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#key1:val1,key2:val2|m:{2}|card:low\n'.format(self.statsd.WARNING, now, u'♬ †øU \\n†øU ¥ºu|m\\: T0µ ♪')
        self.assert_equal_telemetry(
            check,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=0,
                service_checks=1,
                bytes_sent=len(check),
            ),
        )

    def test_service_check_constant_tags(self):
        self.statsd.constant_tags = ['bar:baz', 'foo']
        now = int(time.time())
        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪")
        check = u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#bar:baz,foo|m:{2}'.format(self.statsd.WARNING, now, u"♬ †øU \\n†øU ¥ºu|m\\: T0µ ♪\n")
        self.assert_equal_telemetry(
            check,
            self.recv(2, True),
            telemetry=telemetry_metrics(
                metrics=0,
                service_checks=1,
                tags="bar:baz,foo",
                bytes_sent=len(check),
            ),
        )

        self.statsd._reset_telemetry()

        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            tags=['key1:val1', 'key2:val2'], timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪")
        check = u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#key1:val1,key2:val2,bar:baz,foo|m:{2}'.format(self.statsd.WARNING, now, u"♬ †øU \\n†øU ¥ºu|m\\: T0µ ♪\n")
        self.assert_equal_telemetry(
            check,
            self.recv(2, True),
            telemetry=telemetry_metrics(
                metrics=0,
                service_checks=1,
                tags="bar:baz,foo",
                bytes_sent=len(check),
            ),
        )

    def test_metric_namespace(self):
        """
        Namespace prefixes all metric names.
        """
        self.statsd.namespace = "foo"
        self.statsd.gauge('gauge', 123.4)
        self.assert_equal_telemetry('foo.gauge:123.4|g\n', self.recv(2))

    # Test Client level content tags
    def test_gauge_constant_tags(self):
        self.statsd.constant_tags = ['bar:baz', 'foo']
        self.statsd.gauge('gauge', 123.4)
        metric = 'gauge:123.4|g|#bar:baz,foo\n'
        self.assert_equal_telemetry(metric, self.recv(2), telemetry=telemetry_metrics(tags="bar:baz,foo", bytes_sent=len(metric)))

    def test_counter_constant_tag_with_metric_level_tags(self):
        self.statsd.constant_tags = ['bar:baz', 'foo']
        self.statsd.increment('page.views', tags=['extra'])
        metric = 'page.views:1|c|#extra,bar:baz,foo\n'
        self.assert_equal_telemetry(metric, self.recv(2), telemetry=telemetry_metrics(tags="bar:baz,foo", bytes_sent=len(metric)))

    def test_gauge_constant_tags_with_metric_level_tags_twice(self):
        metric_level_tag = ['foo:bar']
        self.statsd.constant_tags = ['bar:baz']
        self.statsd.gauge('gauge', 123.4, tags=metric_level_tag)
        metric = 'gauge:123.4|g|#foo:bar,bar:baz\n'
        self.assert_equal_telemetry(
            metric,
            self.recv(2),
            telemetry=telemetry_metrics(
                tags="bar:baz",
                bytes_sent=len(metric),
            ),
        )

        self.statsd._reset_telemetry()

        # sending metrics multiple times with same metric-level tags
        # should not duplicate the tags being sent
        self.statsd.gauge('gauge', 123.4, tags=metric_level_tag)
        metric = 'gauge:123.4|g|#foo:bar,bar:baz\n'
        self.assert_equal_telemetry(
            metric,
            self.recv(2, reset_wait=True),
            telemetry=telemetry_metrics(
                tags="bar:baz",
                bytes_sent=len(metric),
            ),
        )

    def test_constant_tags_cache_invalidated_on_mutation(self):
        dogstatsd = DogStatsd(telemetry_min_flush_interval=0, disable_telemetry=True)
        dogstatsd.socket = FakeSocket()

        dogstatsd.constant_tags = ['original:tag']
        dogstatsd.gauge('gauge', 1)
        dogstatsd.flush()
        self.assertEqual('gauge:1|g|#original:tag\n', dogstatsd.socket.recv())

        # append
        dogstatsd.constant_tags.append('new:tag')
        dogstatsd.gauge('gauge', 2)
        dogstatsd.flush()
        self.assertEqual('gauge:2|g|#original:tag,new:tag\n', dogstatsd.socket.recv())

        # sort
        dogstatsd.constant_tags.sort()
        dogstatsd.gauge('gauge', 3)
        dogstatsd.flush()
        self.assertEqual('gauge:3|g|#new:tag,original:tag\n', dogstatsd.socket.recv())

        # remove
        dogstatsd.constant_tags.remove('new:tag')
        dogstatsd.gauge('gauge', 4)
        dogstatsd.flush()
        self.assertEqual('gauge:4|g|#original:tag\n', dogstatsd.socket.recv())

        # __setitem__
        dogstatsd.constant_tags[0] = 'replaced:tag'
        dogstatsd.gauge('gauge', 5)
        dogstatsd.flush()
        self.assertEqual('gauge:5|g|#replaced:tag\n', dogstatsd.socket.recv())

        # extend
        dogstatsd.constant_tags.extend(['a:1', 'b:2'])
        dogstatsd.gauge('gauge', 6)
        dogstatsd.flush()
        self.assertEqual('gauge:6|g|#replaced:tag,a:1,b:2\n', dogstatsd.socket.recv())

        # pop
        dogstatsd.constant_tags.pop()
        dogstatsd.gauge('gauge', 7)
        dogstatsd.flush()
        self.assertEqual('gauge:7|g|#replaced:tag,a:1\n', dogstatsd.socket.recv())

        # clear
        dogstatsd.constant_tags.clear()
        dogstatsd.gauge('gauge', 8)
        dogstatsd.flush()
        self.assertEqual('gauge:8|g\n', dogstatsd.socket.recv())

    def test_socket_error(self):
        self.statsd.socket = BrokenSocket()
        with mock.patch("datadog.dogstatsd.base.log") as mock_log:
            self.statsd.gauge('no error', 1)
            self.statsd.flush()

            mock_log.error.assert_not_called()
            mock_log.warning.assert_called_once_with(
                "Error submitting packet: %s, dropping the packet and closing the socket",
                mock.ANY,
            )

    def _uds_statsd(self, socket_connect_retry=False):
        """
        A UDS-backed client whose current socket is already broken.

        The reconnect-and-retry path in _xmit_packet is deliberately scoped to
        UDS only, so these tests must not use the default UDP client.
        """
        statsd = DogStatsd(
            socket_path='/tmp/dogstatsd-test.sock',
            disable_telemetry=True,
            socket_connect_retry=socket_connect_retry,
        )
        statsd.socket = BrokenSocket(error_number=errno.ECONNREFUSED)
        return statsd

    @patch('datadog.dogstatsd.base.DogStatsd._get_uds_socket')
    def test_direct_send_never_retries_uds_even_with_socket_connect_retry_enabled(self, mock_get_uds_socket):
        # socket_connect_retry only affects the background sender: a direct/
        # synchronous send (background sender disabled, the default) has no
        # queue and no expiry to protect the calling thread, so it must always
        # fail fast on a connection error regardless of this setting.
        mock_get_uds_socket.return_value = FakeSocket()
        statsd = self._uds_statsd(socket_connect_retry=True)

        with mock.patch.object(statsd.socket, 'send', wraps=statsd.socket.send) as mock_send:
            with mock.patch("datadog.dogstatsd.base.log") as mock_log:
                statsd.gauge('not reconnected', 1)

                mock_log.error.assert_not_called()
                mock_log.warning.assert_called_once_with(
                    "Error submitting packet: %s, dropping the packet and closing the socket",
                    mock.ANY,
                )

            # A single send attempt on the broken socket, then dropped -- no
            # reconnect-and-resend, and no connect was ever attempted either.
            mock_send.assert_called_once()

        mock_get_uds_socket.assert_not_called()

    def test_socket_connection_error_does_not_retry_for_udp(self):
        # Reconnect-and-retry is UDS-only: a UDP client drops the packet on a
        # transient connection error even with socket_connect_retry enabled.
        self.statsd.socket_connect_retry = True
        broken_socket = BrokenSocket(error_number=errno.ECONNREFUSED)
        self.statsd.socket = broken_socket

        with mock.patch.object(broken_socket, 'send', wraps=broken_socket.send) as mock_send:
            with mock.patch("datadog.dogstatsd.base.log") as mock_log:
                self.statsd.gauge('not reconnected', 1)

                mock_log.error.assert_not_called()
                mock_log.warning.assert_called_once_with(
                    "Error submitting packet: %s, dropping the packet and closing the socket",
                    mock.ANY,
                )

            # No reconnect-and-resend: a single send attempt, then dropped.
            mock_send.assert_called_once()

    def test_socket_connect_retry_defaults_to_false(self):
        self.assertFalse(self.statsd.socket_connect_retry)

    def test_concurrent_reconnect_does_not_drop_backlog_after_recovery(self):
        # End-to-end ordering: thread A connects slowly while holding
        # _socket_lock (no socket installed yet); B queues right behind it on
        # the same lock. Once A installs a healthy socket, B must send on it
        # rather than also trying to connect -- get_socket() always prefers an
        # already-installed socket over connecting again. Direct sends never
        # retry now, so unlike the old version of this test, neither packet
        # can survive a *failed* connect; this exercises the still-relevant
        # part, concurrent first-time connects sharing one outcome.
        statsd = DogStatsd(
            socket_path='/tmp/dogstatsd-test-concurrent.sock',
            disable_telemetry=True,
        )
        working_socket = FakeSocket()

        a_is_connecting = threading.Event()
        release_connect = threading.Event()
        connect_calls = []

        def slow_connect(*args, **kwargs):
            connect_calls.append(1)
            a_is_connecting.set()
            release_connect.wait(5)
            return working_socket

        with mock.patch.object(DogStatsd, '_get_uds_socket', side_effect=slow_connect):
            thread_a = Thread(target=lambda: statsd.gauge('from-a', 1))
            thread_a.start()
            self.assertTrue(a_is_connecting.wait(5), "A never reached the connect")

            thread_b = Thread(target=lambda: statsd.gauge('from-b', 1))
            thread_b.start()

            # Give B a moment to reach and block on _socket_lock (held by A's
            # in-progress connect), then let A's connect succeed and install
            # the socket.
            time.sleep(0.2)
            release_connect.set()

            thread_a.join(5)
            thread_b.join(5)
            self.assertFalse(thread_a.is_alive())
            # B reused the socket A installed rather than connecting itself.
            self.assertEqual(connect_calls, [1])
            self.assertFalse(thread_b.is_alive())

        payloads = [payload.decode('utf-8') for payload in working_socket.payloads]
        self.assertTrue(any('from-a' in payload for payload in payloads), payloads)
        self.assertTrue(any('from-b' in payload for payload in payloads), payloads)

    def test_close_socket_waits_for_in_flight_send(self):
        # A concurrent close_socket() (e.g. triggered by another thread's failed
        # send) must not be able to close the fd out from under a send that's
        # already in flight - that races and can raise EBADF.
        send_started = threading.Event()
        release_send = threading.Event()

        class SlowSocket(FakeSocket):
            def send(self, payload):
                send_started.set()
                release_send.wait(2)

        self.statsd.socket = SlowSocket()

        sender_thread = Thread(target=lambda: self.statsd.gauge('foo', 1))
        sender_thread.start()
        self.assertTrue(send_started.wait(2), "send did not start in time")

        closer_thread = Thread(target=self.statsd.close_socket)
        closer_thread.start()
        # Give closer_thread a chance to call close_socket() and block on it.
        time.sleep(0.1)

        # The in-flight send still holds _socket_lock, so close_socket() must
        # still be waiting on it here rather than having already closed the socket.
        self.assertTrue(closer_thread.is_alive())

        release_send.set()
        sender_thread.join(2)
        closer_thread.join(2)
        self.assertFalse(closer_thread.is_alive())

    def test_socket_overflown(self):
        self.statsd.socket = OverflownSocket()
        with mock.patch("datadog.dogstatsd.base.log") as mock_log:
            self.statsd.gauge('no error', 1)
            self.statsd.flush()

            mock_log.error.assert_not_called()
            calls = [call("Socket send would block: %s, dropping the packet", mock.ANY)]
            mock_log.debug.assert_has_calls(calls * 2)

    def test_socket_message_too_long(self):
        self.statsd.socket = BrokenSocket(error_number=errno.EMSGSIZE)
        with mock.patch("datadog.dogstatsd.base.log") as mock_log:
            self.statsd.gauge('no error', 1)
            self.statsd.flush()

            mock_log.error.assert_not_called()
            calls = [
                call(
                    "Packet size too big (size: %d): %s, dropping the packet",
                    mock.ANY,
                    mock.ANY,
                ),
            ]
            mock_log.debug.assert_has_calls(calls * 2)

    def test_socket_no_buffer_space(self):
        self.statsd.socket = BrokenSocket(error_number=errno.ENOBUFS)
        with mock.patch("datadog.dogstatsd.base.log") as mock_log:
            self.statsd.gauge('no error', 1)
            self.statsd.flush()

            mock_log.error.assert_not_called()
            calls = [call("Socket buffer full: %s, dropping the packet", mock.ANY)]
            mock_log.debug.assert_has_calls(calls * 2)

    @patch('socket.socket')
    def test_uds_socket_ensures_min_receive_buffer(self, mock_socket_create):
        mock_socket = mock_socket_create.return_value
        mock_socket.setblocking.return_value = None
        mock_socket.connect.return_value = None
        mock_socket.getsockopt.return_value = MIN_SEND_BUFFER_SIZE / 2

        datadog = DogStatsd(socket_path="/fake/uds/socket/path")
        datadog.gauge('some value', 1)
        datadog.flush()

        # Sanity check
        mock_socket_create.assert_called_once_with(socket.AF_UNIX, socket.SOCK_DGRAM)

        mock_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET,
            socket.SO_SNDBUF,
            MIN_SEND_BUFFER_SIZE,
        )

    @patch('socket.socket')
    def test_uds_socket_missing_socket_fails_immediately_no_retry(self, mock_socket_create):
        # _get_uds_socket makes exactly one connect attempt now: retrying a
        # connect failure, if at all, is the caller's job (socket_connect_retry
        # for the background sender; never for a direct send).
        missing_socket_error = socket.error(errno.ENOENT, os.strerror(errno.ENOENT))
        mock_socket = mock_socket_create.return_value
        mock_socket.connect.side_effect = missing_socket_error
        mock_socket.getsockopt.return_value = MIN_SEND_BUFFER_SIZE

        with self.assertRaises(socket.error) as raised:
            DogStatsd._get_uds_socket("unixgram:///fake/uds/socket/path", 0.1)

        self.assertEqual(raised.exception.errno, errno.ENOENT)
        mock_socket_create.assert_called_once_with(socket.AF_UNIX, socket.SOCK_DGRAM)
        mock_socket.settimeout.assert_called_once_with(0.1)
        mock_socket.close.assert_called_once()

    @patch('socket.socket')
    def test_uds_socket_falls_back_to_the_other_kind_on_eprototype(self, mock_socket_create):
        # EPROTOTYPE means "wrong socket kind for this address", not a
        # transient failure: _get_uds_socket falls back to the other
        # candidate kind for it (still one connect attempt per kind), rather
        # than retrying the same kind or giving up.
        wrong_kind_socket = Mock()
        wrong_kind_socket.connect.side_effect = socket.error(errno.EPROTOTYPE, os.strerror(errno.EPROTOTYPE))
        wrong_kind_socket.getsockopt.return_value = MIN_SEND_BUFFER_SIZE
        right_kind_socket = Mock()
        right_kind_socket.connect.return_value = None
        right_kind_socket.getsockopt.return_value = MIN_SEND_BUFFER_SIZE
        mock_socket_create.side_effect = [wrong_kind_socket, right_kind_socket]

        sock = DogStatsd._get_uds_socket("/fake/uds/socket/path", 0.1)

        self.assertIs(sock, right_kind_socket)
        mock_socket_create.assert_has_calls([
            call(socket.AF_UNIX, socket.SOCK_DGRAM),
            call(socket.AF_UNIX, socket.SOCK_STREAM),
        ])
        wrong_kind_socket.close.assert_called_once()

    @patch('socket.socket')
    def test_udp_socket_ensures_min_receive_buffer(self, mock_socket_create):
        mock_socket = mock_socket_create.return_value
        mock_socket.setblocking.return_value = None
        mock_socket.connect.return_value = None
        mock_socket.getsockopt.return_value = MIN_SEND_BUFFER_SIZE / 2

        datadog = DogStatsd()
        datadog.gauge('some value', 1)
        datadog.flush()

        # Sanity check
        mock_socket_create.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

        mock_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET,
            socket.SO_SNDBUF,
            MIN_SEND_BUFFER_SIZE,
        )

    def test_socket_updates_telemetry(self):
        # Test UDP
        self.statsd.gauge("foo", 1)
        self.assert_equal_telemetry("foo:1|g\n", self.recv(2), transport="udp")
        
        # Test UDS
        self.statsd.socket = FakeSocket(socket_path="/fake/path")
        self.statsd._reset_telemetry()
        self.statsd.gauge("foo", 2)
        self.assert_equal_telemetry("foo:2|g\n", self.recv(2), transport="uds")

        # Test UDS stream
        self.statsd.socket = FakeSocket(socket_path="unixstream://fake/path", socket_kind=socket.SOCK_STREAM)
        self.statsd._reset_telemetry()
        self.statsd.gauge("foo", 2)
        self.assert_equal_telemetry("foo:2|g\n", self.recv(2), transport="uds-stream")

    def test_distributed(self):
        """
        Measure the distribution of a function's run time using distribution custom metric.
        """
        # In seconds
        @self.statsd.distributed('distributed.test')
        def func(arg1, arg2, kwarg1=1, kwarg2=1):
            """docstring"""
            time.sleep(0.1)
            return (arg1, arg2, kwarg1, kwarg2)

        self.assertEqual('func', func.__name__)
        self.assertEqual('docstring', func.__doc__)

        result = func(1, 2, kwarg2=3)
        # Assert it handles args and kwargs correctly.
        self.assertEqual(result, (1, 2, 1, 3))

        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('d', type_)
        self.assertEqual('distributed.test', name)
        self.assert_almost_equal(0.1, float(value), 0.09)

        # Repeat, force timer value in milliseconds
        @self.statsd.distributed('distributed.test', use_ms=True)
        def func(arg1, arg2, kwarg1=1, kwarg2=1):
            """docstring"""
            time.sleep(0.5)
            return (arg1, arg2, kwarg1, kwarg2)

        func(1, 2, kwarg2=3)

        # Ignore telemetry packet
        packet = self.recv(2, reset_wait=True).split("\n")[0]
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('d', type_)
        self.assertEqual('distributed.test', name)
        self.assert_almost_equal(500, float(value), 100)
        
    def test_timed(self):
        """
        Measure the distribution of a function's run time.
        """
        # In seconds
        @self.statsd.timed('timed.test')
        def func(arg1, arg2, kwarg1=1, kwarg2=1):
            """docstring"""
            time.sleep(0.5)
            return (arg1, arg2, kwarg1, kwarg2)

        self.assertEqual('func', func.__name__)
        self.assertEqual('docstring', func.__doc__)

        result = func(1, 2, kwarg2=3)
        # Assert it handles args and kwargs correctly.
        self.assertEqual(result, (1, 2, 1, 3))

        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

        # Repeat, force timer value in milliseconds
        @self.statsd.timed('timed.test', use_ms=True)
        def func(arg1, arg2, kwarg1=1, kwarg2=1):
            """docstring"""
            time.sleep(0.5)
            return (arg1, arg2, kwarg1, kwarg2)

        func(1, 2, kwarg2=3)
        self.statsd.flush()

        # Ignore telemetry packet
        packet = self.recv(2).split("\n")[0]
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed.test', name)
        self.assert_almost_equal(500, float(value), 100)

    def test_timed_in_ms(self):
        """
        Timed value is reported in ms when statsd.use_ms is True.
        """
        # Arm statsd to use_ms
        self.statsd.use_ms = True

        # Sample a function run time
        @self.statsd.timed('timed.test')
        def func(arg1, arg2, kwarg1=1, kwarg2=1):
            """docstring"""
            time.sleep(0.5)
            return (arg1, arg2, kwarg1, kwarg2)

        func(1, 2, kwarg2=3)

        # Assess the packet
        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed.test', name)
        self.assert_almost_equal(500, float(value), 100)

        # Repeat, force timer value in seconds
        @self.statsd.timed('timed.test', use_ms=False)
        def func(arg1, arg2, kwarg1=1, kwarg2=1):
            """docstring"""
            time.sleep(0.5)
            return (arg1, arg2, kwarg1, kwarg2)

        func(1, 2, kwarg2=3)
        self.statsd.flush()

        packet = self.recv()
        name_value, type_ = packet.rstrip('\n').split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_no_metric(self, ):
        """
        Test using a decorator without providing a metric.
        """

        @self.statsd.timed()
        def func(arg1, arg2, kwarg1=1, kwarg2=1):
            """docstring"""
            time.sleep(0.5)
            return (arg1, arg2, kwarg1, kwarg2)

        self.assertEqual('func', func.__name__)
        self.assertEqual('docstring', func.__doc__)

        result = func(1, 2, kwarg2=3)
        # Assert it handles args and kwargs correctly.
        self.assertEqual(result, (1, 2, 1, 3))

        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('tests.unit.dogstatsd.test_statsd.func', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    @unittest.skipIf(not is_higher_py35(), reason="Coroutines are supported on Python 3.5 or higher.")
    def test_timed_coroutine(self):
        """
        Measure the distribution of a coroutine function's run time.

        Warning: Python > 3.5 only.
        """
        import asyncio

        source = """
@self.statsd.timed('timed.test')
async def print_foo():
    "docstring"
    import time
    time.sleep(0.5)
    print("foo")
        """
        ns = locals()
        exec(source, {}, ns)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(ns['print_foo']())
        finally:
            loop.close()

        # Assert
        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_context(self):
        """
        Measure the distribution of a context's run time.
        """
        # In seconds
        with self.statsd.timed('timed_context.test') as timer:
            self.assertTrue(isinstance(timer, TimedContextManagerDecorator))
            time.sleep(0.5)

        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed_context.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)
        self.assert_almost_equal(0.5, timer.elapsed, 0.1)

        # In milliseconds
        with self.statsd.timed('timed_context.test', use_ms=True) as timer:
            time.sleep(0.5)

        packet = self.recv(2, reset_wait=True).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed_context.test', name)
        self.assert_almost_equal(500, float(value), 100)
        self.assert_almost_equal(500, timer.elapsed, 100)

    def test_timed_context_exception(self):
        """
        Exception bubbles out of the `timed` context manager.
        """
        class ContextException(Exception):
            pass

        def func(self):
            with self.statsd.timed('timed_context.test.exception'):
                time.sleep(0.5)
                raise ContextException()

        # Ensure the exception was raised.
        with pytest.raises(ContextException):
            func(self)

        # Ensure the timing was recorded.
        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed_context.test.exception', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_context_no_metric_exception(self):
        """Test that an exception occurs if using a context manager without a metric."""

        def func(self):
            with self.statsd.timed():
                time.sleep(0.5)

        # Ensure the exception was raised.
        with pytest.raises(TypeError):
            func(self)

        # Ensure the timing was recorded.
        packet = self.statsd.socket.recv()
        self.assertIsNone(packet)

    def test_timed_start_stop_calls(self):
        # In seconds
        timer = self.statsd.timed('timed_context.test')
        timer.start()
        time.sleep(0.5)
        timer.stop()

        packet = self.recv(2).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed_context.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

        # In milliseconds
        timer = self.statsd.timed('timed_context.test', use_ms=True)
        timer.start()
        time.sleep(0.5)
        timer.stop()

        packet = self.recv(2, reset_wait=True).split("\n")[0] # ignore telemetry packet
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        self.assertEqual('ms', type_)
        self.assertEqual('timed_context.test', name)
        self.assert_almost_equal(500, float(value), 100)

    def test_batching(self):
        self.statsd.open_buffer()
        self.statsd.gauge('page.views', 123)
        self.statsd.timing('timer', 123)
        self.statsd.close_buffer()
        expected = 'page.views:123|g\ntimer:123|ms\n'
        self.assert_equal_telemetry(
                expected,
                self.recv(2),
                telemetry=telemetry_metrics(metrics=2, bytes_sent=len(expected))
        )

    def test_flush_dgram(self):
        self._test_flush(socket.SOCK_DGRAM)

    def test_flush_stream(self):
        self._test_flush(socket.SOCK_STREAM)

    def _test_flush(self, socket_kind):
        dogstatsd = DogStatsd(disable_buffering=False, telemetry_min_flush_interval=0)
        fake_socket = FakeSocket(socket_kind=socket_kind)
        dogstatsd.socket = fake_socket

        dogstatsd.increment(u'page.®views®')
        self.assertIsNone(fake_socket.recv(no_wait=True))
        dogstatsd.flush()
        self.assert_equal_telemetry(u'page.®views®:1|c\n', fake_socket.recv(2))

    def test_flush_interval_dgram(self):
        self._test_flush_interval(socket.SOCK_DGRAM)

    def test_flush_interval_stream(self):
        self._test_flush_interval(socket.SOCK_STREAM)

    def _test_flush_interval(self, socket_kind):
        dogstatsd = DogStatsd(disable_buffering=False, flush_interval=1, telemetry_min_flush_interval=0)
        fake_socket = FakeSocket(socket_kind=socket_kind)
        dogstatsd.socket = fake_socket

        dogstatsd.increment(u'page.®views®')
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(0.3)
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(1)
        self.assert_equal_telemetry(
            u'page.®views®:1|c\n',
            fake_socket.recv(2, no_wait=True)
        )
    
    def test_aggregation_buffering_simultaneously_dgram(self):
        self._test_aggregation_buffering_simultaneously(socket.SOCK_DGRAM)

    def test_aggregation_buffering_simultaneously_stream(self):
        self._test_aggregation_buffering_simultaneously(socket.SOCK_STREAM)

    def _test_aggregation_buffering_simultaneously(self, socket_kind):
        dogstatsd = DogStatsd(disable_buffering=False, disable_aggregation=False, telemetry_min_flush_interval=0)
        fake_socket = FakeSocket(socket_kind=socket_kind)
        dogstatsd.socket = fake_socket
        for _ in range(10):
            dogstatsd.increment(u'test.ÀggregÀtion_and_buffering')
        self.assertIsNone(fake_socket.recv(no_wait=True))
        dogstatsd.flush_aggregated_metrics()
        dogstatsd.flush()
        self.assert_equal_telemetry(u'test.ÀggregÀtion_and_buffering:10|c\n', fake_socket.recv(2))

    def test_aggregation_buffering_simultaneously_with_interval_dgram(self):
        self._test_aggregation_buffering_simultaneously_with_interval(socket.SOCK_DGRAM)

    def test_aggregation_buffering_simultaneously_with_interval_stream(self):
        self._test_aggregation_buffering_simultaneously_with_interval(socket.SOCK_STREAM)
    
    def _test_aggregation_buffering_simultaneously_with_interval(self, socket_kind):
        dogstatsd = DogStatsd(disable_buffering=False, disable_aggregation=False, flush_interval=1, telemetry_min_flush_interval=0)
        fake_socket = FakeSocket(socket_kind=socket_kind)
        dogstatsd.socket = fake_socket
        for _ in range(10):
            dogstatsd.increment('test.aggregation_and_buffering_with_interval')
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(0.3)
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(1)
        self.assert_equal_telemetry(
            'test.aggregation_and_buffering_with_interval:10|c\n',
            fake_socket.recv(2, no_wait=True)
        )

    def test_disable_buffering(self):
        dogstatsd = DogStatsd(disable_buffering=True, telemetry_min_flush_interval=0)
        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket

        dogstatsd.increment('page.views')
        self.assert_equal_telemetry(
            'page.views:1|c\n',
            fake_socket.recv(2, no_wait=True)
        )

    def test_flush_disable(self):
        dogstatsd = DogStatsd(
            disable_buffering=False,
            flush_interval=0,
            telemetry_min_flush_interval=0
        )
        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket

        dogstatsd.increment('page.views')
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(DEFAULT_BUFFERING_FLUSH_INTERVAL)
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(0.3)
        self.assertIsNone(fake_socket.recv(no_wait=True))

    @unittest.skip("Buffering has been disabled again so the deprecation is not valid")
    @patch("warnings.warn")
    def test_manual_buffer_ops_deprecation(self, mock_warn):
        self.assertFalse(mock_warn.called)

        self.statsd.open_buffer()
        self.assertTrue(mock_warn.called)
        self.assertEqual(mock_warn.call_count, 1)

        self.statsd.close_buffer()
        self.assertEqual(mock_warn.call_count, 2)

    def test_mixed_batch_splits_by_replay_safety(self):
        # A queued packet expires as a single unit, so every line in it has to
        # share one expiry policy. Batching timestamped lines together with
        # plain ones would make the whole packet non-replay-safe and strip the
        # timestamped lines of the staleness exemption they're supposed to
        # have, dropping them with the batch after ~10s of backlog. The buffer
        # must split by policy instead.
        sent = []
        self.statsd._send_to_server = lambda packet, replay_safe=False: sent.append((packet, replay_safe))

        self.statsd.open_buffer()
        self.statsd.gauge_with_timestamp("ts.one", 1, timestamp=1700000000)
        self.statsd.gauge("plain.one", 2)
        self.statsd.gauge_with_timestamp("ts.two", 3, timestamp=1700000001)
        self.statsd.gauge("plain.two", 4)
        self.statsd.close_buffer()

        # One packet per expiry policy, not one per metric: interleaving must
        # not defeat batching.
        self.assertEqual(len(sent), 2, "expected exactly one packet per expiry policy, got: {!r}".format(sent))

        by_policy = dict((replay_safe, packet) for packet, replay_safe in sent)
        self.assertEqual(sorted(by_policy.keys()), [False, True])

        # Assert on structure rather than exact packet text: constant/origin
        # tags vary by environment, but which lines land in which packet, and
        # in what order, does not.
        def names(packet):
            return [line.split(":")[0] for line in packet.split("\n")]

        self.assertEqual(names(by_policy[True]), ["ts.one", "ts.two"])
        self.assertEqual(names(by_policy[False]), ["plain.one", "plain.two"])

        # The invariant that actually matters: no packet mixes the two, and no
        # timestamped line ever rides in an expiring packet.
        for packet, replay_safe in sent:
            lines = packet.split("\n")
            timestamped = [line for line in lines if "|T" in line]
            if replay_safe:
                self.assertEqual(timestamped, lines, "replay-safe packet must be entirely timestamped lines")
            else:
                self.assertEqual(timestamped, [], "timestamped line leaked into an expiring packet")

    def test_mixed_batch_respects_max_payload_size_per_buffer(self):
        # Each buffer has to stay under _max_payload_size on its own, and one
        # buffer overflowing must not drag the other one out with it.
        sent = []
        self.statsd._send_to_server = lambda packet, replay_safe=False: sent.append((packet, replay_safe))

        # Measure a real serialised line and size the cap from it. Hard-coding
        # a byte count would make the test depend on how long constant/origin
        # tags happen to make each line in this environment: too small and a
        # single line breaches the cap, too large and nothing ever overflows.
        self.statsd.open_buffer()
        self.statsd.gauge("plain.filler.0", 0)
        line_size = self.statsd._buffer_size
        self.statsd.close_buffer()
        del sent[:]

        # Room for two lines, so every third one forces a flush.
        self.statsd._max_payload_size = line_size * 2 + 1

        self.statsd.open_buffer()
        # One small replay-safe line that should still be buffered while the
        # plain buffer churns through several flushes.
        self.statsd.gauge_with_timestamp("ts.keep", 1, timestamp=1700000000)
        for i in range(12):
            self.statsd.gauge("plain.filler.{}".format(i), i)
        flushes_before_close = len(sent)
        self.statsd.close_buffer()

        self.assertGreater(flushes_before_close, 0, "the plain buffer should have overflowed at least once")
        self.assertTrue(
            all(not replay_safe for _, replay_safe in sent[:flushes_before_close]),
            "overflow of the plain buffer must not flush the replay-safe buffer",
        )
        for packet, _ in sent:
            self.assertLessEqual(len(packet) + 1, self.statsd._max_payload_size)

        # The replay-safe line survived to the final flush, intact and alone.
        final_packet, final_replay_safe = sent[-1]
        self.assertTrue(final_replay_safe)
        self.assertEqual([line.split(":")[0] for line in final_packet.split("\n")], ["ts.keep"])
        self.assertIn("|T1700000000", final_packet)

    def test_batching_sequential(self):
        self.statsd.open_buffer()
        self.statsd.gauge('discarded.data', 123)
        self.statsd.close_buffer()

        self.statsd.open_buffer()
        self.statsd.gauge('page.views', 123)
        self.statsd.timing('timer', 123)
        self.statsd.close_buffer()

        expected1 = 'discarded.data:123|g\n'
        expected_metrics1=telemetry_metrics(metrics=1, bytes_sent=len(expected1))
        self.assert_equal_telemetry(
            expected1,
            self.recv(2),
            telemetry=expected_metrics1)

        expected2 = 'page.views:123|g\ntimer:123|ms\n'
        self.assert_equal_telemetry(
            expected2,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=2,
                packets_sent=2,
                bytes_sent=len(expected2 + expected_metrics1)
            )
        )

    def test_batching_runtime_changes_dgram(self):
        self._test_batching_runtime_changes(socket.SOCK_DGRAM)

    def test_batching_runtime_changes_stream(self):
        self._test_batching_runtime_changes(socket.SOCK_STREAM)

    def _test_batching_runtime_changes(self, socket_kind):
        dogstatsd = DogStatsd(
            disable_buffering=True,
            telemetry_min_flush_interval=0
        )
        dogstatsd.socket = FakeSocket(socket_kind=socket_kind)

        # Send some unbuffered metrics and verify we got it immediately
        last_telemetry_size = self.send_and_assert(
            dogstatsd,
            [
                ('gauge', 'rt.gauge', 123),
                ('timing', 'rt.timer', 123),
            ],
        )

        # Disable buffering (noop expected) and validate
        dogstatsd.disable_buffering = True
        last_telemetry_size = self.send_and_assert(
            dogstatsd,
            [
                ('gauge', 'rt.gauge2', 321),
                ('timing', 'rt.timer2', 321),
            ],
            last_telemetry_size = last_telemetry_size,
        )

        # Enable buffering and validate
        dogstatsd.disable_buffering = False
        last_telemetry_size = self.send_and_assert(
            dogstatsd,
            [
                ('gauge', 'buffered.gauge', 12345),
                ('timing', 'buffered.timer', 12345),
            ],
            last_telemetry_size = last_telemetry_size,
            buffered=True,
        )

        # Enable buffering again (another noop change expected)
        dogstatsd.disable_buffering = False
        last_telemetry_size = self.send_and_assert(
            dogstatsd,
            [
                ('gauge', 'buffered.gauge2', 321),
                ('timing', 'buffered.timer2', 321),
            ],
            last_telemetry_size = last_telemetry_size,
            buffered=True,
        )

        # Flip the toggle to unbuffered functionality one more time and verify
        dogstatsd.disable_buffering = True
        last_telemetry_size = self.send_and_assert(
            dogstatsd,
            [
                ('gauge', 'rt.gauge3', 333),
                ('timing', 'rt.timer3', 333),
            ],
            last_telemetry_size = last_telemetry_size,
        )

    def test_threaded_batching(self):
        num_threads = 4
        threads = []

        dogstatsd = DogStatsd(telemetry_min_flush_interval=0)
        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket

        def batch_metrics(index, dsd):
            time.sleep(0.3 * index)

            dsd.open_buffer()

            time.sleep(0.1)
            dsd.gauge('page.%d.views' % index, 123)

            time.sleep(0.1)
            dsd.timing('timer.%d' % index, 123)

            time.sleep(0.5)
            dsd.close_buffer()

        for idx in range(num_threads):
            thread = Thread(
                name="{}_sender_thread_{}".format(self.__class__.__name__, idx),
                target=batch_metrics,
                args=(idx, dogstatsd)
            )
            thread.daemon = True

            threads.append(thread)

        for thread in threads:
            thread.start()

        time.sleep(5)

        for thread in threads:
            if thread.is_alive():
                thread.join(0.1)

        previous_telemetry_packet_size = 0
        thread_idx = 0

        while thread_idx < num_threads:
            first_message = "page.{}.views:123|g\n".format(thread_idx)
            first_message_len = len(first_message)
            second_message = "timer.{}:123|ms\n".format(thread_idx)
            second_message_len = len(second_message)

            received_payload = fake_socket.recv(1)

            # Base assumption is that we got both messages but
            # we may get metrics split depending on when the flush thread triggers
            if received_payload == first_message:
                message = first_message
                packet_size = first_message_len
                num_metrics = 1
            elif received_payload == second_message:
                message = second_message
                packet_size = second_message_len
                num_metrics = 1
                thread_idx += 1
            else:
                message = first_message + second_message
                packet_size = len(message)
                num_metrics = 2
                thread_idx += 1

            self.assertEqual(received_payload, message)

            packet_sent = 2
            if previous_telemetry_packet_size == 0:
                packet_sent = 1

            bytes_sent = previous_telemetry_packet_size + packet_size
            telemetry = telemetry_metrics(
                    metrics=num_metrics,
                    bytes_sent=bytes_sent,
                    packets_sent=packet_sent,
            )
            self.assertEqual(telemetry, fake_socket.recv(1))

            previous_telemetry_packet_size = len(telemetry)

    def test_telemetry(self):
        self.statsd.metrics_count = 1
        self.statsd.events_count = 2
        self.statsd.service_checks_count = 3
        self.statsd.bytes_sent = 4
        self.statsd.bytes_dropped_writer = 5
        self.statsd.packets_sent = 6
        self.statsd.packets_dropped_writer = 7
        self.statsd.bytes_dropped_queue = 8
        self.statsd.packets_dropped_queue = 9

        self.statsd.open_buffer()
        self.statsd.gauge('page.views', 123)
        self.statsd.close_buffer()

        payload = 'page.views:123|g\n'
        telemetry = telemetry_metrics(metrics=2, events=2, service_checks=3, bytes_sent=4 + len(payload),
                                      bytes_dropped_writer=5, packets_sent=7, packets_dropped_writer=7, bytes_dropped_queue=8, packets_dropped_queue=9)

        self.assert_equal_telemetry(payload, self.recv(2), telemetry=telemetry)

        self.assertEqual(0, self.statsd.metrics_count)
        self.assertEqual(0, self.statsd.events_count)
        self.assertEqual(0, self.statsd.service_checks_count)
        self.assertEqual(len(telemetry), self.statsd.bytes_sent)
        self.assertEqual(0, self.statsd.bytes_dropped_writer)
        self.assertEqual(1, self.statsd.packets_sent)
        self.assertEqual(0, self.statsd.packets_dropped_writer)
        self.assertEqual(0, self.statsd.bytes_dropped_queue)
        self.assertEqual(0, self.statsd.packets_dropped_queue)

    def test_telemetry_folds_expired_drops_into_dropped_queue(self):
        # There's no dedicated wire metric for expired drops: they're
        # reported to the Agent as part of *_dropped_queue (and the combined
        # *_dropped total), alongside capacity-based queue drops, since both
        # never reach a socket write attempt. The distinction is still
        # available in-process via bytes_dropped_expired/packets_dropped_expired.
        # Avoid any real container-id auto-detected from the host/sandbox
        # cgroup leaking into the expected payload below -- this test is
        # about the telemetry counters, not the container-id field.
        self.statsd._container_id = None

        self.statsd.bytes_dropped_queue = 8
        self.statsd.packets_dropped_queue = 9
        self.statsd.bytes_dropped_expired = 10
        self.statsd.packets_dropped_expired = 11
        self.statsd.bytes_dropped_writer = 5
        self.statsd.packets_dropped_writer = 7

        self.statsd.open_buffer()
        self.statsd.gauge('page.views', 123)
        self.statsd.close_buffer()

        payload = 'page.views:123|g\n'
        telemetry = telemetry_metrics(
            metrics=1,
            bytes_sent=len(payload),
            packets_sent=1,
            bytes_dropped_queue=8,
            packets_dropped_queue=9,
            bytes_dropped_expired=10,
            packets_dropped_expired=11,
            bytes_dropped_writer=5,
            packets_dropped_writer=7,
        )

        self.assert_equal_telemetry(payload, self.recv(2), telemetry=telemetry)

        # The in-process counters stay separate even after the flush resets
        # them -- confirming the fold happens only in the wire output, not
        # by merging the underlying attributes.
        self.assertEqual(0, self.statsd.bytes_dropped_queue)
        self.assertEqual(0, self.statsd.packets_dropped_queue)
        self.assertEqual(0, self.statsd.bytes_dropped_expired)
        self.assertEqual(0, self.statsd.packets_dropped_expired)

    def test_telemetry_flush_interval(self):
        dogstatsd = DogStatsd(disable_buffering=False)
        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket

        # Set the last flush time in the future to be sure we won't flush
        dogstatsd._last_flush_time = time.time() + dogstatsd._telemetry_flush_interval
        dogstatsd.gauge('gauge', 123.4)

        metric = 'gauge:123.4|g\n'
        self.assertEqual(metric, fake_socket.recv())

        time1 = time.time()
        # Setting the last flush time in the past to trigger a telemetry flush
        dogstatsd._last_flush_time = time1 - dogstatsd._telemetry_flush_interval -1
        dogstatsd.gauge('gauge', 123.4)
        self.assert_equal_telemetry(
            metric,
            fake_socket.recv(2, reset_wait=True),
            telemetry=telemetry_metrics(
                metrics=2,
                bytes_sent=2*len(metric),
                packets_sent=2,
            ),
        )

        # assert that _last_flush_time has been updated
        self.assertTrue(time1 < dogstatsd._last_flush_time)

    def test_telemetry_flush_interval_alternate_destination(self):
        dogstatsd = DogStatsd(telemetry_host='foo')
        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket
        fake_telemetry_socket = FakeSocket()
        dogstatsd.telemetry_socket = fake_telemetry_socket

        self.assertIsNotNone(dogstatsd.telemetry_host)
        self.assertIsNotNone(dogstatsd.telemetry_port)
        self.assertTrue(dogstatsd._dedicated_telemetry_destination())

        # set the last flush time in the future to be sure we won't flush
        dogstatsd._last_flush_time = time.time() + dogstatsd._telemetry_flush_interval
        dogstatsd.gauge('gauge', 123.4)

        self.assertEqual('gauge:123.4|g\n', fake_socket.recv())

        time1 = time.time()
        # setting the last flush time in the past to trigger a telemetry flush
        dogstatsd._last_flush_time = time1 - dogstatsd._telemetry_flush_interval - 1
        dogstatsd.gauge('gauge', 123.4)

        self.assertEqual('gauge:123.4|g\n', fake_socket.recv(reset_wait=True))
        self.assert_equal_telemetry(
            '',
            fake_telemetry_socket.recv(),
            telemetry=telemetry_metrics(
                metrics=2,
                bytes_sent=14*2,
                packets_sent=2,
            ),
        )

        # assert that _last_flush_time has been updated
        self.assertTrue(time1 < dogstatsd._last_flush_time)

    def test_telemetry_flush_interval_batch(self):
        dogstatsd = DogStatsd(disable_buffering=False)

        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket

        dogstatsd.open_buffer()
        dogstatsd.gauge('gauge1', 1)
        dogstatsd.gauge('gauge2', 2)

        time1 = time.time()
        # setting the last flush time in the past to trigger a telemetry flush
        dogstatsd._last_flush_time = time1 - statsd._telemetry_flush_interval -1
        dogstatsd.close_buffer()

        metric = 'gauge1:1|g\ngauge2:2|g\n'
        self.assert_equal_telemetry(metric, fake_socket.recv(2), telemetry=telemetry_metrics(metrics=2, bytes_sent=len(metric)))
        # assert that _last_flush_time has been updated
        self.assertTrue(time1 < dogstatsd._last_flush_time)

    def test_dedicated_udp_telemetry_dest(self):
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener_sock.bind(('localhost', 0))

        def wait_for_data():
            global udp_thread_telemetry_data
            udp_thread_telemetry_data = listener_sock.recvfrom(UDP_OPTIMAL_PAYLOAD_LENGTH)[0].decode('utf-8')

        with closing(listener_sock):
            port = listener_sock.getsockname()[1]

            dogstatsd = DogStatsd(
                host="localhost",
                port=12345,
                telemetry_min_flush_interval=0,
                telemetry_host="localhost",
                telemetry_port=port,
            )

            server = threading.Thread(target=wait_for_data)
            server.start()

            dogstatsd.increment('abc')

            server.join(3)

            expected_telemetry = telemetry_metrics(metrics=1, packets_sent=1, bytes_sent=8)
            self.assertEqual(udp_thread_telemetry_data, expected_telemetry)

    def test_dedicated_udp6_telemetry_dest(self):
        listener_sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        listener_sock.bind(('localhost', 0))

        def wait_for_data():
            global udp_thread_telemetry_data
            udp_thread_telemetry_data = listener_sock.recvfrom(UDP_OPTIMAL_PAYLOAD_LENGTH)[0].decode('utf-8')

        with closing(listener_sock):
            port = listener_sock.getsockname()[1]

            dogstatsd = DogStatsd(
                host="localhost",
                port=12345,
                telemetry_min_flush_interval=0,
                telemetry_host="::1", # use explicit address, localhost may resolve to v4.
                telemetry_port=port,
            )

            server = threading.Thread(target=wait_for_data)
            server.start()

            dogstatsd.increment('abc')

            server.join(3)

            expected_telemetry = telemetry_metrics(metrics=1, packets_sent=1, bytes_sent=8)
            self.assertEqual(udp_thread_telemetry_data, expected_telemetry)

    def test_dedicated_uds_telemetry_dest(self):
        tempdir = tempfile.mkdtemp()
        socket_path = os.path.join(tempdir, 'socket.sock')

        listener_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        listener_sock.bind(socket_path)

        def wait_for_data():
            global uds_thread_telemetry_data
            uds_thread_telemetry_data = listener_sock.recvfrom(UDS_OPTIMAL_PAYLOAD_LENGTH)[0].decode('utf-8')

        with closing(listener_sock):
            dogstatsd = DogStatsd(
                host="localhost",
                port=12345,
                telemetry_min_flush_interval=0,
                telemetry_socket_path=socket_path,
            )

            server = threading.Thread(target=wait_for_data)
            server.start()

            dogstatsd.increment('def')

            server.join(3)

            expected_telemetry = telemetry_metrics(metrics=1, packets_sent=1, bytes_sent=8)
            self.assertEqual(uds_thread_telemetry_data, expected_telemetry)

        shutil.rmtree(tempdir)

    def test_context_manager(self):
        fake_socket = FakeSocket()
        with DogStatsd(telemetry_min_flush_interval=0) as dogstatsd:
            dogstatsd.socket = fake_socket
            dogstatsd.gauge('page.views', 123)
            dogstatsd.timing('timer', 123)
            dogstatsd.increment('my_counter', 3)

        metric1 = "page.views:123|g"
        metric2 = "timer:123|ms"
        metric3 = "my_counter:3|c"

        metrics = '\n'.join([metric1, metric2, metric3]) + "\n"
        self.assertEqual(metrics, fake_socket.recv(no_wait=True))

        metrics_packet = telemetry_metrics(
            metrics=3,
            bytes_sent=len(metrics),
            packets_sent=1,
        )
        self.assertEqual(metrics_packet, fake_socket.recv(no_wait=True))

    def test_context_manager_restores_enabled_buffering_state(self):
        fake_socket = FakeSocket()
        dogstatsd = DogStatsd(telemetry_min_flush_interval=0, disable_buffering=False)
        dogstatsd.socket = fake_socket

        with dogstatsd:
            dogstatsd.gauge('page.views', 123)
            dogstatsd.timing('timer', 123)

        dogstatsd.gauge('newpage.views', 123)
        dogstatsd.timing('newtimer', 123)

        metric1 = "page.views:123|g"
        metric2 = "timer:123|ms"
        metric3 = "newpage.views:123|g"
        metric4 = "newtimer:123|ms"

        metrics1 = '\n'.join([metric1, metric2]) + "\n"
        self.assertEqual(metrics1, fake_socket.recv(no_wait=True))

        metrics_packet1 = telemetry_metrics(metrics=2, bytes_sent=len(metrics1), packets_sent=1)
        self.assertEqual(metrics_packet1, fake_socket.recv(no_wait=True))

        metrics2 = '\n'.join([metric3, metric4]) + "\n"
        metrics_packet2 = telemetry_metrics(metrics=2, bytes_sent=len(metrics_packet1 + metrics2), packets_sent=2)
        self.assertEqual(metrics2, fake_socket.recv(reset_wait=True))
        self.assertEqual(metrics_packet2, fake_socket.recv())

    def test_context_manager_restores_disabled_buffering_state(self):
        fake_socket = FakeSocket()
        dogstatsd = DogStatsd(telemetry_min_flush_interval=0, disable_buffering=True)
        dogstatsd.socket = fake_socket

        with dogstatsd:
            dogstatsd.gauge('page.views', 123)
            dogstatsd.timing('timer', 123)

        dogstatsd.gauge('newpage.views', 123)
        dogstatsd.timing('newtimer', 123)

        metric1 = "page.views:123|g"
        metric2 = "timer:123|ms"
        metric3 = "newpage.views:123|g"
        metric4 = "newtimer:123|ms"

        metrics1 = '\n'.join([metric1, metric2]) + "\n"
        self.assertEqual(metrics1, fake_socket.recv(no_wait=True))

        metrics_packet1 = telemetry_metrics(metrics=2, bytes_sent=len(metrics1), packets_sent=1)
        self.assertEqual(metrics_packet1, fake_socket.recv(no_wait=True))

        metrics2 = '\n'.join([metric3]) + "\n"
        metrics_packet2 = telemetry_metrics(metrics=1, bytes_sent=len(metrics_packet1 + metrics2), packets_sent=2)
        self.assertEqual(metrics2, fake_socket.recv())
        self.assertEqual(metrics_packet2, fake_socket.recv(no_wait=True))

        metrics3 = '\n'.join([metric4]) + "\n"
        metrics_packet3 = telemetry_metrics(metrics=1, bytes_sent=len(metrics_packet2 + metrics3), packets_sent=2)
        self.assertEqual(metrics3, fake_socket.recv())
        self.assertEqual(metrics_packet3, fake_socket.recv(no_wait=True))

    def test_batched_buffer_autoflush(self):
        fake_socket = FakeSocket()
        bytes_sent = 0
        with DogStatsd(telemetry_min_flush_interval=0, disable_buffering=False) as dogstatsd:
            dogstatsd.socket = fake_socket

            self.assertEqual(dogstatsd._max_payload_size, UDP_OPTIMAL_PAYLOAD_LENGTH)

            single_metric = 'mycounter:1|c\n'
            metrics_per_packet = dogstatsd._max_payload_size // len(single_metric)
            for _ in range(metrics_per_packet + 1):
                dogstatsd.increment('mycounter')
            payload = ''.join([single_metric for _ in range(metrics_per_packet)])

            telemetry = telemetry_metrics(
                metrics=metrics_per_packet+1,
                bytes_sent=len(payload),
            )
            bytes_sent += len(payload) + len(telemetry)
            self.assertEqual(payload, fake_socket.recv())
            self.assertEqual(telemetry, fake_socket.recv())

        self.assertEqual(single_metric, fake_socket.recv())

        telemetry = telemetry_metrics(metrics=0, packets_sent=2, bytes_sent=len(single_metric) + len(telemetry))
        self.assertEqual(telemetry, fake_socket.recv())

    def test_module_level_instance(self):
        self.assertTrue(isinstance(statsd, DogStatsd))

    def test_instantiating_does_not_connect(self):
        dogpound = DogStatsd()
        self.assertIsNone(dogpound.socket)

    def test_accessing_socket_opens_socket(self):
        dogpound = DogStatsd()
        try:
            self.assertIsNotNone(dogpound.get_socket())
        finally:
            dogpound.socket.close()

    def test_accessing_socket_multiple_times_returns_same_socket(self):
        dogpound = DogStatsd()
        fresh_socket = FakeSocket()
        dogpound.socket = fresh_socket
        self.assertEqual(fresh_socket, dogpound.get_socket())
        self.assertNotEqual(FakeSocket(), dogpound.get_socket())

    def test_tags_from_environment(self):
        with preserve_environment_variable('DATADOG_TAGS'):
            os.environ['DATADOG_TAGS'] = 'country:china,age:45,blue'
            dogstatsd = DogStatsd(telemetry_min_flush_interval=0)
        dogstatsd.socket = FakeSocket()
        dogstatsd.gauge('gt', 123.4)
        metric = 'gt:123.4|g|#country:china,age:45,blue\n'
        self.assertEqual(metric, dogstatsd.socket.recv())
        self.assertEqual(telemetry_metrics(tags="country:china,age:45,blue", bytes_sent=len(metric)), dogstatsd.socket.recv())

    def test_tags_from_environment_and_constant(self):
        with preserve_environment_variable('DATADOG_TAGS'):
            os.environ['DATADOG_TAGS'] = 'country:china,age:45,blue'
            dogstatsd = DogStatsd(constant_tags=['country:canada', 'red'], telemetry_min_flush_interval=0)
        dogstatsd.socket = FakeSocket()
        dogstatsd.gauge('gt', 123.4)
        tags = "country:canada,red,country:china,age:45,blue"
        metric = 'gt:123.4|g|#' + tags + '\n'
        self.assertEqual(metric, dogstatsd.socket.recv())
        self.assertEqual(telemetry_metrics(tags=tags, bytes_sent=len(metric)), dogstatsd.socket.recv())

    def test_entity_id_and_container_id(self):
        with preserve_environment_variable('DD_ENTITY_ID'):
            os.environ['DD_ENTITY_ID'] = '04652bb7-19b7-11e9-9cc6-42010a9c016d'
            dogstatsd = DogStatsd(telemetry_min_flush_interval=0)
        dogstatsd.socket = FakeSocket()
        dogstatsd._container_id = "ci-fake-container-id"

        dogstatsd.increment("page.views")
        dogstatsd.flush()
        tags = "dd.internal.entity_id:04652bb7-19b7-11e9-9cc6-42010a9c016d"
        metric = 'page.views:1|c|#' + tags + '|c:ci-fake-container-id\n'
        self.assertEqual(metric, dogstatsd.socket.recv())
        self.assertEqual(telemetry_metrics(tags=tags, bytes_sent=len(metric)), dogstatsd.socket.recv())

    def test_entity_id_and_container_id_and_external_env(self):
        with preserve_environment_variable('DD_ENTITY_ID'), preserve_environment_variable('DD_EXTERNAL_ENV'):
            os.environ['DD_ENTITY_ID'] = '04652bb7-19b7-11e9-9cc6-42010a9c016d'
            os.environ['DD_EXTERNAL_ENV'] = 'it-false,cn-container-name,pu-04652bb7-19b7-11e9-9cc6-42010a9c016d'
            dogstatsd = DogStatsd(telemetry_min_flush_interval=0)
        dogstatsd.socket = FakeSocket()
        dogstatsd._container_id = "ci-fake-container-id"

        dogstatsd.increment("page.views")
        dogstatsd.flush()
        tags = "dd.internal.entity_id:04652bb7-19b7-11e9-9cc6-42010a9c016d"
        metric = 'page.views:1|c|#' + tags + '|c:ci-fake-container-id' + '|e:it-false,cn-container-name,pu-04652bb7-19b7-11e9-9cc6-42010a9c016d' + '\n'
        self.assertEqual(metric, dogstatsd.socket.recv())
        self.assertEqual(telemetry_metrics(tags=tags, bytes_sent=len(metric)), dogstatsd.socket.recv())

    def test_entity_tag_from_environment(self):
        with preserve_environment_variable('DD_ENTITY_ID'):
            os.environ['DD_ENTITY_ID'] = '04652bb7-19b7-11e9-9cc6-42010a9c016d'
            dogstatsd = DogStatsd(telemetry_min_flush_interval=0)
        dogstatsd.socket = FakeSocket()
        dogstatsd.gauge('gt', 123.4)
        metric = 'gt:123.4|g|#dd.internal.entity_id:04652bb7-19b7-11e9-9cc6-42010a9c016d\n'
        self.assertEqual(metric, dogstatsd.socket.recv())
        self.assertEqual(
            telemetry_metrics(tags="dd.internal.entity_id:04652bb7-19b7-11e9-9cc6-42010a9c016d", bytes_sent=len(metric)),
            dogstatsd.socket.recv())

    def test_entity_tag_from_environment_and_constant(self):
        with preserve_environment_variable('DD_ENTITY_ID'):
            os.environ['DD_ENTITY_ID'] = '04652bb7-19b7-11e9-9cc6-42010a9c016d'
            dogstatsd = DogStatsd(constant_tags=['country:canada', 'red'], telemetry_min_flush_interval=0)
        dogstatsd.socket = FakeSocket()
        dogstatsd.gauge('gt', 123.4)
        metric = 'gt:123.4|g|#country:canada,red,dd.internal.entity_id:04652bb7-19b7-11e9-9cc6-42010a9c016d\n'
        self.assertEqual(metric, dogstatsd.socket.recv())
        self.assertEqual(
            telemetry_metrics(tags="country:canada,red,dd.internal.entity_id:04652bb7-19b7-11e9-9cc6-42010a9c016d",
                              bytes_sent=len(metric)),
            dogstatsd.socket.recv()
        )

    def test_entity_tag_and_tags_from_environment_and_constant(self):
        with preserve_environment_variable('DATADOG_TAGS'):
            os.environ['DATADOG_TAGS'] = 'country:china,age:45,blue'
            with preserve_environment_variable('DD_ENTITY_ID'):
                os.environ['DD_ENTITY_ID'] = '04652bb7-19b7-11e9-9cc6-42010a9c016d'
                dogstatsd = DogStatsd(constant_tags=['country:canada', 'red'], telemetry_min_flush_interval=0)
        dogstatsd.socket = FakeSocket()
        dogstatsd.gauge('gt', 123.4)
        tags = "country:canada,red,country:china,age:45,blue,dd.internal.entity_id:04652bb7-19b7-11e9-9cc6-42010a9c016d"
        metric = 'gt:123.4|g|#' + tags + '\n'
        self.assertEqual(metric, dogstatsd.socket.recv())
        self.assertEqual(telemetry_metrics(tags=tags, bytes_sent=len(metric)), dogstatsd.socket.recv())

    def test_dogstatsd_initialization_with_dd_env_service_version(self):
        """
        Dogstatsd should automatically use DD_ENV, DD_SERVICE, and DD_VERSION (if present)
        to set {env, service, version} as global tags for all metrics emitted.
        """
        cases = [
            # Test various permutations of setting DD_* env vars, as well as other global tag configuration.
            # An empty string signifies that the env var either isn't set or that it is explicitly set to empty string.
            ('', '', '', '', [], []),
            ('prod', '', '', '', [], ['env:prod']),
            ('prod', 'dog', '', '', [], ['env:prod', 'service:dog']),
            ('prod', 'dog', 'abc123', '', [], ['env:prod', 'service:dog', 'version:abc123']),
            ('prod', 'dog', 'abc123', 'env:prod,type:app', [], ['env:prod', 'env:prod', 'service:dog', 'type:app', 'version:abc123']),
            ('prod', 'dog', 'abc123', 'env:prod2,type:app', [], ['env:prod', 'env:prod2', 'service:dog', 'type:app', 'version:abc123']),
            ('prod', 'dog', 'abc123', '', ['env:prod', 'type:app'], ['env:prod', 'env:prod', 'service:dog', 'type:app', 'version:abc123']),
            ('prod', 'dog', 'abc123', '', ['env:prod2', 'type:app'], ['env:prod', 'env:prod2', 'service:dog', 'type:app', 'version:abc123']),
            ('prod', 'dog', 'abc123', 'env:prod3,custom_tag:cat', ['env:prod2', 'type:app'], ['custom_tag:cat', 'env:prod', 'env:prod2', 'env:prod3', 'service:dog', 'type:app', 'version:abc123']),
        ]
        for case in cases:
            dd_env, dd_service, dd_version, datadog_tags, constant_tags, global_tags = case
            with EnvVars(
                env_vars={
                    'DATADOG_TAGS': datadog_tags,
                    'DD_ENV': dd_env,
                    'DD_SERVICE': dd_service,
                    'DD_VERSION': dd_version,
                }
            ):
                dogstatsd = DogStatsd(constant_tags=constant_tags, telemetry_min_flush_interval=0)
                dogstatsd.socket = FakeSocket()

            # Guarantee consistent ordering, regardless of insertion order.
            dogstatsd.constant_tags.sort()
            self.assertEqual(global_tags, dogstatsd.constant_tags)

            # Make call with no tags passed; only the globally configured tags will be used.
            global_tags_str = ','.join([t for t in global_tags])
            dogstatsd.gauge('gt', 123.4)
            dogstatsd.flush()

            # Protect against the no tags case.
            metric = 'gt:123.4|g|#{}\n'.format(global_tags_str) if global_tags_str else 'gt:123.4|g\n'
            self.assertEqual(metric, dogstatsd.socket.recv())
            self.assertEqual(
                telemetry_metrics(
                    tags=global_tags_str,
                    bytes_sent=len(metric)
                ),
                dogstatsd.socket.recv(),
            )
            dogstatsd._reset_telemetry()

            # Make another call with local tags passed.
            passed_tags = ['env:prod', 'version:def456', 'custom_tag:toad']
            all_tags_str = ','.join([t for t in passed_tags + global_tags])
            dogstatsd.gauge('gt', 123.4, tags=passed_tags)
            dogstatsd.flush()

            metric = 'gt:123.4|g|#{}\n'.format(all_tags_str)
            self.assertEqual(metric, dogstatsd.socket.recv())
            self.assertEqual(
                telemetry_metrics(
                    tags=global_tags_str,
                    bytes_sent=len(metric),
                ),
                dogstatsd.socket.recv(),
            )

    def test_default_max_udp_packet_size(self):
        dogstatsd = DogStatsd(disable_buffering=False, flush_interval=10000, disable_telemetry=True)
        dogstatsd.socket = FakeSocket()

        for _ in range(10000):
            dogstatsd.increment('val')

        payload = dogstatsd.socket.recv()
        self.assertIsNotNone(payload)
        while payload is not None:
            payload_size = len(payload)
            self.assertLessEqual(payload_size, UDP_OPTIMAL_PAYLOAD_LENGTH)
            self.assertGreater(payload_size, UDP_OPTIMAL_PAYLOAD_LENGTH - 100)

            payload = dogstatsd.socket.recv()

    def test_default_max_uds_packet_size(self):
        dogstatsd = DogStatsd(
            disable_buffering=False,
            socket_path="fake",
            flush_interval=10000,
            disable_telemetry=True,
        )
        dogstatsd.socket = FakeSocket(socket_path=dogstatsd.socket_path)

        for _ in range(10000):
            dogstatsd.increment('val')

        payload = dogstatsd.socket.recv()
        self.assertIsNotNone(payload)
        while payload is not None:
            payload_size = len(payload)
            self.assertLessEqual(payload_size, UDS_OPTIMAL_PAYLOAD_LENGTH)
            self.assertGreater(payload_size, UDS_OPTIMAL_PAYLOAD_LENGTH - 100)

            payload = dogstatsd.socket.recv()

    def test_custom_max_packet_size(self):
        dogstatsd = DogStatsd(
            disable_buffering=False,
            max_buffer_len=4000,
            flush_interval=10000,
            disable_telemetry=True,
        )
        dogstatsd.socket = FakeSocket()

        for _ in range(10000):
            dogstatsd.increment('val')

        payload = dogstatsd.socket.recv()
        self.assertIsNotNone(payload)
        while payload is not None:
            payload_size = len(payload)
            self.assertLessEqual(payload_size, 4000)
            self.assertGreater(payload_size, 3900)

            payload = dogstatsd.socket.recv()

    def test_gauge_does_not_send_none(self):
        self.statsd.gauge('metric', None)
        self.assertIsNone(self.recv())

    def test_increment_does_not_send_none(self):
        self.statsd.increment('metric', None)
        self.assertIsNone(self.recv())

    def test_decrement_does_not_send_none(self):
        self.statsd.decrement('metric', None)
        self.assertIsNone(self.recv())

    def test_timing_does_not_send_none(self):
        self.statsd.timing('metric', None)
        self.assertIsNone(self.recv())

    def test_histogram_does_not_send_none(self):
        self.statsd.histogram('metric', None)
        self.assertIsNone(self.recv())

    def test_set_with_container_field(self):
        self.statsd._container_id = "ci-fake-container-id"
        self.statsd.set("set", 123)
        self.assert_equal_telemetry("set:123|s|c:ci-fake-container-id\n", self.recv(2))
        self.statsd._container_id = None

    def test_gauge_with_container_field(self):
        self.statsd._container_id = "ci-fake-container-id"
        self.statsd.gauge("gauge", 123.4)
        self.assert_equal_telemetry("gauge:123.4|g|c:ci-fake-container-id\n", self.recv(2))
        self.statsd._container_id = None

    def test_counter_with_container_field(self):
        self.statsd._container_id = "ci-fake-container-id"

        self.statsd.increment("page.views")
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:1|c|c:ci-fake-container-id\n", self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.increment("page.views", 11)
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:11|c|c:ci-fake-container-id\n", self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.decrement("page.views")
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:-1|c|c:ci-fake-container-id\n", self.recv(2))

        self.statsd._reset_telemetry()
        self.statsd.decrement("page.views", 12)
        self.statsd.flush()
        self.assert_equal_telemetry("page.views:-12|c|c:ci-fake-container-id\n", self.recv(2))

        self.statsd._container_id = None

    def test_histogram_with_container_field(self):
        self.statsd._container_id = "ci-fake-container-id"
        self.statsd.histogram("histo", 123.4)
        self.assert_equal_telemetry("histo:123.4|h|c:ci-fake-container-id\n", self.recv(2))
        self.statsd._container_id = None

    def test_timing_with_container_field(self):
        self.statsd._container_id = "ci-fake-container-id"
        self.statsd.timing("t", 123)
        self.assert_equal_telemetry("t:123|ms|c:ci-fake-container-id\n", self.recv(2))
        self.statsd._container_id = None

    def test_event_with_container_field(self):
        self.statsd._container_id = "ci-fake-container-id"
        self.statsd.event(
            "Title",
            "L1\nL2",
            priority="low",
            date_happened=1375296969,
        )
        event2 = u"_e{5,6}:Title|L1\\nL2|d:1375296969|p:low|c:ci-fake-container-id\n"
        self.assert_equal_telemetry(
            event2,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                bytes_sent=len(event2),
            ),
        )

        self.statsd._reset_telemetry()

        self.statsd.event("Title", u"♬ †øU †øU ¥ºu T0µ ♪", aggregation_key="key", tags=["t1", "t2:v2"])
        event3 = u"_e{5,32}:Title|♬ †øU †øU ¥ºu T0µ ♪|k:key|#t1,t2:v2|c:ci-fake-container-id\n"
        self.assert_equal_telemetry(
            event3,
            self.recv(2, reset_wait=True),
            telemetry=telemetry_metrics(
                metrics=0,
                events=1,
                bytes_sent=len(event3),
            ),
        )
        self.statsd._container_id = None

    def test_service_check_with_container_field(self):
        self.statsd._container_id = "ci-fake-container-id"
        now = int(time.time())
        self.statsd.service_check(
            "my_check.name",
            self.statsd.WARNING,
            tags=["key1:val1", "key2:val2"],
            timestamp=now,
            hostname=u"i-abcd1234",
            message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪",
        )
        check = u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#key1:val1,key2:val2|m:{2}|c:ci-fake-container-id\n'.format(
            self.statsd.WARNING, now, u'♬ †øU \\n†øU ¥ºu|m\\: T0µ ♪'
        )
        self.assert_equal_telemetry(
            check,
            self.recv(2),
            telemetry=telemetry_metrics(
                metrics=0,
                service_checks=1,
                bytes_sent=len(check),
            ),
        )
        self.statsd._container_id = None

    def test_sender_mode(self):
        statsd = DogStatsd(disable_background_sender=True)
        self.assertIsNone(statsd._queue)

        statsd.enable_background_sender()
        self.assertIsNotNone(statsd._queue)

        statsd = DogStatsd(disable_background_sender=False)
        self.assertIsNotNone(statsd._queue)

    def test_sender_queue_expiry_seconds_defaults_to_constant(self):
        statsd = DogStatsd(disable_background_sender=False)
        self.assertEqual(statsd._sender_queue_expiry_seconds, PENDING_PAYLOAD_EXPIRY_SECONDS)
        self.assertEqual(statsd._queue._expiry_seconds, PENDING_PAYLOAD_EXPIRY_SECONDS)
        statsd.stop()

    def test_sender_queue_expiry_seconds_is_configurable(self):
        statsd = DogStatsd(
            disable_background_sender=False,
            sender_queue_expiry_seconds=0.5,
        )
        self.assertEqual(statsd._sender_queue_expiry_seconds, 0.5)
        self.assertEqual(statsd._queue._expiry_seconds, 0.5)
        statsd.stop()

    def test_enable_background_sender_accepts_expiry_seconds(self):
        statsd = DogStatsd(disable_background_sender=True)
        statsd.enable_background_sender(sender_queue_expiry_seconds=1.5)
        self.assertEqual(statsd._sender_queue_expiry_seconds, 1.5)
        self.assertEqual(statsd._queue._expiry_seconds, 1.5)
        statsd.stop()

    def test_sender_calls_task_done(self):
        statsd = DogStatsd(disable_background_sender=False)
        statsd.socket = OverflownSocket()
        statsd.increment("test.metric")
        statsd.wait_for_pending()

    def test_sender_queue_no_timeout(self):
        statsd = DogStatsd(disable_background_sender=False, sender_queue_timeout=None)
        statsd.stop()

    def _call_bounded(self, func, args=(), limit=5.0):
        """Call func in a worker thread, failing if it doesn't return in time.

        Everything exercised below exists to *bound* a wait, so a regression
        that reintroduces an unbounded wait should surface as a clear failure
        rather than hanging the whole suite until CI kills the job.
        """
        result = {}

        def run():
            result["value"] = func(*args)

        t = threading.Thread(target=run)
        t.daemon = True
        t.start()
        t.join(limit)
        self.assertFalse(
            t.is_alive(),
            "{} did not return within {}s: timeout not honoured".format(getattr(func, "__name__", func), limit),
        )
        return result["value"]

    def test_queue_join_timeout(self):
        # join(timeout) must report whether the queue actually drained, and must
        # not rely on Condition.wait()'s return value (always None on Python 2).
        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=100.0,
            on_drop_queue_full=lambda item: self.fail("unexpected full drop"),
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )
        self.assertIs(pending_queue.join(0), True)
        self.assertIs(pending_queue.join(), True)

        pending_queue.put(PendingPayload("first\n", sender_queue_clock()))

        # Nothing is draining it, so a bounded join must give up and say so
        # rather than blocking forever or claiming success.
        t0 = time.time()
        self.assertIs(self._call_bounded(pending_queue.join, (0.2,)), False)
        self.assertGreaterEqual(time.time() - t0, 0.2)

        # timeout=0 is a non-blocking poll.
        t0 = time.time()
        self.assertIs(self._call_bounded(pending_queue.join, (0,)), False)
        self.assertLess(time.time() - t0, 0.2)

        # Once the payload is accounted for, join() succeeds.
        got = pending_queue.get()
        pending_queue.task_done(got)
        self.assertIs(pending_queue.join(0), True)

    def test_queue_join_timeout_returns_as_soon_as_the_queue_drains(self):
        # A generous timeout must not be waited out: join() returns as soon as
        # the last task is done.
        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=100.0,
            on_drop_queue_full=lambda item: None,
            on_drop_expired=lambda item: None,
        )
        pending_queue.put(PendingPayload("first\n", sender_queue_clock()))

        def drain():
            time.sleep(0.2)
            got = pending_queue.get()
            pending_queue.task_done(got)

        t = threading.Thread(target=drain)
        t.start()
        try:
            t0 = time.time()
            self.assertIs(pending_queue.join(10.0), True)
            elapsed = time.time() - t0
        finally:
            t.join(timeout=5.0)
        self.assertLess(elapsed, 5.0, "join() should return on drain, not wait out the whole timeout")

    def test_wait_for_pending_timeout(self):
        # A queue with no sender thread draining it: wait_for_pending() must
        # give up and report False rather than blocking forever. Done without a
        # thread on purpose -- the default transport is UDP, where a send
        # succeeds even with nothing listening, so "assign no socket" would not
        # reliably keep a payload pending.
        statsd = DogStatsd(disable_background_sender=True, disable_telemetry=True)
        statsd._queue = SenderQueue(
            0,
            PENDING_PAYLOAD_EXPIRY_SECONDS,
            lambda item: None,
            lambda item: None,
        )
        statsd._send_to_server("test.metric:1|c")

        t0 = time.time()
        self.assertIs(self._call_bounded(statsd.wait_for_pending, (0.2,)), False)
        self.assertGreaterEqual(time.time() - t0, 0.2)

        # timeout=0 is a non-blocking poll.
        self.assertIs(self._call_bounded(statsd.wait_for_pending, (0,)), False)

    def test_wait_for_pending_returns_true_with_no_queue(self):
        # Nothing queued (background sender disabled) is trivially "drained".
        statsd = DogStatsd(disable_background_sender=True, disable_telemetry=True)
        self.assertIsNone(statsd._queue)
        self.assertIs(statsd.wait_for_pending(), True)
        self.assertIs(statsd.wait_for_pending(0), True)

    def test_stop_timeout_reports_failure_and_keeps_the_thread_joinable(self):
        # A wedged sender must not make stop() hang forever when a timeout is
        # given, and stop() must say it didn't finish.
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        release = threading.Event()
        wedged = statsd._sender_thread

        # Wedge the sender inside a send so it can't observe Stop.
        def blocking_xmit(packet, queue_mode=False):
            release.wait(10.0)
            return True

        statsd._xmit_packet_with_telemetry = blocking_xmit
        statsd._send_to_server("test.metric:1|c")
        time.sleep(0.1)  # let the sender pick it up and wedge

        try:
            t0 = time.time()
            self.assertIs(self._call_bounded(statsd.stop, (0.2,)), False)
            self.assertGreaterEqual(time.time() - t0, 0.2)
            # The handle is retained so the thread isn't lost.
            self.assertIs(statsd._sender_thread, wedged)
            self.assertTrue(wedged.is_alive())

            # Unwedge: a second stop() now succeeds and clears the handle.
            release.set()
            self.assertIs(statsd.stop(5.0), True)
            self.assertIsNone(statsd._sender_thread)
        finally:
            release.set()
            wedged.join(timeout=5.0)

    def test_metric_call_racing_stop_does_not_land_behind_the_stop_sentinel(self):
        # The actual regression this guards against: a metric call racing
        # disable_background_sender() must never land in the queue BEHIND
        # the Stop sentinel -- where it would be silently lost once the
        # sender reaches Stop and exits without ever seeing it. Rejecting
        # new puts is gated on _sender_stopping (set before Stop is
        # appended, both under the same lock _send_to_server() re-checks --
        # see _stop_sender_thread), not on self._queue itself, which stays
        # non-None until the sender actually finishes with it.
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        release = threading.Event()
        entered_first_send = threading.Event()
        sent = []

        def blocking_xmit(packet, queue_mode=False):
            sent.append(packet)
            entered_first_send.set()
            release.wait(10.0)
            return True

        statsd._xmit_packet_with_telemetry = blocking_xmit
        statsd._send_to_server("first:1|c")
        self.assertTrue(entered_first_send.wait(5.0), "sender never picked up the first payload")

        stop_result = {}
        second_result = {}

        def call_stop():
            stop_result["value"] = statsd.stop(5.0)

        def call_second():
            # Deliberately started only once the queue is confirmed already
            # closed below -- this IS the race under test.
            statsd._send_to_server("second:1|c")
            second_result["done"] = True

        stopper = threading.Thread(target=call_stop)
        stopper.start()
        second_thread = None
        try:
            # _stop_sender_thread sets _sender_stopping (which is what
            # _send_to_server() rejects new puts on) well before the drain
            # can possibly finish -- it only needs to set a flag and append
            # Stop, not wait for the wedged send. Poll briefly rather than a
            # fixed sleep, to stay fast without being flaky on a slower
            # machine.
            signalled = False
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if statsd._sender_stopping.is_set():
                    signalled = True
                    break
                time.sleep(0.01)
            self.assertTrue(signalled, "the shutdown signal must be set promptly, without waiting for the drain")
            self.assertIsNotNone(statsd._queue, "the real, still-draining queue must remain reachable")
            self.assertTrue(stopper.is_alive(), "stop() must still be waiting on the wedged sender")

            second_thread = threading.Thread(target=call_second)
            second_thread.start()
            # Still wedged behind the first send (same mocked entry point,
            # same release Event) -- confirms this really took the direct-
            # send fallback rather than silently returning after a queue put.
            second_thread.join(0.3)
            self.assertTrue(second_thread.is_alive(), "expected the direct send to be wedged behind the first one too")
        finally:
            release.set()
            stopper.join(timeout=10.0)
            if second_thread is not None:
                second_thread.join(timeout=10.0)

        self.assertIs(stop_result.get("value"), True, "stop() should have completed cleanly")
        self.assertTrue(second_result.get("done"))
        self.assertEqual(
            sent, ["first:1|c\n", "second:1|c\n"],
            "the racing payload must have been delivered (via a direct send), not lost behind Stop",
        )

    def test_stop_timeout_is_bounded_when_a_producer_is_wedged_waiting_for_room(self):
        # The actual regression this guards against: a producer thread
        # blocked inside SenderQueue.put(), waiting for room in a full
        # queue, holds _buffer_lock for as long as that wait lasts -- up to
        # sender_queue_timeout, or forever if it's None. Without
        # SenderQueue.close() waking it immediately, _stop_sender_thread()
        # can't even acquire that lock to append Stop, so stop(timeout)
        # ignores its own timeout entirely (bounded only by whatever else
        # eventually frees the stuck producer -- nothing, in the worst case).
        statsd = DogStatsd(
            disable_background_sender=False,
            disable_telemetry=True,
            sender_queue_size=1,
            sender_queue_timeout=None,  # wait forever for room if not interrupted
        )
        release = threading.Event()
        entered_send = threading.Event()

        def blocking_xmit(packet, queue_mode=False):
            entered_send.set()
            release.wait(30.0)
            return True

        statsd._xmit_packet_with_telemetry = blocking_xmit
        statsd._send_to_server("first:1|c")
        self.assertTrue(entered_send.wait(5.0), "sender never picked up first")
        # get() already popped "first" off the queue while the sender is
        # wedged inside the mocked send -- refill it to maxsize=1 so the
        # NEXT put() has nowhere to go.
        statsd._send_to_server("second:1|c")
        self.assertEqual(statsd._queue.qsize(), 1)

        producer_started = threading.Event()

        def producer():
            producer_started.set()
            statsd._send_to_server("third:1|c")

        producer_thread = threading.Thread(target=producer)
        producer_thread.start()
        self.assertTrue(producer_started.wait(5.0))
        # Give the producer a moment to actually reach put()'s internal wait
        # (queue full, sender_queue_timeout=None) before racing stop().
        time.sleep(0.2)

        try:
            t0 = time.time()
            self.assertIs(self._call_bounded(statsd.stop, (1.0,), limit=3.0), False)
            elapsed = time.time() - t0
            self.assertLess(elapsed, 3.0, "stop(1) must not hang behind a producer wedged in put()")
            self.assertGreaterEqual(elapsed, 1.0, "stop(1) should still take roughly its own timeout, not return early")
        finally:
            release.set()
            producer_thread.join(timeout=5.0)

    def test_stop_timeout_is_bounded_while_the_sender_holds_the_socket_lock(self):
        # The wedge that matters in practice: the sender is parked inside a
        # blocking send() and therefore owns _socket_lock. stop()'s own
        # close_socket()/flush calls want that same lock, so without care they
        # block for as long as the sender stays stuck and the timeout means
        # nothing. stop() must still return within its timeout.
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        release = threading.Event()
        entered_send = threading.Event()
        wedged = statsd._sender_thread

        class BlockingSocket(object):
            def send(self, data):
                entered_send.set()
                release.wait(30.0)
                return len(data)

            def sendall(self, data):
                return self.send(data)

            def close(self):
                pass

            def setblocking(self, *args):
                pass

            def settimeout(self, *args):
                pass

            def getsockopt(self, *args):
                return MIN_SEND_BUFFER_SIZE

            def setsockopt(self, *args):
                pass

        statsd.socket = BlockingSocket()
        for i in range(5):
            statsd._send_to_server("test.metric.{}:1|c".format(i))
        self.assertTrue(entered_send.wait(5.0), "sender never reached send()")

        try:
            t0 = time.time()
            self.assertIs(self._call_bounded(statsd.stop, (0.2,)), False)
            elapsed = time.time() - t0
            self.assertGreaterEqual(elapsed, 0.2)
            self.assertLess(elapsed, 5.0, "stop() blocked well past its timeout")

            # The socket was deliberately left alone: closing it under a thread
            # that is mid-send is both unsafe and the thing that would block.
            self.assertIsNotNone(statsd.socket)
            self.assertTrue(wedged.is_alive())
            self.assertIs(statsd._sender_thread, wedged)
        finally:
            release.set()
            wedged.join(timeout=5.0)

    def test_stop_timeout_then_restart_does_not_orphan_the_sender(self):
        # After a timed-out stop() the sender is still running and the queue is
        # intentionally retained. Re-enabling the background sender must not
        # mint a SECOND thread alongside the first (which is what happened when
        # the queue was dropped on timeout): the client would leak a thread and
        # end up with two senders sharing one socket/lock.
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        release = threading.Event()
        entered_send = threading.Event()
        wedged = statsd._sender_thread

        def blocking_send(self, data):
            entered_send.set()
            release.wait(30.0)
            return len(data)

        statsd.socket = type("W", (object,), {
            "send": blocking_send,
            "sendall": blocking_send,
            "close": lambda self: None,
            "setblocking": lambda self, *a: None,
            "settimeout": lambda self, *a: None,
            "getsockopt": lambda self, *a: MIN_SEND_BUFFER_SIZE,
            "setsockopt": lambda self, *a: None,
        })()
        statsd._send_to_server("test.metric:1|c")
        self.assertTrue(entered_send.wait(5.0))

        try:
            self.assertIs(self._call_bounded(statsd.stop, (0.2,)), False)
            self.assertTrue(wedged.is_alive())
            self.assertIsNotNone(statsd._queue, "queue must be retained so state stays coherent")

            statsd.enable_background_sender()
            # This identity check IS the proof there's no orphan: if a second
            # thread had been minted, _sender_thread would now point at it
            # instead of at wedged. (Deliberately not also scanning
            # threading.enumerate() for same-named threads process-wide: this
            # file has other, unrelated tests that spin up daemon
            # "DogStatsd_sender_thread"s of their own, so a global count is not
            # a property this test can own.)
            self.assertIs(
                statsd._sender_thread, wedged,
                "re-enabling after a timed-out stop must not start a second sender thread",
            )
            self.assertTrue(wedged.is_alive())
        finally:
            release.set()
            wedged.join(timeout=5.0)

    def test_stop_timeout_then_unwedge_then_restart_starts_fresh(self):
        # Once the timed-out thread finally drains and exits, the client
        # self-heals: the next stop() reports success and cleans up, and a
        # re-enabled background sender is a brand new thread over a new queue.
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        release = threading.Event()
        entered_send = threading.Event()
        wedged = statsd._sender_thread

        def blocking_send(self, data):
            entered_send.set()
            release.wait(30.0)
            return len(data)

        statsd.socket = type("W", (object,), {
            "send": blocking_send,
            "sendall": blocking_send,
            "close": lambda self: None,
            "setblocking": lambda self, *a: None,
            "settimeout": lambda self, *a: None,
            "getsockopt": lambda self, *a: MIN_SEND_BUFFER_SIZE,
            "setsockopt": lambda self, *a: None,
        })()
        statsd._send_to_server("test.metric:1|c")
        self.assertTrue(entered_send.wait(5.0))

        try:
            self.assertIs(self._call_bounded(statsd.stop, (0.2,)), False)
            release.set()  # let the wedged send finish; the thread drains and exits
            self.assertIs(self._call_bounded(statsd.stop, (5.0,)), True)
            self.assertIsNone(statsd._queue)
            self.assertIsNone(statsd._sender_thread)

            statsd.enable_background_sender()
            self.assertIsNotNone(statsd._sender_thread)
            self.assertIsNot(statsd._sender_thread, wedged, "a fresh thread should start")
            self.assertTrue(statsd._sender_thread.is_alive())
            self.assertFalse(wedged.is_alive(), "the old thread must have actually exited, not just been forgotten")
        finally:
            release.set()
            # The fresh thread's queue is empty and has never been sent a Stop
            # sentinel, so joining statsd._sender_thread directly would just
            # time out waiting on a get() that never returns -- leaking the
            # thread into later tests. stop() sends Stop and joins correctly
            # regardless of which thread/queue is current.
            statsd.stop(5.0)

    def test_sender_self_heals_when_the_timed_out_thread_finishes_on_its_own(self):
        # The timed-out thread can exit without a second stop() ever being
        # called. The client must detect that and allow a fresh sender, rather
        # than keeping the dead thread / stale queue around and silently
        # refusing to start a new one (metrics would then queue up and drop).
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        release = threading.Event()
        entered_send = threading.Event()
        wedged = statsd._sender_thread

        def blocking_send(self, data):
            entered_send.set()
            release.wait(30.0)
            return len(data)

        statsd.socket = type("W", (object,), {
            "send": blocking_send,
            "sendall": blocking_send,
            "close": lambda self: None,
            "setblocking": lambda self, *a: None,
            "settimeout": lambda self, *a: None,
            "getsockopt": lambda self, *a: MIN_SEND_BUFFER_SIZE,
            "setsockopt": lambda self, *a: None,
        })()
        statsd._send_to_server("test.metric:1|c")
        self.assertTrue(entered_send.wait(5.0))

        try:
            self.assertIs(self._call_bounded(statsd.stop, (0.2,)), False)
            self.assertIsNotNone(statsd._queue)
            self.assertIs(statsd._sender_thread, wedged)

            # Caller moved on and never called stop() again; the wedged send
            # eventually completes and the thread drains and exits on its own.
            release.set()
            wedged.join(timeout=5.0)
            self.assertFalse(wedged.is_alive())

            # The exit must have healed the client state so a re-enable works.
            self.assertIsNone(statsd._queue)
            self.assertIsNone(statsd._sender_thread)
            statsd.enable_background_sender()
            self.assertIsNot(
                statsd._sender_thread, wedged,
                "a timed-out thread that finished on its own must not block a restart",
            )
            self.assertTrue(statsd._sender_thread.is_alive())
        finally:
            release.set()
            # Same reason as the sibling test above: the fresh thread started
            # by enable_background_sender() has an empty queue and was never
            # sent Stop, so joining it directly would time out and leak it.
            statsd.stop(5.0)

    def test_wait_for_pending_is_honest_after_a_stop_timeout(self):
        # After a timed-out stop(), the queue is retained (not shown as empty),
        # so wait_for_pending() still reports the truth -- False while the
        # sender is draining, True once it has actually drained -- rather than
        # claiming "drained" while a live thread is still sending.
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        release = threading.Event()
        entered_send = threading.Event()
        wedged = statsd._sender_thread

        def blocking_send(self, data):
            entered_send.set()
            release.wait(30.0)
            return len(data)

        statsd.socket = type("W", (object,), {
            "send": blocking_send,
            "sendall": blocking_send,
            "close": lambda self: None,
            "setblocking": lambda self, *a: None,
            "settimeout": lambda self, *a: None,
            "getsockopt": lambda self, *a: MIN_SEND_BUFFER_SIZE,
            "setsockopt": lambda self, *a: None,
        })()
        statsd._send_to_server("test.metric:1|c")
        self.assertTrue(entered_send.wait(5.0))

        try:
            self.assertIs(self._call_bounded(statsd.stop, (0.2,)), False)
            self.assertIs(
                self._call_bounded(statsd.wait_for_pending, (0.2,)), False,
                "wait_for_pending() must not claim drained while the sender is still running",
            )

            release.set()  # sender finishes the send, hits Stop, drains, exits
            self.assertIs(self._call_bounded(statsd.wait_for_pending, (5.0,)), True)
        finally:
            release.set()
            wedged.join(timeout=5.0)

    def test_stop_and_wait_for_pending_default_to_waiting_forever(self):
        # The default must stay unbounded: a slow-but-progressing sender is
        # waited out completely, with nothing left pending.
        statsd = DogStatsd(disable_background_sender=False, disable_telemetry=True)
        sent = []

        def slow_xmit(packet, queue_mode=False):
            time.sleep(0.05)
            sent.append(packet)
            return True

        statsd._xmit_packet_with_telemetry = slow_xmit
        for i in range(5):
            statsd._send_to_server("test.metric.{}:1|c".format(i))

        self.assertIs(statsd.wait_for_pending(), True)
        self.assertEqual(len(sent), 5, "unbounded wait_for_pending() must drain everything")
        self.assertIs(statsd.stop(), True)
        self.assertIsNone(statsd._sender_thread)

    def test_sender_queue_timeout_blocks_the_calling_thread_through_the_client(self):
        # End-to-end: sender_queue_timeout configured on the real client
        # actually makes statsd.increment() (the calling/application thread)
        # block waiting for room, not just an internal SenderQueue detail.
        statsd = DogStatsd(
            disable_background_sender=False,
            sender_queue_size=1,
            sender_queue_timeout=5.0,
        )
        # No socket assigned: the sender thread can never drain anything by
        # actually sending, so the only way room opens up is via get()
        # pulling an item off (which happens immediately, since nothing can
        # succeed in sending it -- it gets hard-dropped as a writer failure
        # and the sender loop moves on to the next get()).
        statsd.socket = FakeSocket()

        statsd.increment("first")

        t0 = time.time()
        statsd.increment("second")
        elapsed = time.time() - t0

        self.assertLess(elapsed, 5.0, "should not have waited out the full 5s timeout")
        statsd.wait_for_pending()
        statsd.stop()

    def test_bytes_dropped_queue_counts_actual_bytes(self):
        # No sender thread: a live one could drain the first payload before the
        # third is queued, so nothing would be evicted and the counters below
        # would describe a schedule that never happened. Size 2 rather than 1
        # so the eviction order is observable -- with a single slot the evicted
        # entry is both the oldest and the newest.
        statsd = DogStatsd(disable_background_sender=True)
        statsd._queue = SenderQueue(
            2,
            PENDING_PAYLOAD_EXPIRY_SECONDS,
            statsd._account_dropped_queue_full,
            statsd._account_dropped_expired,
        )

        first, second, third = "test.metric.first", "test.metric.second", "test.metric.third"
        statsd._send_to_server(first)
        statsd._send_to_server(second)
        statsd._send_to_server(third)  # evicts the oldest (first) to make room

        # bytes_dropped_queue is the real byte length, including the newline
        # _send_to_server() appends.
        self.assertEqual(statsd.bytes_dropped_queue, len((first + "\n").encode("utf-8")))
        self.assertEqual(statsd.packets_dropped_queue, 1)
        self.assertEqual(statsd.bytes_dropped_expired, 0)
        self.assertEqual(statsd.packets_dropped_expired, 0)

        # Dropping the oldest leaves the two newest queued, in order.
        survivors = [statsd._queue.get().payload, statsd._queue.get().payload]
        self.assertEqual(survivors, [second + "\n", third + "\n"])

        statsd.stop()

    def test_sender_queue_put_timeout_default_evicts_immediately(self):
        # Default put_timeout (0, whether omitted or explicit): no waiting
        # at all, same as before this feature existed. Deliberately omits
        # put_timeout here to prove the *default* -- not just 0 -- means
        # "don't wait", since None means something very different (wait
        # forever) and must not be the implicit default for anyone who
        # constructs a SenderQueue without thinking about put_timeout at all.
        dropped_queue_full = []
        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=100.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )

        pending_queue.put(PendingPayload("first\n", sender_queue_clock()))

        t0 = time.time()
        pending_queue.put(PendingPayload("second\n", sender_queue_clock()))
        elapsed = time.time() - t0

        self.assertLess(elapsed, 0.05, "put() should not have waited at all")
        self.assertEqual([p.payload for p in dropped_queue_full], ["first\n"])
        self.assertEqual(pending_queue.get().payload, "second\n")

    def test_sender_queue_put_timeout_zero_evicts_immediately(self):
        # Same as the default, but with put_timeout=0 passed explicitly.
        dropped_queue_full = []
        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=100.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
            put_timeout=0,
        )

        pending_queue.put(PendingPayload("first\n", sender_queue_clock()))

        t0 = time.time()
        pending_queue.put(PendingPayload("second\n", sender_queue_clock()))
        elapsed = time.time() - t0

        self.assertLess(elapsed, 0.05, "put() should not have waited at all")
        self.assertEqual([p.payload for p in dropped_queue_full], ["first\n"])
        self.assertEqual(pending_queue.get().payload, "second\n")

    def test_sender_queue_put_timeout_none_waits_forever_and_never_evicts(self):
        # put_timeout=None is an explicit opt-in to unbounded blocking: put()
        # must keep waiting indefinitely -- not fall back to eviction after
        # some internal default -- until room actually opens up.
        dropped_queue_full = []
        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=100.0,
            on_drop_queue_full=lambda item: dropped_queue_full.append(item),
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
            put_timeout=None,
        )
        pending_queue.put(PendingPayload("first\n", sender_queue_clock()))

        result = {}

        def blocked_put():
            t0 = time.time()
            pending_queue.put(PendingPayload("second\n", sender_queue_clock()))
            result["elapsed"] = time.time() - t0

        t = threading.Thread(target=blocked_put)
        t.start()
        try:
            # Nothing is draining the queue: with a real timeout this would
            # have already fired and evicted "first" well before 1s. With
            # None it must still be waiting.
            time.sleep(1.0)
            self.assertTrue(t.is_alive(), "put(timeout=None) must keep waiting, never fall back to eviction on its own")
            self.assertEqual(dropped_queue_full, [])

            # Now free up room: the blocked put() should wake up and
            # succeed without ever having dropped anything.
            first = pending_queue.get()
            self.assertEqual(first.payload, "first\n")
            pending_queue.task_done(first)
        finally:
            t.join(timeout=5.0)

        self.assertFalse(t.is_alive())
        self.assertEqual(dropped_queue_full, [], "put_timeout=None must never fall back to eviction")
        self.assertEqual(pending_queue.get().payload, "second\n")

    def test_sender_queue_put_timeout_wakes_up_when_room_opens(self):
        # A slot freed by get() (well within put_timeout) should wake a
        # blocked put() immediately rather than making it wait out the full
        # timeout, and nothing should be dropped.
        dropped_queue_full = []
        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=100.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
            put_timeout=5.0,
        )
        pending_queue.put(PendingPayload("first\n", sender_queue_clock()))

        result = {}

        def blocked_put():
            t0 = time.time()
            pending_queue.put(PendingPayload("second\n", sender_queue_clock()))
            result["elapsed"] = time.time() - t0

        t = threading.Thread(target=blocked_put)
        t.start()
        time.sleep(0.2)
        self.assertTrue(t.is_alive(), "put() should still be waiting for room")

        # Drain the one slot: the blocked put() should wake up promptly.
        first = pending_queue.get()
        self.assertEqual(first.payload, "first\n")
        pending_queue.task_done(first)

        t.join(timeout=5.0)
        self.assertFalse(t.is_alive())
        self.assertLess(result["elapsed"], 5.0, "should have woken up well before the 5s timeout")
        self.assertEqual(dropped_queue_full, [], "nothing should have been dropped: room opened up in time")
        self.assertEqual(pending_queue.get().payload, "second\n")

    def test_sender_queue_put_timeout_falls_back_to_eviction(self):
        # If room never opens up within put_timeout, put() falls back to
        # the same drop-oldest eviction as the immediate (no-wait) case.
        dropped_queue_full = []
        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=100.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
            put_timeout=0.2,
        )
        pending_queue.put(PendingPayload("first\n", sender_queue_clock()))

        t0 = time.time()
        pending_queue.put(PendingPayload("second\n", sender_queue_clock()))
        elapsed = time.time() - t0

        self.assertGreaterEqual(elapsed, 0.2)
        self.assertEqual([p.payload for p in dropped_queue_full], ["first\n"])
        self.assertEqual(pending_queue.get().payload, "second\n")

    def test_sender_queue_bulk_expired_reclaim_wakes_blocked_producers(self):
        # When the eviction path's cleanup loop reclaims *more* than the one
        # slot its caller needs, the surplus is real free capacity. Producers
        # already parked in put()'s wait-for-room loop have to be told about
        # it, otherwise they sleep out their full put_timeout while the queue
        # sits half empty.
        put_timeout = 1.0
        maxsize = 4
        dropped_expired = []
        pending_queue = SenderQueue(
            maxsize=maxsize,
            expiry_seconds=100.0,
            on_drop_queue_full=lambda item: self.fail("entries are stale: expect expiry drops, not full drops"),
            on_drop_expired=dropped_expired.append,
            put_timeout=put_timeout,
        )
        # Fill to capacity with entries that are already stale, so the
        # cleanup loop has something to reclaim beyond the mandatory one.
        stale_clock = sender_queue_clock() - 1000.0
        for i in range(maxsize):
            pending_queue.put(PendingPayload("stale-{}\n".format(i), stale_clock))

        result = {}

        def evictor():
            # Queue is full and nothing drains it, so this waits out
            # put_timeout and then falls back to eviction, whose cleanup loop
            # reclaims all remaining stale entries in one go.
            pending_queue.put(PendingPayload("evictor\n", sender_queue_clock()))

        def late_waiter():
            t0 = time.time()
            pending_queue.put(PendingPayload("late\n", sender_queue_clock()))
            result["elapsed"] = time.time() - t0

        t_evictor = threading.Thread(target=evictor)
        t_evictor.start()
        # Start the second producer halfway through the first one's timeout so
        # its own deadline is strictly later: it must be woken by the bulk
        # reclaim, not by its own timeout firing.
        time.sleep(put_timeout / 2.0)
        t_late = threading.Thread(target=late_waiter)
        t_late.start()

        t_evictor.join(timeout=5.0)
        t_late.join(timeout=5.0)
        self.assertFalse(t_evictor.is_alive())
        self.assertFalse(t_late.is_alive())

        # All four stale entries went out through the cleanup path.
        self.assertEqual(
            [p.payload for p in dropped_expired],
            ["stale-0\n", "stale-1\n", "stale-2\n", "stale-3\n"],
        )
        # Both live payloads made it, and the queue is well under maxsize.
        self.assertEqual(pending_queue.qsize(), 2)

        # The heart of it: the late producer had roughly put_timeout/2 left on
        # its own clock when capacity opened up. Waking on the reclaim means
        # ~put_timeout/2 elapsed; sleeping through it means the full
        # put_timeout. Assert it beat its own deadline by a clear margin.
        self.assertLess(
            result["elapsed"],
            put_timeout * 0.9,
            "blocked producer slept through its put_timeout despite the bulk reclaim freeing capacity",
        )

    def test_sender_queue_requeue_front_never_blocks_on_put_timeout(self):
        # requeue_front() runs on the background sender thread; it must
        # never wait on put_timeout, or one stuck retry would stall every
        # other queued payload behind it.
        dropped_queue_full = []
        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=100.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
            put_timeout=5.0,
        )
        in_flight = PendingPayload("in-flight\n", sender_queue_clock())
        pending_queue.put(in_flight)
        got = pending_queue.get()
        pending_queue.put(PendingPayload("new\n", sender_queue_clock()))  # fills the one slot again

        t0 = time.time()
        pending_queue.requeue_front(got)
        elapsed = time.time() - t0

        self.assertLess(elapsed, 0.05, "requeue_front() must not block on put_timeout")
        self.assertEqual([p.payload for p in dropped_queue_full], ["in-flight\n"])
        self.assertEqual(pending_queue.get().payload, "new\n")

    def test_sender_queue_drops_oldest_and_stale_entries_on_overflow(self):
        dropped_queue_full = []
        dropped_expired = []

        pending_queue = SenderQueue(
            maxsize=2,
            expiry_seconds=20.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=dropped_expired.append,
        )

        now = sender_queue_clock()
        fresh = PendingPayload("fresh\n", now)
        stale = PendingPayload("stale\n", now - 100)
        newest = PendingPayload("newest\n", now)

        # Fill the queue: [fresh, stale] (stale is already expired, but that
        # doesn't matter until something tries to make room or pull it off).
        pending_queue.put(fresh)
        pending_queue.put(stale)
        self.assertEqual(pending_queue.qsize(), 2)

        # Queue is full: the oldest entry (fresh) is evicted to make room, and
        # since the next entry at the front (stale) is also expired, it gets
        # opportunistically cleared out too.
        pending_queue.put(newest)

        self.assertEqual([p.payload for p in dropped_queue_full], ["fresh\n"])
        self.assertEqual([p.payload for p in dropped_expired], ["stale\n"])
        self.assertEqual(pending_queue.qsize(), 1)
        self.assertEqual(pending_queue.get().payload, "newest\n")

    def test_sender_queue_overflow_attributes_stale_oldest_entry_to_expiry(self):
        dropped_queue_full = []
        dropped_expired = []

        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=20.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=dropped_expired.append,
        )

        stale = PendingPayload("stale\n", sender_queue_clock() - 100)
        pending_queue.put(stale)

        # The oldest (and only) entry being evicted is itself already
        # expired: that's a staleness drop, not a queue-full drop.
        pending_queue.put(PendingPayload("newest\n", sender_queue_clock()))

        self.assertEqual(dropped_queue_full, [])
        self.assertEqual([p.payload for p in dropped_expired], ["stale\n"])

    def test_sender_queue_get_drops_expired_entries(self):
        dropped_expired = []

        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=20.0,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=dropped_expired.append,
        )

        now = sender_queue_clock()
        pending_queue.put(PendingPayload("stale-1\n", now - 100))
        pending_queue.put(PendingPayload("stale-2\n", now - 100))
        pending_queue.put(PendingPayload("fresh\n", now))

        # get() lazily drains every stale entry at the front before handing
        # back the next payload actually worth sending.
        item = pending_queue.get()
        self.assertEqual(item.payload, "fresh\n")
        self.assertEqual([p.payload for p in dropped_expired], ["stale-1\n", "stale-2\n"])

    def test_sender_queue_replay_safe_payload_never_expires(self):
        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=20.0,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=lambda item: self.fail("replay-safe payload should not expire"),
        )

        # A replay-safe entry is the bare string, so there is no enqueued_at to
        # age against at all -- it can never be dropped for staleness however
        # long it sits there.
        old_but_replay_safe = "timestamped\n"
        pending_queue.put(old_but_replay_safe)

        self.assertTrue(is_replay_safe(old_but_replay_safe))
        self.assertIs(pending_queue.get(), old_but_replay_safe)

    def test_sender_queue_requeue_front_when_room_available(self):
        pending_queue = SenderQueue(
            maxsize=2,
            expiry_seconds=20.0,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )

        in_flight = PendingPayload("in-flight\n", sender_queue_clock())
        pending_queue.put(in_flight)

        # Simulate the sender thread picking it up and failing to send it.
        got = pending_queue.get()
        self.assertIs(got, in_flight)
        pending_queue.requeue_front(got)

        # There was room for it: it's retried first, ahead of anything newer.
        pending_queue.put(PendingPayload("new\n", sender_queue_clock()))
        self.assertEqual(pending_queue.get().payload, "in-flight\n")
        self.assertEqual(pending_queue.get().payload, "new\n")

    def test_sender_queue_requeue_front_drops_when_queue_is_full(self):
        dropped_queue_full = []

        pending_queue = SenderQueue(
            maxsize=1,
            expiry_seconds=20.0,
            on_drop_queue_full=dropped_queue_full.append,
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )

        in_flight = PendingPayload("in-flight\n", sender_queue_clock())
        pending_queue.put(in_flight)

        # Simulate the sender thread picking it up, failing to send it, and a
        # fresh payload filling the now-empty slot in the meantime.
        got = pending_queue.get()
        self.assertIs(got, in_flight)
        pending_queue.put(PendingPayload("new\n", sender_queue_clock()))

        # The queue is already at maxsize: the requeue is dropped rather than
        # growing the queue past its limit or evicting the newer entry.
        pending_queue.requeue_front(got)

        self.assertEqual([p.payload for p in dropped_queue_full], ["in-flight\n"])
        self.assertEqual(pending_queue.qsize(), 1)
        self.assertEqual(pending_queue.get().payload, "new\n")

    def test_sender_queue_requeue_front_drops_when_expired(self):
        dropped_expired = []

        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=0.01,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=dropped_expired.append,
        )

        # Simulate the sender thread picking up a payload and failing to
        # send it, with enough time passing in between that it's now stale.
        # Unbounded queue (so it's never "full") isolates the expiry check.
        in_flight = PendingPayload("stale\n", sender_queue_clock())
        pending_queue.put(in_flight)
        got = pending_queue.get()
        time.sleep(0.02)

        pending_queue.requeue_front(got)

        self.assertEqual([p.payload for p in dropped_expired], ["stale\n"])
        self.assertEqual(pending_queue.qsize(), 0)

    def test_sender_queue_requeue_front_ignores_item_not_in_flight(self):
        # requeue_front() must be called on the exact item get() returned, and
        # only while it's still in flight. Requeuing something that was never
        # get() (or was already finished) would otherwise corrupt
        # _unfinished_tasks. The guard logs the misuse and ignores the call
        # (no deque change, no counter change) so the sender thread stays
        # alive rather than crashing on a bookkeeping bug.
        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=20.0,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )

        never_got = PendingPayload("never-get\n", sender_queue_clock())
        with self._capture_error_logs() as captured:
            pending_queue.requeue_front(never_got)
        self.assertTrue(captured, "the not-in-flight requeue should have logged an error")
        self.assertEqual(pending_queue.qsize(), 0, "never-got item was not added to the deque")
        self.assertEqual(pending_queue._unfinished_tasks, 0, "counter untouched")

        # And requeuing an item that was already finished (get then task_done)
        # is equally ignored: it's no longer in flight, the counter stays put.
        finished = PendingPayload("finished\n", sender_queue_clock())
        pending_queue.put(finished)
        got = pending_queue.get()
        self.assertIs(got, finished)
        pending_queue.task_done(got)
        self.assertEqual(pending_queue._unfinished_tasks, 0, "finished -> counter back to zero")
        with self._capture_error_logs() as captured:
            pending_queue.requeue_front(got)
        self.assertTrue(captured, "the already-finished requeue should have logged an error")
        self.assertEqual(pending_queue._unfinished_tasks, 0, "counter did not drift on the ignored requeue")
        self.assertEqual(pending_queue.qsize(), 0, "already-finished item was not re-added")

    def test_sender_queue_requeue_front_ignores_double_requeue(self):
        # A second requeue_front() of the same item (e.g. two threads both
        # handed the same in-flight reference) would put it in the deque twice
        # while only one task was ever counted. The in-flight guard logs the
        # second call and ignores it, so the deque and counter stay consistent.
        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=20.0,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )

        item = PendingPayload("once\n", sender_queue_clock())
        pending_queue.put(item)
        got = pending_queue.get()
        self.assertIs(got, item)
        pending_queue.requeue_front(got)  # first requeue: fine, back in the deque
        self.assertEqual(pending_queue.qsize(), 1)
        with self._capture_error_logs() as captured:
            pending_queue.requeue_front(got)  # second: no longer in flight
        self.assertTrue(captured, "the double requeue should have logged an error")
        self.assertEqual(pending_queue.qsize(), 1, "item was NOT added to the deque a second time")
        self.assertEqual(pending_queue._unfinished_tasks, 1, "counter unchanged")

    def test_sender_queue_task_done_ignores_double_finish(self):
        # A second task_done() on the same item (double finish) would drive
        # _unfinished_tasks negative. The in-flight guard logs the second call
        # and skips the decrement, so the counter stays at zero instead of
        # going to -1 -- and the sender thread stays alive.
        pending_queue = SenderQueue(
            maxsize=0,
            expiry_seconds=20.0,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )

        item = PendingPayload("once\n", sender_queue_clock())
        pending_queue.put(item)
        got = pending_queue.get()
        pending_queue.task_done(got)
        self.assertEqual(pending_queue._unfinished_tasks, 0, "first finish -> counter at zero")
        with self._capture_error_logs() as captured:
            pending_queue.task_done(got)
        self.assertTrue(captured, "the double finish should have logged an error")
        self.assertEqual(pending_queue._unfinished_tasks, 0, "second finish did NOT drive the counter negative")

    def test_sender_queue_many_threads_get_and_requeue_never_logs_error(self):
        # 100 threads, split into getters and requeuers. Each getter runs
        # get() and hands the item to a requeuer via a thread-safe handoff;
        # each requeuer takes that item and calls requeue_front() on it. So
        # the thread that get() the item is NOT the thread that requeues it --
        # the item crosses thread boundaries. The identity guard is
        # thread-agnostic by design, so this must stay clean: no ERROR log,
        # no counter drift, no crash. This is the future-proofing proof: a
        # legitimate cross-thread get/requeue workload stays clean.
        try:
            import queue as queue_mod
        except ImportError:  # Python 2
            import Queue as queue_mod

        pending_queue = SenderQueue(
            maxsize=0,  # unbounded: requeue never drops for capacity
            expiry_seconds=100.0,
            on_drop_queue_full=lambda item: self.fail("unexpected queue-full drop"),
            on_drop_expired=lambda item: self.fail("unexpected expiry drop"),
        )

        n_items = 200
        n_getters = 50
        n_requeuers = 50
        iterations = 100

        for i in range(n_items):
            pending_queue.put(PendingPayload("item-{}\n".format(i), sender_queue_clock()))
        self.assertEqual(pending_queue._unfinished_tasks, n_items)

        handoff = queue_mod.Queue()
        SENTINEL = object()

        with self._capture_error_logs() as captured:
            def getter():
                for _ in range(iterations):
                    item = pending_queue.get()
                    handoff.put(item)

            def requeuer():
                while True:
                    item = handoff.get()
                    if item is SENTINEL:
                        return
                    pending_queue.requeue_front(item)

            getters = [threading.Thread(target=getter) for _ in range(n_getters)]
            requeuers = [threading.Thread(target=requeuer) for _ in range(n_requeuers)]

            # Start requeuers first so they're draining the handoff before
            # getters begin filling it; otherwise the handoff could grow
            # unbounded and the SenderQueue could drain to empty (getters
            # would then block in get() until requeuers put items back).
            for t in requeuers:
                t.start()
            for t in getters:
                t.start()

            for t in getters:
                t.join()
            # All getters done: every real item is either in the handoff or
            # already requeued. Sentinels go behind them, so no real item is
            # stranded.
            for _ in range(n_requeuers):
                handoff.put(SENTINEL)
            for t in requeuers:
                t.join()

        # No ERROR log ever fired: the in-flight guard never tripped even
        # though every item crossed from the getter thread to a different
        # requeuer thread.
        self.assertEqual(
            captured, [],
            "no error should be logged when get() and requeue_front() run on "
            "different threads; got: {!r}".format([r.getMessage() for r in captured]),
        )

        # Every get() was matched by a requeue_front() (no task_done, no
        # drops on the unbounded queue), so the queue is fully populated and
        # the task counter is unchanged -- no drift.
        self.assertEqual(pending_queue.qsize(), n_items, "all items back in the queue")
        self.assertEqual(
            pending_queue._unfinished_tasks, n_items,
            "_unfinished_tasks never drifted under cross-thread get/requeue contention",
        )

    def test_replay_safety_is_carried_by_the_queued_entry_type(self):
        # Replay-safety is not a stored flag: an entry subject to expiry is a
        # PendingPayload (carrying the enqueued_at it will be judged against),
        # and a replay-safe one is the bare packet string. That keeps the
        # wrapper -- and the GC traversal it implies -- off replay-safe entries
        # entirely.
        statsd = DogStatsd(disable_background_sender=False)
        statsd.socket = FakeSocket()

        captured = []
        original_put = statsd._queue.put

        def capture_put(item):
            if item is not Stop:
                captured.append(item)
            return original_put(item)

        statsd._queue.put = capture_put

        statsd.increment("no.timestamp")
        statsd.gauge_with_timestamp("with.timestamp", 1, int(time.time()))
        statsd.wait_for_pending()

        self.assertEqual(len(captured), 2)

        expiring, replay_safe = captured
        self.assertIsInstance(expiring, PendingPayload)
        self.assertFalse(is_replay_safe(expiring))
        self.assertIsInstance(
            expiring.enqueued_at, float,
            "an expiring payload needs a real timestamp to be judged against",
        )

        # Deliberately not asserting a concrete string type here: on Python 2
        # the serialized packet is unicode, not str. What matters is that the
        # entry is the bare payload rather than a wrapper, which is exactly
        # what is_replay_safe()/payload_text() key off.
        self.assertNotIsInstance(replay_safe, PendingPayload)
        self.assertTrue(is_replay_safe(replay_safe))
        self.assertIs(payload_text(replay_safe), replay_safe)

        # Either form still yields its packet text the same way.
        self.assertTrue(payload_text(expiring).startswith("no.timestamp"))
        self.assertTrue(payload_text(replay_safe).startswith("with.timestamp"))

        statsd.stop()

    def test_connection_failure_requeues_and_resends_once_reconnected(self):
        # A UDS client whose socket is broken. socket_connect_retry=True is
        # what makes queue-mode sends hand off a connection failure to the
        # sender queue's own retry-by-requeuing instead of dropping the
        # payload on the first attempt -- direct sends never do this.
        working_socket = FakeSocket()
        attempts = {"count": 0}

        def flaky_get_uds_socket(cls, socket_path, timeout):
            attempts["count"] += 1
            if attempts["count"] < 4:
                raise socket.error(errno.ECONNREFUSED, "still refused")
            return working_socket

        with mock.patch.object(DogStatsd, "_get_uds_socket", classmethod(flaky_get_uds_socket)):
            statsd = DogStatsd(
                socket_path="/tmp/dogstatsd-test-requeue.sock",
                disable_telemetry=True,
                disable_background_sender=False,
                socket_connect_retry=True,
            )

            statsd.gauge("eventually.sent", 1)
            statsd.wait_for_pending()

        # The payload survived every failed reconnect attempt and was sent
        # once a working socket was finally available -- it was never
        # dropped as a writer failure or expired out of the queue.
        self.assertGreaterEqual(attempts["count"], 4)
        self.assertEqual(statsd.packets_dropped_writer, 0)
        self.assertEqual(statsd.packets_dropped_expired, 0)
        self.assertTrue(working_socket.payloads[0].decode("utf-8").startswith("eventually.sent:1|g"))

        statsd.stop()

    def test_stop_timeout_retries_until_the_deadline_before_abandoning_a_payload(self):
        # The actual regression this guards against: stop(timeout) must keep
        # retrying a connection failure for close to the requested timeout --
        # not abandon on the very first backoff check -- so a payload that
        # would have succeeded on a later attempt is not silently lost.
        working_socket = FakeSocket()
        attempts = {"count": 0}

        def flaky_get_uds_socket(cls, socket_path, timeout):
            attempts["count"] += 1
            if attempts["count"] < 4:
                raise socket.error(errno.ECONNREFUSED, "still refused")
            return working_socket

        with mock.patch.object(DogStatsd, "_get_uds_socket", classmethod(flaky_get_uds_socket)), \
                patch("datadog.dogstatsd.base.SENDER_RETRY_INITIAL_BACKOFF", 0.05):
            statsd = DogStatsd(
                socket_path="/tmp/dogstatsd-test-stop-retries.sock",
                disable_telemetry=True,
                disable_background_sender=False,
                socket_connect_retry=True,
            )

            statsd.gauge("eventually.sent", 1)
            time.sleep(0.05)  # let the first attempt fail and start retrying

            # A generous bounded timeout: comfortably enough for a few fast
            # (patched-down) backoff doublings to reach the 4th, working
            # attempt, but nowhere near SENDER_UNBOUNDED_STOP_GRACE_SECONDS.
            # Before the fix, stop() abandoned on the very first backoff
            # check regardless of this value, so this would have failed:
            # returning near-instantly with the payload never sent.
            self.assertIs(self._call_bounded(statsd.stop, (3.0,), limit=5.0), True)

        self.assertGreaterEqual(attempts["count"], 4)
        self.assertEqual(statsd.packets_dropped_writer, 0, "the payload must not have been abandoned")
        self.assertTrue(working_socket.payloads[0].decode("utf-8").startswith("eventually.sent:1|g"))

    def test_queue_mode_drops_immediately_by_default(self):
        # socket_connect_retry defaults to False for the background sender
        # too: without it, a connection failure on a queued payload is
        # accounted as a writer drop on the very first attempt, exactly like
        # a direct send, rather than requeued and retried.
        statsd = DogStatsd(
            socket_path="/tmp/dogstatsd-test-no-retry-queue.sock",
            disable_background_sender=False,
        )
        self.assertFalse(statsd.socket_connect_retry)
        statsd.socket = BrokenSocket(error_number=errno.ECONNREFUSED)

        statsd.gauge("dropped.immediately", 1)
        statsd.wait_for_pending()

        self.assertGreaterEqual(statsd.packets_dropped_writer, 1)
        self.assertEqual(statsd.packets_dropped_expired, 0)
        statsd.stop()

    def test_queue_mode_retry_backoff_caps_at_one_minute(self):
        # "Backoff...to a maximum of once per minute": the doubling algorithm
        # in _sender_main_loop is unchanged (already exercised end-to-end by
        # test_connection_failure_requeues_and_resends_once_reconnected,
        # which drives it through several real doublings below the cap); what
        # changed is this constant, from the old 1-second cap to 60.
        self.assertEqual(SENDER_RETRY_MAX_BACKOFF, 60.0)

    def _unreachable_retrying_client(self):
        """Background-sender client whose UDS path will never exist.

        socket_connect_retry=True, so every queued payload fails to connect
        and gets requeued at the FRONT of the queue -- ahead of any Stop
        sentinel.
        """
        sock_path = os.path.join(tempfile.mkdtemp(), "never-created.sock")
        return DogStatsd(
            socket_path="unix://" + sock_path,
            socket_connect_retry=True,
            disable_background_sender=False,
            disable_telemetry=True,
            # Keep these out of the module-level _instances WeakSet: the
            # pre_fork test below abandons its instance with _config_lock
            # still held, and the global os.register_at_fork hooks iterate
            # _instances -- a later real fork() would deadlock on it.
            track_instance=False,
        )

    def test_stop_is_bounded_with_a_stuck_replay_safe_payload(self):
        # requeue_front() puts a failed payload back ahead of the Stop
        # sentinel, and replay-safe payloads are exempt from the queue's
        # expiry, so such a payload never resolves while the Agent is down.
        # Without a bounded grace period the sender never reaches Stop at all
        # and stop() hangs forever. A small patched grace makes the test fast
        # and deterministic instead of depending on the real 60s default.
        statsd = self._unreachable_retrying_client()
        statsd.gauge_with_timestamp("replay.safe", 1, timestamp=int(time.time()))
        time.sleep(0.1)  # let the sender pick it up and start retrying

        with patch("datadog.dogstatsd.base.SENDER_UNBOUNDED_STOP_GRACE_SECONDS", 0.3):
            t0 = time.time()
            self.assertIs(self._call_bounded(statsd.stop, ()), False, "the payload was never delivered")
            self.assertLess(time.time() - t0, 5.0, "stop() did not bound the retry loop")
        self.assertIsNone(statsd._queue)
        self.assertEqual(statsd.packets_dropped_writer, 1, "the abandoned payload must be accounted for")

    def test_pre_fork_is_bounded_with_a_stuck_replay_safe_payload(self):
        # Same starvation, reached through pre_fork() -- which matters more:
        # it is installed as an os.register_at_fork hook, has no timeout
        # parameter, and would therefore block any fork() in the process.
        statsd = self._unreachable_retrying_client()
        statsd.gauge_with_timestamp("replay.safe", 1, timestamp=int(time.time()))
        time.sleep(0.1)

        # Run it on a worker so a regression fails this assertion instead of
        # hanging the suite. That means _config_lock -- which pre_fork()
        # deliberately acquires and leaves held for post_fork_parent() to
        # release -- ends up owned by a thread that then exits, so this
        # instance is deliberately abandoned rather than restored. It is
        # constructed with track_instance=False precisely so nothing else can
        # ever try to take that lock again.
        with patch("datadog.dogstatsd.base.SENDER_UNBOUNDED_STOP_GRACE_SECONDS", 0.3):
            t0 = time.time()
            self._call_bounded(statsd.pre_fork, ())
            self.assertLess(time.time() - t0, 5.0, "pre_fork() would have blocked os.fork()")
        self.assertIsNone(statsd._sender_thread, "pre_fork() should have stopped the sender")
        self.assertEqual(statsd.packets_dropped_writer, 1, "the abandoned payload must be accounted for")

    def test_stop_interrupts_a_long_retry_backoff_instead_of_waiting_it_out(self):
        # The backoff cap is a full minute. A plain time.sleep() would make
        # stop() wait out however much of it is left; the shutdown signal must
        # cut it short well before its own (also patched down) grace period.
        statsd = self._unreachable_retrying_client()
        with patch("datadog.dogstatsd.base.SENDER_RETRY_INITIAL_BACKOFF", 30.0), \
                patch("datadog.dogstatsd.base.SENDER_UNBOUNDED_STOP_GRACE_SECONDS", 0.3):
            statsd.gauge("ordinary", 1)
            time.sleep(0.3)  # fail once, then settle into the 30s backoff

            t0 = time.time()
            self.assertIs(self._call_bounded(statsd.stop, ()), False, "the payload was never delivered")
            self.assertLess(time.time() - t0, 5.0, "stop() waited out the backoff sleep")

    def test_sender_can_restart_after_a_stop_cleared_the_stopping_signal(self):
        # The shutdown signal is sticky, so it has to be cleared when a new
        # sender starts or the replacement would exit immediately.
        statsd = self._unreachable_retrying_client()
        statsd.gauge("ordinary", 1)
        time.sleep(0.1)
        with patch("datadog.dogstatsd.base.SENDER_UNBOUNDED_STOP_GRACE_SECONDS", 0.3):
            self.assertIs(self._call_bounded(statsd.stop, ()), False, "the payload was never delivered")

        statsd.enable_background_sender()
        try:
            self.assertIsNotNone(statsd._queue)
            fresh = statsd._sender_thread
            self.assertIsNotNone(fresh)

            # The stale signal only bites once the sender reaches its retry
            # branch, so it has to actually fail a send here: an idle sender
            # just blocks in get() and would mask the bug. With the signal
            # left set, this first failure looks like a shutdown request and
            # the fresh sender exits silently on it.
            statsd.gauge("ordinary", 1)
            time.sleep(0.3)
            self.assertTrue(fresh.is_alive(), "fresh sender exited on a stale stopping signal")
            self.assertIs(statsd._sender_thread, fresh)
        finally:
            # Bounded cleanup: the fresh sender is genuinely retrying against
            # a socket path that will never exist, so a bounded stop() now
            # legitimately waits close to its own timeout before giving up
            # (see the fix above) -- keep it short so this cleanup stays fast.
            statsd.stop(1.0)

    def test_set_socket_timeout(self):
        statsd = DogStatsd(disable_background_sender=False)
        statsd.socket = FakeSocket()
        statsd.set_socket_timeout(1)
        self.assertEqual(statsd.socket.timeout, 1)
        self.assertEqual(statsd.socket_timeout, 1)

    def test_telemetry_api(self):
        statsd = DogStatsd(disable_background_sender=False)

        self.assertEqual(statsd.metrics_count, 0)
        self.assertEqual(statsd.events_count, 0)
        self.assertEqual(statsd.service_checks_count, 0)
        self.assertEqual(statsd.bytes_sent, 0)
        self.assertEqual(statsd.bytes_dropped, 0)
        self.assertEqual(statsd.bytes_dropped_queue, 0)
        self.assertEqual(statsd.bytes_dropped_writer, 0)
        self.assertEqual(statsd.packets_sent, 0)
        self.assertEqual(statsd.packets_dropped, 0)
        self.assertEqual(statsd.packets_dropped_queue, 0)
        self.assertEqual(statsd.packets_dropped_writer, 0)

    def test_max_payload_size(self):
        statsd = DogStatsd(socket_path=None, port=8125)
        self.assertEqual(statsd._max_payload_size, UDP_OPTIMAL_PAYLOAD_LENGTH)

        test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        statsd.socket = test_socket
        self.assertEqual(statsd._max_payload_size, UDP_OPTIMAL_PAYLOAD_LENGTH)

        test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        statsd.socket = test_socket
        self.assertEqual(statsd._max_payload_size, UDS_OPTIMAL_PAYLOAD_LENGTH)

    def test_post_fork_locks(self):
        def inner():
            statsd = DogStatsd(socket_path=None, port=8125)
            # Statsd should survive this sequence of events
            statsd.pre_fork()
            statsd.get_socket()
            statsd.post_fork_parent()
        t = Thread(target=inner)
        t.daemon = True
        t.start()
        t.join(timeout=5)
        self.assertFalse(t.is_alive())

    def test_fake_sockets(self):
        """
        To support legacy behavior wherein customers were able to set sockets directly as long as they supported a .send interface, 
        ensure that arbitrary values passed to these properties are allowed and are handled correctly
        """
        statsd = DogStatsd(disable_buffering=True)

        class fakeSock:
            def __init__(self, id):
                self.id = id
            def send(self, _):
                pass
        statsd.socket = fakeSock(5)
        statsd.telemetry_socket = fakeSock(10)

        assert statsd.socket.id == 5
        assert statsd.telemetry_socket.id == 10

        statsd.increment("test", 1)

        assert statsd.socket is not None

    def test_transport_attribute_present_on_connection_error(self):
        """
        Ensure `_transport` attribute is present for telemetry even if the socket is None.
        """
        # This test will fail with an AttributeError before the fix.
        # Use a non-resolvable host to trigger a connection error.
        statsd = DogStatsd(
            host='non.existent.host.datadog.internal',
            telemetry_min_flush_interval=0  # Flush telemetry immediately
        )

        # This call will attempt to send a metric, fail to create a socket,
        # and then attempt to send telemetry, which requires `_transport`.
        statsd.gauge('test.metric', 1)

        assert statsd.socket is None
        assert statsd._transport is not None
