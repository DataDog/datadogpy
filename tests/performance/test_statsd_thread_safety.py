import time
import six
import threading
from collections import deque
from nose import tools as t

from datadog.dogstatsd.base import DogStatsd


class FakeSocket(object):
    """ A fake socket for testing. """

    def __init__(self):
        self.payloads = deque()

    def send(self, payload):
        assert type(payload) == six.binary_type
        self.payloads.append(payload)

    def recv(self):
        try:
            return self.payloads
        except IndexError:
            return None

    def __repr__(self):
        return str(self.payloads)


class DogstatsdTest(DogStatsd):
    def send_metrics(self):
        self.increment('whatever')


class TestDogStatsdThreadSafety(object):

    def setUp(self):
        self.socket = FakeSocket()

    def recv(self):
        return self.socket.recv()

    def test_send_metrics(self):
        statsd = DogstatsdTest()
        statsd.socket = self.socket
        for _ in range(10000):
            threading.Thread(target=statsd.send_metrics).start()
        time.sleep(1)
        t.assert_equal(10000, len(self.recv()), len(self.recv()))

    def test_send_batch_metrics(self):
        with DogstatsdTest() as batch:
            batch.socket = self.socket
            for _ in range(10000):
                threading.Thread(target=batch.send_metrics).start()
        time.sleep(1)
        payload = map(lambda x: x.split("\n"), self.recv())
        payload = reduce(lambda prev, ele: prev + ele, payload, [])
        t.assert_equal(10001, len(payload), len(payload))
