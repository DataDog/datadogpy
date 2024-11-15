from contextlib import closing
import itertools
import os
import shutil
import socket
import struct
import tempfile
from threading import Thread
import uuid

import pytest

from datadog.dogstatsd.base import DogStatsd

@pytest.mark.parametrize(
    "disable_background_sender, disable_buffering, wait_for_pending, socket_timeout, stop, socket_kind",
    list(itertools.product([True, False], [True, False], [True, False], [0, 1], [True, False], [socket.SOCK_DGRAM, socket.SOCK_STREAM])),
)
def test_sender_mode(disable_background_sender, disable_buffering, wait_for_pending, socket_timeout, stop, socket_kind):
    # Test basic sender operation with an assortment of options
    foo, bar = socket.socketpair(socket.AF_UNIX, socket_kind, 0)
    statsd = DogStatsd(
        telemetry_min_flush_interval=0,
        disable_background_sender=disable_background_sender,
        disable_buffering=disable_buffering,
        socket_timeout=socket_timeout,
    )

    statsd.socket = foo
    statsd._reset_telemetry()

    def reader_thread():
        if socket_kind == socket.SOCK_DGRAM:
            msg = bar.recv(8192)
        else:
            size = struct.unpack("<I", bar.recv(4))[0]
            msg = bar.recv(size)
        assert msg == b"test.metric:1|c\n"

    t = Thread(target=reader_thread, name="test_sender_mode/reader_thread")
    t.daemon = True
    t.start()

    statsd.increment("test.metric")
    if wait_for_pending:
        statsd.wait_for_pending()

    if stop:
        statsd.stop()

    t.join(timeout=10)
    assert not t.is_alive()

def test_set_socket_timeout():
    statsd = DogStatsd(socket_timeout=0)
    assert statsd.get_socket().gettimeout() == 0
    statsd.set_socket_timeout(1)
    assert statsd.get_socket().gettimeout() == 1
    statsd.close_socket()
    assert statsd.get_socket().gettimeout() == 1

def test_stream_cleanup():
    foo, _ = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM, 0)

    foo.settimeout(0)
    statsd = DogStatsd(disable_buffering=True)
    statsd.socket = foo
    statsd.increment("test", 1)
    statsd.increment("test", 1)
    statsd.increment("test", 1)
    assert statsd.socket is not None

    foo.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1) # different os's have different mins, e.g. this sets the buffer size to 2304 on certain linux variants

    with pytest.raises(socket.error):
        foo.sendall(os.urandom(5000)) # pre-emptively clog the buffer

    statsd.increment("test", 1)

    assert statsd.socket is None

@pytest.mark.parametrize(
    "disable_background_sender, disable_buffering",
    list(itertools.product([True, False], [True, False])),
)
def test_fork_hooks(disable_background_sender, disable_buffering):
    statsd = DogStatsd(
        telemetry_min_flush_interval=0,
        disable_background_sender=disable_background_sender,
        disable_buffering=disable_buffering,
    )

    foo, bar = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM, 0)
    statsd.socket = foo

    statsd.increment("test.metric")

    assert disable_buffering or statsd._flush_thread.is_alive()
    assert disable_background_sender or statsd._sender_thread.is_alive()

    statsd.pre_fork()

    assert statsd._flush_thread is None
    assert statsd._sender_thread is None
    assert statsd._queue is None or statsd._queue.empty()
    assert len(statsd._buffer) == 0

    statsd.post_fork_parent()

    assert disable_buffering or statsd._flush_thread.is_alive()
    assert disable_background_sender or statsd._sender_thread.is_alive()

    foo.close()
    bar.close()


def test_buffering_with_context():
    statsd = DogStatsd(
        telemetry_min_flush_interval=0,
        disable_buffering=False,
    )

    foo, bar = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM, 0)
    statsd.socket = foo

    statsd.increment("first")
    with statsd: # should not erase previously buffered metrics
        pass

    bar.settimeout(5)
    msg = bar.recv(8192)
    assert msg == b"first:1|c\n"

@pytest.fixture()
def socket_dir():
    tempdir = tempfile.mkdtemp()
    yield tempdir
    shutil.rmtree(tempdir)

@pytest.mark.parametrize(
        "socket_prefix, socket_kind, success",
        [
            ("", socket.SOCK_DGRAM, True),
            ("", socket.SOCK_STREAM, True),
            ("unix://", socket.SOCK_DGRAM, True),
            ("unix://", socket.SOCK_STREAM, True),
            ("unixstream://", socket.SOCK_DGRAM, False),
            ("unixstream://", socket.SOCK_STREAM, True),
            ("unixgram://", socket.SOCK_DGRAM, True),
            ("unixgram://", socket.SOCK_STREAM, False)
        ]
)
def test_socket_connection(socket_dir, socket_prefix, socket_kind, success):
    socket_path = os.path.join(socket_dir, str(uuid.uuid1()) + ".sock")
    listener_socket = socket.socket(socket.AF_UNIX, socket_kind)
    listener_socket.bind(socket_path)

    if socket_kind == socket.SOCK_STREAM:
        listener_socket.listen(1)

    with closing(listener_socket):
        statsd = DogStatsd(
            socket_path = socket_prefix + socket_path
        )

        if success:
            assert statsd.get_socket() is not None
        else:
            with pytest.raises(socket.error):
                statsd.get_socket()
