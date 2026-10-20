# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc.
"""Property-based / fuzz tests for the #987 shutdown-bounding work.

Companion to test_sender_queue_fuzz.py, which fuzzes SenderQueue in
isolation. This file fuzzes the machinery #987 added on top of it, all of
which specifically needs real thread interleaving to exercise -- a
synchronous/single-threaded model can't reach any of it:

  - SenderQueue.close(): a put() genuinely blocked waiting for room, woken
    from a different thread.
  - DogStatsd._stop_sender_thread()'s deadline: stop(timeout) staying
    bounded even with a producer wedged inside put() and/or the sender
    thread wedged inside a "connection" that never resolves.
  - The _send_to_server() / _stop_sender_thread() race close() and sender
    lifecycle state transitions together are meant to close: a producer
    thread racing a shutdown must never land behind Stop and vanish with no
    accounting.
  - The retry-deadline abandon path: a payload stuck retrying a connection
    failure forever must still get counted (packets_dropped_writer) and
    still make stop() report False, not True.
  - The sender thread's own per-item bookkeeping in _sender_main_loop
    (success-path state transitions, retry/backoff waits) must never be
    blocked behind a producer that is itself blocked waiting for room
    inside SenderQueue.put() -- a deadlock distinct from (and not covered
    by) the stop()/close() scenarios above, since it can happen during
    completely ordinary operation with no shutdown involved at all.
  - stop() must stay bounded even with a large pile of producers
    genuinely parked inside SenderQueue.put()'s own wait-for-room, not
    just a couple of them racing by chance -- ruling out a two-lock
    deadlock between _buffer_lock and SenderQueue's own lock (nested the
    other way, for Stop insertion) at scale.

Same opt-in policy as test_sender_queue_fuzz.py: skipped entirely (not
failed) without hypothesis, and Python 3.6+ only. See tox.ini's
[testenv:fuzz].
"""
from __future__ import absolute_import

import os
import random
import sys
import threading
import time

# Make `import datadog...` below resolve to this checkout's source tree
# rather than to an unrelated `datadog` package that happens to be
# installed elsewhere on sys.path (e.g. a stale non-editable install
# predating sender_queue.py). Normal invocation via pytest/tox already puts
# the repo root ahead of site-packages, but this file also supports being
# run directly as a script (see the __main__ block at the bottom), where
# sys.path[0] is this file's own directory instead of the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pytest  # noqa: E402

if sys.version_info[0] < 3:
    pytest.skip("hypothesis fuzz suite requires Python 3", allow_module_level=True)

hypothesis = pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402
from unittest.mock import patch  # noqa: E402

from datadog.dogstatsd.base import DogStatsd  # noqa: E402
from datadog.dogstatsd.sender_queue import SenderQueue  # noqa: E402


# ---------------------------------------------------------------------------
# 1. SenderQueue.close() must wake every put() genuinely blocked for room,
#    regardless of put_timeout, maxsize, or how many producers are stuck.
# ---------------------------------------------------------------------------
@given(
    maxsize=st.integers(min_value=1, max_value=6),
    num_producers=st.integers(min_value=1, max_value=10),
    put_timeout=st.one_of(st.none(), st.floats(min_value=10.0, max_value=120.0)),
    delay_before_close=st.floats(min_value=0.0, max_value=0.05),
)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_close_unblocks_every_producer_wedged_in_put(maxsize, num_producers, put_timeout, delay_before_close):
    # No consumer ever drains this queue (nothing calls get()), so close()
    # cannot make room appear -- it only stops a put() from *waiting* for
    # room. Every put() that still finds the queue full when it (eventually)
    # proceeds therefore evicts the oldest entry to make room for itself
    # (the same drop-oldest path put_timeout=0 always takes): qsize() and
    # _unfinished_tasks stay pinned at maxsize throughout, and exactly one
    # eviction fires per producer -- that is the invariant this test checks,
    # not "the queue grew", which it structurally can't without a consumer.
    dropped_full = []
    queue = SenderQueue(
        maxsize=maxsize,
        expiry_seconds=10000.0,
        on_drop_queue_full=dropped_full.append,
        on_drop_expired=lambda item: None,
        put_timeout=put_timeout,
    )
    for i in range(maxsize):
        queue.put("seed-%d\n" % i)
    assert queue.qsize() == maxsize

    reached_wait = threading.Event()
    reached_count = [0]
    count_lock = threading.Lock()

    def producer(n):
        with count_lock:
            reached_count[0] += 1
            if reached_count[0] == num_producers:
                reached_wait.set()
        queue.put("extra-%d\n" % n)  # queue is full: this blocks until close()

    threads = [threading.Thread(target=producer, args=(n,)) for n in range(num_producers)]
    for t in threads:
        t.start()

    # Best-effort: increase the odds every producer is actually inside its
    # wait before close() runs. Not required for correctness -- close() must
    # also cover a producer that hasn't reached the wait loop yet.
    reached_wait.wait(2.0)
    time.sleep(delay_before_close)

    t0 = time.time()
    queue.close()

    for t in threads:
        t.join(timeout=10.0)
    elapsed = time.time() - t0

    still_alive = [t for t in threads if t.is_alive()]
    assert not still_alive, (
        "%d/%d producer(s) still blocked %.2fs after close() "
        "(maxsize=%s put_timeout=%s)" % (len(still_alive), num_producers, elapsed, maxsize, put_timeout)
    )
    assert elapsed < 10.0

    # The queue never had anywhere to grow to: it stays exactly full, one
    # eviction per producer, and nothing left dangling as "in flight" (no
    # get() was ever called).
    assert queue.qsize() == maxsize
    assert queue._unfinished_tasks == maxsize
    assert len(dropped_full) == num_producers
    assert len(queue._in_flight) == 0


# ---------------------------------------------------------------------------
# 2. DogStatsd.stop(timeout) must stay bounded (roughly to `timeout`, never
#    to "however long a wedged producer/sender happens to take") even under
#    concurrent producers actively racing the shutdown -- fuzzing exactly
#    the combination the #987 fix (SenderQueue.close() + sender-state-gated
#    _send_to_server() admission checks) targets.
# ---------------------------------------------------------------------------
@given(
    maxsize=st.integers(min_value=0, max_value=4),
    sender_queue_timeout=st.one_of(st.just(0), st.none(), st.floats(min_value=5.0, max_value=60.0)),
    stop_timeout=st.floats(min_value=0.05, max_value=1.0),
    num_racing_producers=st.integers(min_value=0, max_value=6),
    socket_connect_retry=st.booleans(),
    seed=st.integers(min_value=0),
)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_stop_timeout_bounded_with_wedged_sender_and_racing_producers(
    maxsize, sender_queue_timeout, stop_timeout, num_racing_producers, socket_connect_retry, seed
):
    rng = random.Random(seed)
    statsd = DogStatsd(
        disable_background_sender=False,
        disable_buffering=True,
        disable_aggregation=True,
        disable_telemetry=True,
        sender_queue_size=maxsize,
        sender_queue_timeout=sender_queue_timeout,
        socket_connect_retry=socket_connect_retry,
        track_instance=False,
    )
    release = threading.Event()

    def blocking_xmit(packet, queue_mode=False):
        # Never fails -- release() lets it "succeed" so nothing here relies
        # on retry logic; this test's whole point is the wedge + race, not
        # the connect-failure path (that's covered by test 3 below).
        release.wait(30.0)
        return True

    statsd._xmit_packet_with_telemetry = blocking_xmit
    statsd._send_to_server("wedge:1|c")  # the sender picks this up and wedges

    exceptions = []

    def guarded(fn):
        try:
            fn()
        except Exception as exc:  # the whole point: this must never happen
            exceptions.append(exc)

    racer_threads = [
        threading.Thread(target=guarded, args=(lambda: statsd._send_to_server("racer:1|c"),))
        for _ in range(num_racing_producers)
    ]
    for t in racer_threads:
        t.start()
    time.sleep(rng.uniform(0.0, 0.05))  # jitter when stop() joins the race

    result = {}
    t0 = time.time()

    def call_stop():
        guarded(lambda: result.__setitem__("value", statsd.stop(stop_timeout)))

    stopper = threading.Thread(target=call_stop)
    stopper.start()

    slack = stop_timeout + 5.0
    stopper.join(timeout=slack)
    elapsed = time.time() - t0

    release.set()  # unwedge regardless of outcome so cleanup can't hang
    for t in racer_threads:
        t.join(timeout=5.0)
    stopper.join(timeout=5.0)

    assert not stopper.is_alive(), (
        "stop(%.3f) did not return within %.3fs slack (elapsed=%.3f, maxsize=%s, "
        "sender_queue_timeout=%s, racers=%d, retry=%s)"
        % (stop_timeout, slack, elapsed, maxsize, sender_queue_timeout, num_racing_producers, socket_connect_retry)
    )
    assert elapsed < slack
    assert not exceptions, "unexpected exception(s) from producer/stop threads: %r" % (exceptions,)
    # The sender was genuinely still wedged the whole time, so this can only
    # be a timeout (False), never a false "drained" success.
    assert result.get("value") is False


# ---------------------------------------------------------------------------
# 3. Nothing sent through DogStatsd ever silently vanishes: every attempt is
#    either delivered or accounted for in a drop counter, under concurrent
#    producers hammering a real (non-wedged) sender.
# ---------------------------------------------------------------------------
@given(
    num_producers=st.integers(min_value=1, max_value=6),
    items_per_producer=st.integers(min_value=1, max_value=25),
    maxsize=st.integers(min_value=0, max_value=8),
)
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_every_metric_is_delivered_or_accounted_under_concurrent_producers(num_producers, items_per_producer, maxsize):
    sent = []
    sent_lock = threading.Lock()

    def fake_xmit(packet, queue_mode=False):
        with sent_lock:
            sent.append(packet)
        return True

    statsd = DogStatsd(
        disable_background_sender=False,
        disable_buffering=True,
        disable_aggregation=True,
        disable_telemetry=True,
        sender_queue_size=maxsize,
        sender_queue_timeout=0,  # default: never blocks a producer
        track_instance=False,
    )
    statsd._xmit_packet_with_telemetry = fake_xmit

    total = num_producers * items_per_producer

    def produce(n):
        for i in range(n):
            statsd._send_to_server("m-%d:1|c" % i)

    threads = [threading.Thread(target=produce, args=(items_per_producer,)) for _ in range(num_producers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)
        assert not t.is_alive(), "producer thread did not finish in time"

    assert statsd.wait_for_pending(30.0) is True, "queue never fully drained"

    accounted = (
        len(sent)
        + statsd.packets_dropped_queue
        + statsd.packets_dropped_expired
        + statsd.packets_dropped_writer
    )
    assert accounted == total, (
        "sent=%d dropped_queue=%d dropped_expired=%d dropped_writer=%d != total=%d"
        % (
            len(sent),
            statsd.packets_dropped_queue,
            statsd.packets_dropped_expired,
            statsd.packets_dropped_writer,
            total,
        )
    )
    statsd.stop()


# ---------------------------------------------------------------------------
# 4. A payload stuck retrying a connection failure forever (agent
#    permanently unreachable) must still be given up on within a bounded
#    time, must be counted as a writer drop rather than vanishing, and
#    stop() must report False -- never a false "drained" success -- for
#    that exact scenario.
# ---------------------------------------------------------------------------
@given(
    stop_timeout=st.one_of(st.none(), st.floats(min_value=0.05, max_value=0.5)),
)
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_abandoned_retry_payload_is_accounted_and_stop_reports_failure(stop_timeout):
    with patch("datadog.dogstatsd.base.SENDER_UNBOUNDED_STOP_GRACE_SECONDS", 0.3), \
            patch("datadog.dogstatsd.base.SENDER_STOP_RETRY_INTERVAL", 0.05):
        sock_path = "/tmp/dogstatsd-fuzz-never-created-%d.sock" % random.randint(0, 10 ** 9)
        statsd = DogStatsd(
            disable_background_sender=False,
            disable_buffering=True,
            disable_aggregation=True,
            disable_telemetry=True,
            socket_path="unix://" + sock_path,
            socket_connect_retry=True,
            track_instance=False,
        )
        statsd.gauge("stuck.retry", 1)
        time.sleep(0.05)  # let the first connect attempt fail and start retrying

        bound = (stop_timeout if stop_timeout is not None else 0.3) + 5.0
        t0 = time.time()
        result = statsd.stop(stop_timeout)
        elapsed = time.time() - t0

        # If stop() returned False because its OWN thread.join(timeout) timed
        # out while the sender thread was still alive -- a real, bounded
        # possibility: the sender's deadline check only runs once per
        # SENDER_STOP_RETRY_INTERVAL pacing cycle, so its actual abandon can
        # lag its own deadline by up to that interval, and for a bounded
        # timeout() comparable to (or smaller than) that interval, join()'s
        # own clock (which starts a moment after the deadline is set) can
        # expire first -- the drop accounting lands a little later,
        # asynchronously, on the still-running sender. stop() only promises
        # to bound *its own* wait, not that every side effect has already
        # landed by the time it returns. Poll briefly rather than asserting
        # instantaneously.
        deadline = time.time() + 3.0
        while statsd.packets_dropped_writer < 1 and time.time() < deadline:
            time.sleep(0.02)

    assert elapsed < bound, "stop(%r) took %.2fs, expected under %.2fs" % (stop_timeout, elapsed, bound)
    assert result is False, "the payload can never succeed here; stop() must report failure, not success"
    assert statsd.packets_dropped_writer == 1, "the abandoned payload must eventually be accounted, not silently lost"


# ---------------------------------------------------------------------------
# 5. The sender thread's own bookkeeping (which needs _buffer_lock between
#    items) must never be blocked by a producer that is itself parked
#    inside SenderQueue.put()'s wait-for-room phase holding that same lock.
#    Deliberately never calls stop(): that path has its own close()-based
#    escape hatch (see test 1 above) that would mask this exact deadlock,
#    which is about ordinary operation, not shutdown.
# ---------------------------------------------------------------------------
@given(
    maxsize=st.integers(min_value=1, max_value=4),
    sender_queue_timeout=st.one_of(st.none(), st.floats(min_value=5.0, max_value=30.0)),
    seed=st.integers(min_value=0),
)
@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_sender_bookkeeping_never_deadlocks_a_producer_waiting_for_room(maxsize, sender_queue_timeout, seed):
    rng = random.Random(seed)
    statsd = DogStatsd(
        disable_background_sender=False,
        disable_buffering=True,
        disable_aggregation=True,
        disable_telemetry=True,
        sender_queue_size=maxsize,
        sender_queue_timeout=sender_queue_timeout,
        track_instance=False,
    )

    release_a = threading.Event()
    entered_a = threading.Event()
    sent = []
    sent_lock = threading.Lock()

    def fake_xmit(packet, queue_mode=False):
        with sent_lock:
            first = not sent
            sent.append(packet)
        if first:
            # The sender has dequeued A and is now "transmitting" it --
            # wedge here so A stays in flight while the rest of the queue
            # fills up behind it.
            entered_a.set()
            release_a.wait(10.0)
        return True

    statsd._xmit_packet_with_telemetry = fake_xmit

    statsd._send_to_server("A:1|c")
    assert entered_a.wait(5.0), "sender never picked up A"

    # A is now out of the deque (in flight, wedged "sending"), so the deque
    # itself is empty: fill it to exactly maxsize without ever waiting.
    for i in range(maxsize):
        statsd._send_to_server("filler-%d:1|c" % i)

    # Deterministically know producer C is genuinely blocked waiting for
    # room (using only the queue's own lock) before releasing A -- without
    # this, A could get released before C ever needs to wait, making the
    # test pass vacuously regardless of whether the deadlock fix works.
    # Instrumenting the queue's own Condition.wait() directly (rather than a
    # dedicated hook) keeps this test decoupled from SenderQueue's internals
    # beyond the one blocking call it actually cares about.
    active_queue = statsd._active_sender.queue
    entered_wait = threading.Event()
    original_wait = active_queue._not_full.wait

    def wait_and_signal(timeout=None):
        entered_wait.set()
        return original_wait(timeout)

    active_queue._not_full.wait = wait_and_signal

    c_done = threading.Event()
    exceptions = []

    def send_c():
        try:
            statsd._send_to_server("C:1|c")
        except Exception as exc:  # pragma: no cover -- must never happen
            exceptions.append(exc)
        finally:
            c_done.set()

    t_c = threading.Thread(target=send_c, daemon=True)
    t_c.start()

    assert entered_wait.wait(5.0), "producer C never reached the wait-for-room phase"
    time.sleep(rng.uniform(0.0, 0.05))  # best-effort extra settling, as in test 2

    release_a.set()

    progressed = c_done.wait(10.0)
    t_c.join(timeout=5.0)

    assert not exceptions, "unexpected exception from producer C: %r" % (exceptions,)
    assert progressed and not t_c.is_alive(), (
        "producer C never returned from put() after A's send completed "
        "(maxsize=%s, sender_queue_timeout=%s) -- the sender's own "
        "bookkeeping is deadlocked against a producer waiting for room, "
        "with no stop() call anywhere in this test" % (maxsize, sender_queue_timeout)
    )

    assert statsd.wait_for_pending(10.0) is True
    statsd.stop()


# ---------------------------------------------------------------------------
# 6. stop() must stay bounded even with a large pile of producers genuinely
#    blocked inside SenderQueue.put()'s own wait-for-room (SenderQueue's
#    self._lock), not just a couple of them racing by chance. This is the
#    specific two-lock-deadlock shape to rule out for _send_to_server() no
#    longer holding _buffer_lock across put(): _stop_sender_thread() still
#    nests _buffer_lock -> SenderQueue.self._lock to insert Stop, so if that
#    nested acquisition could ever be blocked by producers parked in
#    self._lock's own Condition.wait(), stop() would hang here. It must not,
#    because Condition.wait() releases self._lock for the whole wait -- a
#    blocked producer holds no lock at all at that point.
# ---------------------------------------------------------------------------
@given(
    num_producers=st.integers(min_value=10, max_value=60),
    sender_queue_timeout=st.one_of(st.none(), st.floats(min_value=10.0, max_value=60.0)),
)
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_stop_stays_bounded_with_many_producers_genuinely_blocked_on_queue_room(
    num_producers, sender_queue_timeout
):
    statsd = DogStatsd(
        disable_background_sender=False,
        disable_buffering=True,
        disable_aggregation=True,
        disable_telemetry=True,
        sender_queue_size=1,
        sender_queue_timeout=sender_queue_timeout,
        track_instance=False,
    )

    release_wedge = threading.Event()
    entered_wedge = threading.Event()

    def fake_xmit(packet, queue_mode=False):
        if queue_mode and not entered_wedge.is_set():
            entered_wedge.set()
            release_wedge.wait(30.0)
        return True

    statsd._xmit_packet_with_telemetry = fake_xmit

    statsd._send_to_server("A:1|c")
    assert entered_wedge.wait(5.0), "sender never picked up the wedged send"
    statsd._send_to_server("B:1|c")  # fills sender_queue_size=1

    # Deterministically know every producer is genuinely inside put()'s
    # wait-for-room (holding only SenderQueue's own lock, and only for the
    # instant each wait() call takes to start) before racing stop() against
    # them -- a sleep-based "probably blocked by now" guess could let some
    # producers never reach the wait at all, which wouldn't exercise this.
    active_queue = statsd._active_sender.queue
    entered_count = [0]
    count_lock = threading.Lock()
    all_entered = threading.Event()
    original_wait = active_queue._not_full.wait

    def wait_and_count(timeout=None):
        with count_lock:
            entered_count[0] += 1
            if entered_count[0] == num_producers:
                all_entered.set()
        return original_wait(timeout)

    active_queue._not_full.wait = wait_and_count

    exceptions = []

    def producer(n):
        try:
            statsd._send_to_server("p-%d:1|c" % n)
        except Exception as exc:  # pragma: no cover -- must never happen
            exceptions.append(exc)

    producer_threads = [threading.Thread(target=producer, args=(n,), daemon=True) for n in range(num_producers)]
    for t in producer_threads:
        t.start()

    assert all_entered.wait(10.0), "not every producer reached the wait-for-room phase"

    stop_result = {}

    def call_stop():
        try:
            stop_result["value"] = statsd.stop(10.0)
        except Exception as exc:  # pragma: no cover -- must never happen
            exceptions.append(exc)

    t_stop = threading.Thread(target=call_stop)
    t0 = time.time()
    t_stop.start()

    # Give stop() a beat to actually start draining before unwedging, so
    # this is exercising stop() racing the pile of blocked producers, not
    # just unwedging into an already-finished stop() call.
    time.sleep(0.05)
    release_wedge.set()

    t_stop.join(timeout=15.0)
    elapsed = time.time() - t0

    for t in producer_threads:
        t.join(timeout=10.0)
    still_alive = [t for t in producer_threads if t.is_alive()]

    assert not exceptions, "unexpected exception(s): %r" % (exceptions,)
    assert not t_stop.is_alive(), "stop() did not return within 15s (num_producers=%d)" % num_producers
    assert not still_alive, "%d/%d producer(s) never returned from put()" % (len(still_alive), num_producers)
    assert elapsed < 15.0
    assert stop_result.get("value") is True, "stop() should have drained cleanly once unwedged"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
