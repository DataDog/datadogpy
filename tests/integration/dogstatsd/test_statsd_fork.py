import os
import itertools
import socket
import threading
import logging

import pytest

from datadog.dogstatsd.base import DogStatsd, SUPPORTS_FORKING

logging.getLogger("datadog.dogstatsd").setLevel(logging.FATAL)

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


def sender_a(statsd, running):
    while running[0]:
        statsd.gauge("spam", 1)


def sender_b(statsd, running):
    while running[0]:
        with statsd:
            statsd.gauge("spam", 1)

@pytest.mark.parametrize(
    "disable_background_sender, disable_buffering, sender_fn",
    list(itertools.product([True, False], [True, False], [sender_a, sender_b])),
)
def test_fork_with_thread(disable_background_sender, disable_buffering, sender_fn):
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
        sender = threading.Thread(target=sender_fn, args=(statsd, sender_running))
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
