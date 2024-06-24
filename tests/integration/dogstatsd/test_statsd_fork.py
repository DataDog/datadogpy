import os
import itertools
import socket

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
    statsd.post_fork = track(statsd.post_fork)

    pid = os.fork()
    if pid == 0:
        os._exit(0)

    assert pid > 0
    os.waitpid(pid, 0)

    assert len(tracker) == 2
