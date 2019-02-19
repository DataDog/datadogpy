# -*- coding: utf-8 -*-
"""
Tests for dogstatsd.py
"""
# stdlib
from collections import deque
import os
import socket
import time
import unittest

# 3p
from mock import (
    mock_open,
    patch,
)
from nose import (
    SkipTest,
    tools as t,
)

# datadog
from datadog import initialize, statsd
from datadog.dogstatsd.base import DogStatsd
from datadog.dogstatsd.context import TimedContextManagerDecorator
from datadog.util.compat import is_higher_py35, is_p3k
from tests.util.contextmanagers import preserve_environment_variable
from tests.unit.dogstatsd.fixtures import load_fixtures


class FakeSocket(object):
    """ A fake socket for testing. """

    def __init__(self):
        self.payloads = deque()

    def send(self, payload):
        if is_p3k():
            assert type(payload) == bytes
        else:
            assert type(payload) == str
        self.payloads.append(payload)

    def recv(self):
        try:
            return self.payloads.popleft().decode('utf-8')
        except IndexError:
            return None

    def close(self):
        pass

    def __repr__(self):
        return str(self.payloads)


class BrokenSocket(FakeSocket):

    def send(self, payload):
        raise socket.error("Socket error")


class TestDogStatsd(unittest.TestCase):

    def setUp(self):
        """
        Set up a default Dogstatsd instance and mock the proc filesystem.
        """
        #
        self.statsd = DogStatsd()
        self.statsd.socket = FakeSocket()

        # Mock the proc filesystem
        route_data = load_fixtures('route')
        self._procfs_mock = patch('datadog.util.compat.builtins.open', mock_open())
        self._procfs_mock.__enter__().return_value.readlines.return_value = route_data.split("\n")

    def tearDown(self):
        """
        Unmock the proc filesystem.
        """
        self._procfs_mock.__exit__()

    def recv(self):
        return self.statsd.socket.recv()

    def test_initialization(self):
        """
        `initialize` overrides `statsd` default instance attributes.
        """
        options = {
            'statsd_host': "myhost",
            'statsd_port': 1234
        }

        # Default values
        t.assert_equal(statsd.host, "localhost")
        t.assert_equal(statsd.port, 8125)

        # After initialization
        initialize(**options)
        t.assert_equal(statsd.host, "myhost")
        t.assert_equal(statsd.port, 1234)

        # Set `statsd` host to the system's default route
        initialize(statsd_use_default_route=True, **options)
        t.assert_equal(statsd.host, "172.17.0.1")
        t.assert_equal(statsd.port, 1234)

        # Add UNIX socket
        options['statsd_socket_path'] = '/var/run/dogstatsd.sock'
        initialize(**options)
        t.assert_equal(statsd.socket_path, options['statsd_socket_path'])
        t.assert_equal(statsd.host, None)
        t.assert_equal(statsd.port, None)

    def test_default_route(self):
        """
        Dogstatsd host can be dynamically set to the default route.
        """
        # Setup
        statsd = DogStatsd(use_default_route=True)

        # Assert
        t.assert_equal(statsd.host, "172.17.0.1")

    def test_set(self):
        self.statsd.set('set', 123)
        assert self.recv() == 'set:123|s'

    def test_gauge(self):
        self.statsd.gauge('gauge', 123.4)
        assert self.recv() == 'gauge:123.4|g'

    def test_counter(self):
        self.statsd.increment('page.views')
        t.assert_equal('page.views:1|c', self.recv())

        self.statsd.increment('page.views', 11)
        t.assert_equal('page.views:11|c', self.recv())

        self.statsd.decrement('page.views')
        t.assert_equal('page.views:-1|c', self.recv())

        self.statsd.decrement('page.views', 12)
        t.assert_equal('page.views:-12|c', self.recv())

    def test_histogram(self):
        self.statsd.histogram('histo', 123.4)
        t.assert_equal('histo:123.4|h', self.recv())

    def test_tagged_gauge(self):
        self.statsd.gauge('gt', 123.4, tags=['country:china', 'age:45', 'blue'])
        t.assert_equal('gt:123.4|g|#country:china,age:45,blue', self.recv())

    def test_tagged_counter(self):
        self.statsd.increment('ct', tags=[u'country:españa', 'red'])
        t.assert_equal(u'ct:1|c|#country:españa,red', self.recv())

    def test_tagged_histogram(self):
        self.statsd.histogram('h', 1, tags=['red'])
        t.assert_equal('h:1|h|#red', self.recv())

    def test_sample_rate(self):
        self.statsd.increment('c', sample_rate=0)
        assert not self.recv()
        for i in range(10000):
            self.statsd.increment('sampled_counter', sample_rate=0.3)
        self.assert_almost_equal(3000, len(self.statsd.socket.payloads), 150)
        t.assert_equal('sampled_counter:1|c|@0.3', self.recv())

    def test_tags_and_samples(self):
        for i in range(100):
            self.statsd.gauge('gst', 23, tags=["sampled"], sample_rate=0.9)

        def test_tags_and_samples(self):
            for i in range(100):
                self.statsd.gauge('gst', 23, tags=["sampled"], sample_rate=0.9)
            t.assert_equal('gst:23|g|@0.9|#sampled')

    def test_timing(self):
        self.statsd.timing('t', 123)
        t.assert_equal('t:123|ms', self.recv())

    def test_event(self):
        self.statsd.event('Title', u'L1\nL2', priority='low', date_happened=1375296969)
        t.assert_equal(u'_e{5,6}:Title|L1\\nL2|d:1375296969|p:low', self.recv())

        self.statsd.event('Title', u'♬ †øU †øU ¥ºu T0µ ♪',
                          aggregation_key='key', tags=['t1', 't2:v2'])
        t.assert_equal(u'_e{5,19}:Title|♬ †øU †øU ¥ºu T0µ ♪|k:key|#t1,t2:v2', self.recv())

    def test_event_constant_tags(self):
        self.statsd.constant_tags = ['bar:baz', 'foo']
        self.statsd.event('Title', u'L1\nL2', priority='low', date_happened=1375296969)
        t.assert_equal(u'_e{5,6}:Title|L1\\nL2|d:1375296969|p:low|#bar:baz,foo', self.recv())

        self.statsd.event('Title', u'♬ †øU †øU ¥ºu T0µ ♪',
                          aggregation_key='key', tags=['t1', 't2:v2'])
        t.assert_equal(u'_e{5,19}:Title|♬ †øU †øU ¥ºu T0µ ♪|k:key|#t1,t2:v2,bar:baz,foo', self.recv())

    def test_service_check(self):
        now = int(time.time())
        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            tags=['key1:val1', 'key2:val2'], timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪")
        t.assert_equal(
            u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#key1:val1,key2:val2|m:{2}'
            .format(self.statsd.WARNING, now, u"♬ †øU \\n†øU ¥ºu|m\: T0µ ♪"), self.recv())

    def test_service_check_constant_tags(self):
        self.statsd.constant_tags = ['bar:baz', 'foo']
        now = int(time.time())
        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪")
        t.assert_equal(
            u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#bar:baz,foo|m:{2}'
            .format(self.statsd.WARNING, now, u"♬ †øU \\n†øU ¥ºu|m\: T0µ ♪"), self.recv())

        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            tags=['key1:val1', 'key2:val2'], timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪")
        t.assert_equal(
            u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#key1:val1,key2:val2,bar:baz,foo|m:{2}'
            .format(self.statsd.WARNING, now, u"♬ †øU \\n†øU ¥ºu|m\: T0µ ♪"), self.recv())

    def test_metric_namespace(self):
        """
        Namespace prefixes all metric names.
        """
        self.statsd.namespace = "foo"
        self.statsd.gauge('gauge', 123.4)
        t.assert_equal('foo.gauge:123.4|g', self.recv())

    # Test Client level contant tags
    def test_gauge_constant_tags(self):
        self.statsd.constant_tags=['bar:baz', 'foo']
        self.statsd.gauge('gauge', 123.4)
        assert self.recv() == 'gauge:123.4|g|#bar:baz,foo'

    def test_counter_constant_tag_with_metric_level_tags(self):
        self.statsd.constant_tags=['bar:baz', 'foo']
        self.statsd.increment('page.views', tags=['extra'])
        t.assert_equal('page.views:1|c|#extra,bar:baz,foo', self.recv())

    def test_gauge_constant_tags_with_metric_level_tags_twice(self):
        metric_level_tag = ['foo:bar']
        self.statsd.constant_tags=['bar:baz']
        self.statsd.gauge('gauge', 123.4, tags=metric_level_tag)
        assert self.recv() == 'gauge:123.4|g|#foo:bar,bar:baz'

        # sending metrics multiple times with same metric-level tags
        # should not duplicate the tags being sent
        self.statsd.gauge('gauge', 123.4, tags=metric_level_tag)
        assert self.recv() == 'gauge:123.4|g|#foo:bar,bar:baz'

    @staticmethod
    def assert_almost_equal(a, b, delta):
        assert 0 <= abs(a - b) <= delta, "%s - %s not within %s" % (a, b, delta)

    def test_socket_error(self):
        self.statsd.socket = BrokenSocket()
        self.statsd.gauge('no error', 1)
        assert True, 'success'

    def test_timed(self):
        """
        Measure the distribution of a function's run time.
        """
        # In seconds
        @self.statsd.timed('timed.test')
        def func(a, b, c=1, d=1):
            """docstring"""
            time.sleep(0.5)
            return (a, b, c, d)

        t.assert_equal('func', func.__name__)
        t.assert_equal('docstring', func.__doc__)

        result = func(1, 2, d=3)
        # Assert it handles args and kwargs correctly.
        t.assert_equal(result, (1, 2, 1, 3))

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

        # Repeat, force timer value in milliseconds
        @self.statsd.timed('timed.test', use_ms=True)
        def func(a, b, c=1, d=1):
            """docstring"""
            time.sleep(0.5)
            return (a, b, c, d)

        func(1, 2, d=3)

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed.test', name)
        self.assert_almost_equal(500, float(value), 100)

    def test_timed_in_ms(self):
        """
        Timed value is reported in ms when statsd.use_ms is True.
        """
        # Arm statsd to use_ms
        self.statsd.use_ms = True

        # Sample a function run time
        @self.statsd.timed('timed.test')
        def func(a, b, c=1, d=1):
            """docstring"""
            time.sleep(0.5)
            return (a, b, c, d)

        func(1, 2, d=3)

        # Assess the packet
        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed.test', name)
        self.assert_almost_equal(500, float(value), 100)

        # Repeat, force timer value in seconds
        @self.statsd.timed('timed.test', use_ms=False)
        def func(a, b, c=1, d=1):
            """docstring"""
            time.sleep(0.5)
            return (a, b, c, d)

        func(1, 2, d=3)

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_no_metric(self, ):
        """
        Test using a decorator without providing a metric.
        """

        @self.statsd.timed()
        def func(a, b, c=1, d=1):
            """docstring"""
            time.sleep(0.5)
            return (a, b, c, d)

        t.assert_equal('func', func.__name__)
        t.assert_equal('docstring', func.__doc__)

        result = func(1, 2, d=3)
        # Assert it handles args and kwargs correctly.
        t.assert_equal(result, (1, 2, 1, 3))

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('tests.unit.dogstatsd.test_statsd.func', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_coroutine(self):
        """
        Measure the distribution of a coroutine function's run time.

        Warning: Python > 3.5 only.
        """
        if not is_higher_py35():
            raise SkipTest(
                u"Coroutines are supported on Python 3.5 or higher."
            )

        import asyncio

        @self.statsd.timed('timed.test')
        @asyncio.coroutine
        def print_foo():
            """docstring"""
            time.sleep(0.5)
            print("foo")

        loop = asyncio.get_event_loop()
        loop.run_until_complete(print_foo())
        loop.close()

        # Assert
        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_context(self):
        """
        Measure the distribution of a context's run time.
        """
        # In seconds
        with self.statsd.timed('timed_context.test') as timer:
            t.assert_is_instance(timer, TimedContextManagerDecorator)
            time.sleep(0.5)

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed_context.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)
        self.assert_almost_equal(0.5, timer.elapsed, 0.1)

        # In milliseconds
        with self.statsd.timed('timed_context.test', use_ms=True) as timer:
            time.sleep(0.5)

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed_context.test', name)
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
        t.assert_raises(ContextException, func, self)

        # Ensure the timing was recorded.
        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed_context.test.exception', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_context_no_metric_exception(self):
        """Test that an exception occurs if using a context manager without a metric."""

        def func(self):
            with self.statsd.timed():
                time.sleep(0.5)

        # Ensure the exception was raised.
        t.assert_raises(TypeError, func, self)

        # Ensure the timing was recorded.
        packet = self.recv()
        t.assert_equal(packet, None)

    def test_timed_start_stop_calls(self):
        # In seconds
        timer = self.statsd.timed('timed_context.test')
        timer.start()
        time.sleep(0.5)
        timer.stop()

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed_context.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

        # In milliseconds
        timer = self.statsd.timed('timed_context.test', use_ms=True)
        timer.start()
        time.sleep(0.5)
        timer.stop()

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed_context.test', name)
        self.assert_almost_equal(500, float(value), 100)

    def test_batched(self):
        self.statsd.open_buffer()
        self.statsd.gauge('page.views', 123)
        self.statsd.timing('timer', 123)
        self.statsd.close_buffer()

        t.assert_equal('page.views:123|g\ntimer:123|ms', self.recv())

    def test_context_manager(self):
        fake_socket = FakeSocket()
        with DogStatsd() as statsd:
            statsd.socket = fake_socket
            statsd.gauge('page.views', 123)
            statsd.timing('timer', 123)

        t.assert_equal('page.views:123|g\ntimer:123|ms', fake_socket.recv())

    def test_batched_buffer_autoflush(self):
        fake_socket = FakeSocket()
        with DogStatsd() as statsd:
            statsd.socket = fake_socket
            for i in range(51):
                statsd.increment('mycounter')
            t.assert_equal('\n'.join(['mycounter:1|c' for i in range(50)]), fake_socket.recv())

        t.assert_equal('mycounter:1|c', fake_socket.recv())

    def test_module_level_instance(self):
        t.assert_true(isinstance(statsd, DogStatsd))

    def test_instantiating_does_not_connect(self):
        dogpound = DogStatsd()
        t.assert_equal(None, dogpound.socket)

    def test_accessing_socket_opens_socket(self):
        dogpound = DogStatsd()
        try:
            t.assert_not_equal(None, dogpound.get_socket())
        finally:
            dogpound.socket.close()

    def test_accessing_socket_multiple_times_returns_same_socket(self):
        dogpound = DogStatsd()
        fresh_socket = FakeSocket()
        dogpound.socket = fresh_socket
        t.assert_equal(fresh_socket, dogpound.get_socket())
        t.assert_not_equal(FakeSocket(), dogpound.get_socket())

    def test_tags_from_environment(self):
        with preserve_environment_variable('DATADOG_TAGS'):
            os.environ['DATADOG_TAGS'] = 'country:china,age:45,blue'
            statsd = DogStatsd()
        statsd.socket = FakeSocket()
        statsd.gauge('gt', 123.4)
        t.assert_equal('gt:123.4|g|#country:china,age:45,blue', statsd.socket.recv())

    def test_tags_from_environment_and_constant(self):
        with preserve_environment_variable('DATADOG_TAGS'):
           os.environ['DATADOG_TAGS'] = 'country:china,age:45,blue'
           statsd = DogStatsd(constant_tags=['country:canada', 'red'])
        statsd.socket = FakeSocket()
        statsd.gauge('gt', 123.4)
        t.assert_equal('gt:123.4|g|#country:canada,red,country:china,age:45,blue', statsd.socket.recv())

    def test_gauge_doesnt_send_None(self):
        self.statsd.gauge('metric', None)
        assert self.recv() is None

    def test_increment_doesnt_send_None(self):
        self.statsd.increment('metric', None)
        assert self.recv() is None

    def test_decrement_doesnt_send_None(self):
        self.statsd.decrement('metric', None)
        assert self.recv() is None

    def test_timing_doesnt_send_None(self):
        self.statsd.timing('metric', None)
        assert self.recv() is None

    def test_histogram_doesnt_send_None(self):
        self.statsd.histogram('metric', None)
        assert self.recv() is None
