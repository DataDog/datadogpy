import os
import itertools
import socket
import threading

import mock
import pytest

from datadog.dogstatsd.base import DogStatsd, SUPPORTS_FORKING


@pytest.mark.parametrize(
    "disable_background_sender, disable_buffering",
    list(itertools.product([True, False], [True, False])),
)
def test_register_at_fork(disable_background_sender, disable_buffering):
    if not SUPPORTS_FORKING:
        pytest.skip("os.register_at_fork is required for this test")

    statsd = DogStatsd(
        telemetry_min_flush_interval=0,
        disable_background_sender=disable_background_sender,
        disable_buffering=disable_buffering,
    )

    tracker = {}

    def track(method):
        def inner(*args, **kwargs):
            method(*args, **kwargs)
            tracker[method] = True

        return inner

    statsd.pre_fork = track(statsd.pre_fork)
    statsd.post_fork_parent = track(statsd.post_fork_parent)

    pid = os.fork()
    if pid == 0:
        os._exit(0)

    assert pid > 0
    os.waitpid(pid, 0)

    assert len(tracker) == 2


@pytest.mark.parametrize(
    "disable_background_sender, disable_buffering",
    list(itertools.product([True, False], [True, False])),
)
def test_post_fork_does_not_log(disable_background_sender, disable_buffering):
    """
    post_fork_child/post_fork_parent run from an os.register_at_fork(after_in_child=...)
    callback, where logging.Logger.debug() is not safe: it can block acquiring a
    StreamHandler's own lock, left permanently locked in the child if some other thread
    held it at the instant of fork (no thread survives fork to release it there). Neither
    should log anything, regardless of config, so there's nothing here for that lock to
    block on.
    """
    if not SUPPORTS_FORKING:
        pytest.skip("os.register_at_fork is required for this test")

    statsd = DogStatsd(
        telemetry_min_flush_interval=0,
        disable_background_sender=disable_background_sender,
        disable_buffering=disable_buffering,
    )
    try:
        with mock.patch("datadog.dogstatsd.base.log") as log:
            statsd.pre_fork()
            statsd.post_fork_parent()
            log.debug.assert_not_called()

            statsd.pre_fork()
            statsd.post_fork_child()
            log.debug.assert_not_called()
    finally:
        statsd.stop()


def sender_a(statsd, running):
    while running[0]:
        statsd.gauge("spam", 1)


def sender_b(statsd, signal):
    while running[0]:
        with statsd:
            statsd.gauge("spam", 1)

@pytest.mark.parametrize(
    "disable_background_sender, disable_buffering, sender",
    list(itertools.product([True, False], [True, False], [sender_a, sender_b])),
)
def test_fork_with_thread(disable_background_sender, disable_buffering, sender):
    if not SUPPORTS_FORKING:
        pytest.skip("os.register_at_fork is required for this test")

    statsd = DogStatsd(
        telemetry_min_flush_interval=0,
        disable_background_sender=disable_background_sender,
        disable_buffering=disable_buffering,
    )

    sender = None
    try:
        sender_running = [True]
        sender = threading.Thread(target=sender, args=(statsd, sender_running))
        sender.daemon = True
        sender.start()

        pid = os.fork()
        if pid == 0:
            os._exit(42)

        assert pid > 0
        (_, status) = os.waitpid(pid, 0)

        assert os.WEXITSTATUS(status) == 42
    finally:
        statsd.stop()
        if sender:
            sender_running[0] = False
            sender.join()
