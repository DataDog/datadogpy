# -*- coding: utf-8 -*-
"""
Tests for dogstatsd.py
"""

from collections import deque
import six
import socket
import time

from nose import tools as t

from datadog.dogstatsd.base import DogStatsd
from datadog import initialize, statsd


class FakeSocket(object):
    """ A fake socket for testing. """

    def __init__(self):
        self.payloads = deque()

    def send(self, payload):
        assert type(payload) == six.binary_type
        self.payloads.append(payload)

    def recv(self):
        try:
            return self.payloads.popleft().decode('utf-8')
        except IndexError:
            return None

    def __repr__(self):
        return str(self.payloads)


class BrokenSocket(FakeSocket):

    def send(self, payload):
        raise socket.error("Socket error")


class TestDogStatsd(object):

    def setUp(self):
        self.statsd = DogStatsd()
        self.statsd.socket = FakeSocket()

    def recv(self):
        return self.statsd.socket.recv()

    def test_initialization(self):
        options = {
            'statsd_host': "myhost",
            'statsd_port': 1234
        }

        t.assert_equal(statsd.host, "localhost")
        t.assert_equal(statsd.port, 8125)
        initialize(**options)
        t.assert_equal(statsd.host, "myhost")
        t.assert_equal(statsd.port, 1234)

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
        self.statsd.increment('ct', tags=['country:canada', 'red'])
        t.assert_equal('ct:1|c|#country:canada,red', self.recv())

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

    def test_service_check(self):
        now = int(time.time())
        self.statsd.service_check(
            'my_check.name', self.statsd.WARNING,
            tags=['key1:val1', 'key2:val2'], timestamp=now,
            hostname='i-abcd1234', message=u"♬ †øU \n†øU ¥ºu|m: T0µ ♪")
        t.assert_equal(
            u'_sc|my_check.name|{0}|d:{1}|h:i-abcd1234|#key1:val1,key2:val2|m:{2}'
            .format(self.statsd.WARNING, now, u"♬ †øU \\n†øU ¥ºu|m\: T0µ ♪"), self.recv())

    @staticmethod
    def assert_almost_equal(a, b, delta):
        assert 0 <= abs(a - b) <= delta, "%s - %s not within %s" % (a, b, delta)

    def test_socket_error(self):
        self.statsd.socket = BrokenSocket()
        self.statsd.gauge('no error', 1)
        assert True, 'success'

    def test_timed(self):

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

    def test_timed_context(self):
        with self.statsd.timed('timed_context.test'):
            time.sleep(0.5)

        packet = self.recv()
        name_value, type_ = packet.split('|')
        name, value = name_value.split(':')

        t.assert_equal('ms', type_)
        t.assert_equal('timed_context.test', name)
        self.assert_almost_equal(0.5, float(value), 0.1)

    def test_timed_context_exception(self):
        """Test that an exception bubbles out of the context manager."""
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


if __name__ == '__main__':
    statsd = statsd
    while True:
        statsd.gauge('test.gauge', 1)
        statsd.increment('test.count', 2)
        time.sleep(0.05)
