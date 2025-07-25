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
from datadog.dogstatsd.base import DEFAULT_BUFFERING_FLUSH_INTERVAL, DogStatsd, MIN_SEND_BUFFER_SIZE, UDP_OPTIMAL_PAYLOAD_LENGTH, UDS_OPTIMAL_PAYLOAD_LENGTH
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


def telemetry_metrics(metrics=1, events=0, service_checks=0, bytes_sent=0, bytes_dropped_writer=0, packets_sent=1, packets_dropped_writer=0, transport="udp", tags="", bytes_dropped_queue=0, packets_dropped_queue=0):
    tags = "," + tags if tags else ""

    return "\n".join([
        "datadog.dogstatsd.client.metrics:{}|c|#client:py,client_version:{},client_transport:{}{}".format(metrics, version, transport, tags),
        "datadog.dogstatsd.client.events:{}|c|#client:py,client_version:{},client_transport:{}{}".format(events, version, transport, tags),
        "datadog.dogstatsd.client.service_checks:{}|c|#client:py,client_version:{},client_transport:{}{}".format(service_checks, version, transport, tags),
        "datadog.dogstatsd.client.bytes_sent:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_sent, version, transport, tags),
        "datadog.dogstatsd.client.bytes_dropped:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_dropped_queue + bytes_dropped_writer, version, transport, tags),
        "datadog.dogstatsd.client.bytes_dropped_queue:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_dropped_queue, version, transport, tags),
        "datadog.dogstatsd.client.bytes_dropped_writer:{}|c|#client:py,client_version:{},client_transport:{}{}".format(bytes_dropped_writer, version, transport, tags),
        "datadog.dogstatsd.client.packets_sent:{}|c|#client:py,client_version:{},client_transport:{}{}".format(packets_sent, version, transport, tags),
        "datadog.dogstatsd.client.packets_dropped:{}|c|#client:py,client_version:{},client_transport:{}{}".format(packets_dropped_queue + packets_dropped_writer, version, transport, tags),
        "datadog.dogstatsd.client.packets_dropped_queue:{}|c|#client:py,client_version:{},client_transport:{}{}".format(packets_dropped_queue, version, transport, tags),
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

    def test_sender_calls_task_done(self):
        statsd = DogStatsd(disable_background_sender=False)
        statsd.socket = OverflownSocket()
        statsd.increment("test.metric")
        statsd.wait_for_pending()

    def test_sender_queue_no_timeout(self):
        statsd = DogStatsd(disable_background_sender=False, sender_queue_timeout=None)

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