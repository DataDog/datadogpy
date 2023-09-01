import itertools
import socket
from threading import Thread

import pytest

from datadog.dogstatsd.base import DogStatsd

@pytest.mark.parametrize(
    "disable_background_sender, disable_buffering, wait_for_pending, socket_timeout",
    list(itertools.product([True, False], [True, False], [True, False], [0, 1])),
)
def test_sender_mode(disable_background_sender, disable_buffering, wait_for_pending, socket_timeout):
    # Test basic sender operation with an assortment of options
    foo, bar = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM, 0)
    statsd = DogStatsd(
        telemetry_min_flush_interval=0,
        disable_background_sender=disable_background_sender,
        disable_buffering=disable_buffering,
        socket_timeout=socket_timeout,
    )

    statsd.socket = foo
    statsd._reset_telemetry()

    def reader_thread():
        msg = bar.recv(8192)
        assert msg == b"test.metric:1|c\n"

    t = Thread(target=reader_thread, name="test_sender_mode/reader_thread")
    t.daemon = True
    t.start()

    statsd.increment("test.metric")
    if wait_for_pending:
        statsd.wait_for_pending()

    t.join(timeout=10)
    assert not t.is_alive()

def test_set_socket_timeout():
    statsd = DogStatsd(socket_timeout=0)
    assert statsd.get_socket().gettimeout() == 0
    statsd.set_socket_timeout(1)
    assert statsd.get_socket().gettimeout() == 1
    statsd.close_socket()
    assert statsd.get_socket().gettimeout() == 1

