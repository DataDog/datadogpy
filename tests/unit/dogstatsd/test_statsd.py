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
from contextlib import closing
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
from datadog.dogstatsd.base import DEFAULT_FLUSH_INTERVAL, DogStatsd, MIN_SEND_BUFFER_SIZE, UDP_OPTIMAL_PAYLOAD_LENGTH, UDS_OPTIMAL_PAYLOAD_LENGTH
from datadog.dogstatsd.context import TimedContextManagerDecorator
from datadog.util.compat import is_higher_py35, is_p3k
from tests.util.contextmanagers import preserve_environment_variable, EnvVars
from tests.unit.dogstatsd.fixtures import load_fixtures


class FakeSocket(object):
    """ A fake socket for testing. """

    FLUSH_GRACE_PERIOD = 0.2

    def __init__(self, flush_interval=DEFAULT_FLUSH_INTERVAL):
        self.payloads = deque()

        self._flush_interval = flush_interval
        self._flush_wait = False

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

        if count > len(self.payloads):
            return None

        out = []
        for _ in range(count):
            out.append(self.payloads.popleft().decode('utf-8'))
        return '\n'.join(out)

    def close(self):
        pass

    def __repr__(self):
        return str(self.payloads)


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


def telemetry_metrics(metrics=1, events=0, service_checks=0, bytes_sent=0, bytes_dropped=0, packets_sent=1, packets_dropped=0, transport="udp", tags=""):
    tags = "," + tags if tags else ""

    return "\n".join([
        "datadog.dogstatsd.client.metrics:{}|c|#client:py,client_version:{},client_transport:{}{}".format(metrics, version, transport, tags),
        "datadog.dogstatsd.client.events:{}|c|#client:py,client_version:{},client_transport:{}{}".format(events, version, transport, tags),
        "datadog.dogstatsd.client.service_checks:{}|c|#client:py,client_version:{},client_transport:{}{}".format(service_checks, version, transport, tags),
        "datadog.dogstatsd.client.bytes_sent:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_sent, version, transport, tags),
        "datadog.dogstatsd.client.bytes_dropped:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_dropped, version, transport, tags),
        "datadog.dogstatsd.client.packets_sent:{}|c|#client:py,client_version:{},client_transport:{}{}".format(packets_sent, version, transport, tags),
        "datadog.dogstatsd.client.packets_dropped:{}|c|#client:py,client_version:{},client_transport:{}{}".format(packets_dropped, version, transport, tags)
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

    def assert_equal_telemetry(self, expected_payload, actual_payload, telemetry=None):
        if telemetry is None:
            telemetry = telemetry_metrics(bytes_sent=len(expected_payload))

        if expected_payload:
            expected_payload = "\n".join([expected_payload, telemetry])
        else:
            expected_payload = telemetry

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

    def test_dogstatsd_initialization_with_env_vars(self):
        """
        Dogstatsd can retrieve its config from env vars when
        not provided in constructor.
        """
        # Setup
        with preserve_environment_variable('DD_AGENT_HOST'):
            os.environ['DD_AGENT_HOST'] = 'myenvvarhost'
            with preserve_environment_variable('DD_DOGSTATSD_PORT'):
                os.environ['DD_DOGSTATSD_PORT'] = '4321'
                dogstatsd = DogStatsd()

        # Assert
        self.assertEqual(dogstatsd.host, "myenvvarhost")
        self.assertEqual(dogstatsd.port, 4321)

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

    def test_gauge(self):
        self.statsd.gauge('gauge', 123.4)
        self.assert_equal_telemetry('gauge:123.4|g\n', self.recv(2))

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

    def test_histogram(self):
        self.statsd.histogram('histo', 123.4)
        self.assert_equal_telemetry('histo:123.4|h\n', self.recv(2))

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
        )
        event2 = u'_e{5,6}:Title|L1\\nL2|d:1375296969|p:low\n'
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

    def test_service_check(self):
        now = int(time.time())
        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            tags=['key1:val1', 'key2:val2'], timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪")
        check = u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#key1:val1,key2:val2|m:{2}'.format(self.statsd.WARNING, now, u'♬ †øU \\n†øU ¥ºu|m\\: T0µ ♪\n')
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

    # Test Client level contant tags
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
    def test_udp_socket_ensures_min_receive_buffer(self, mock_socket_create):
        mock_socket = mock_socket_create.return_value
        mock_socket.setblocking.return_value = None
        mock_socket.connect.return_value = None
        mock_socket.getsockopt.return_value = MIN_SEND_BUFFER_SIZE / 2

        datadog = DogStatsd()
        datadog.gauge('some value', 1)
        datadog.flush()

        # Sanity check
        mock_socket_create.assert_called_once_with(socket.AF_INET, socket.SOCK_DGRAM)

        mock_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET,
            socket.SO_SNDBUF,
            MIN_SEND_BUFFER_SIZE,
        )

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
        exec(source, {}, locals())

        loop = asyncio.get_event_loop()
        loop.run_until_complete(locals()['print_foo']())
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

    def test_flush(self):
        dogstatsd = DogStatsd(disable_buffering=False, telemetry_min_flush_interval=0)
        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket

        dogstatsd.increment('page.views')
        self.assertIsNone(fake_socket.recv(no_wait=True))
        dogstatsd.flush()
        self.assert_equal_telemetry('page.views:1|c\n', fake_socket.recv(2))

    def test_flush_interval(self):
        dogstatsd = DogStatsd(disable_buffering=False, flush_interval=1, telemetry_min_flush_interval=0)
        fake_socket = FakeSocket()
        dogstatsd.socket = fake_socket

        dogstatsd.increment('page.views')
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(0.3)
        self.assertIsNone(fake_socket.recv(no_wait=True))

        time.sleep(1)
        self.assert_equal_telemetry(
            'page.views:1|c\n',
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

        time.sleep(DEFAULT_FLUSH_INTERVAL)
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

    def test_batching_runtime_changes(self):
        dogstatsd = DogStatsd(
            disable_buffering=True,
            telemetry_min_flush_interval=0
        )
        dogstatsd.socket = FakeSocket()

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
        self.statsd.bytes_dropped = 5
        self.statsd.packets_sent = 6
        self.statsd.packets_dropped = 7

        self.statsd.open_buffer()
        self.statsd.gauge('page.views', 123)
        self.statsd.close_buffer()

        payload = 'page.views:123|g\n'
        telemetry = telemetry_metrics(metrics=2, events=2, service_checks=3, bytes_sent=4 + len(payload),
                                      bytes_dropped=5, packets_sent=7, packets_dropped=7)

        self.assert_equal_telemetry(payload, self.recv(2), telemetry=telemetry)

        self.assertEqual(0, self.statsd.metrics_count)
        self.assertEqual(0, self.statsd.events_count)
        self.assertEqual(0, self.statsd.service_checks_count)
        self.assertEqual(len(telemetry), self.statsd.bytes_sent)
        self.assertEqual(0, self.statsd.bytes_dropped)
        self.assertEqual(1, self.statsd.packets_sent)
        self.assertEqual(0, self.statsd.packets_dropped)

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
        dogstatsd.socket = FakeSocket()

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
