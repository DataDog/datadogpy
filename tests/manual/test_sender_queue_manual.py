"""
Manual, narrated test-drive of `datadog.dogstatsd.sender_queue.SenderQueue`.

Unlike the unit tests, this script is meant to be *read while it runs*: every
scenario prints what it's about to do, what actually happened, and then
asserts on the outcome. It exercises the queue in isolation first (no
threads, no sockets), then stresses it with real concurrent producers/
consumers, and finally drives it through the real `DogStatsd` client end to
end (drop-oldest, real-time expiry, and requeue-on-connection-failure).

Usage:
    python3 tests/manual/test_sender_queue_manual.py

Exits 0 if every check passed, 1 otherwise.
"""
import errno
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datadog.dogstatsd.sender_queue import (  # noqa: E402
    PendingPayload,
    SenderQueue,
    Stop,
    is_replay_safe,
    payload_text,
)
from datadog.util.compat import monotonic  # noqa: E402
import datadog.dogstatsd.base as base_module  # noqa: E402
from datadog.dogstatsd.base import DogStatsd  # noqa: E402


# --------------------------------------------------------------------------
# Small helpers: narration + a pass/fail ledger shared across every scenario.
# --------------------------------------------------------------------------
_RESULTS = {"pass": 0, "fail": 0, "failures": []}


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def note(msg):
    print("    . {}".format(msg))


def check(condition, description):
    if condition:
        _RESULTS["pass"] += 1
        print("  [PASS] {}".format(description))
    else:
        _RESULTS["fail"] += 1
        _RESULTS["failures"].append(description)
        print("  [FAIL] {}".format(description))
    return condition


def recorder(label):
    """A drop callback that remembers every item it was called with and prints it."""
    events = []

    def _on_drop(item):
        events.append(item)
        rs = is_replay_safe(item)
        # Replay-safe entries are bare strings with no enqueued_at to age.
        age = "n/a" if rs else "{:.3f}s".format(monotonic() - item.enqueued_at)
        print(
            "    -> {label} fired: payload={payload!r} age={age} replay_safe={rs}".format(
                label=label, payload=payload_text(item), age=age, rs=rs
            )
        )

    _on_drop.events = events
    return _on_drop


def new_recorders():
    return recorder("on_drop_queue_full"), recorder("on_drop_expired")


def quiet_recorder(label, report_every=100):
    """Like recorder(), but only prints a running count every `report_every`
    hits instead of one line per drop -- for scenarios with hundreds of them,
    where line-per-event narration would just be noise."""
    events = []

    def _on_drop(item):
        events.append(item)
        if len(events) % report_every == 0:
            print("    -> {label}: {count} drops so far (e.g. {sample!r})".format(
                label=label, count=len(events), sample=payload_text(item).strip()
            ))

    _on_drop.events = events
    return _on_drop


def payload(text, replay_safe=False, enqueued_at=None):
    """Build a queue entry: a bare string when replay-safe, else a wrapper."""
    if replay_safe:
        return text
    return PendingPayload(text, enqueued_at if enqueued_at is not None else monotonic())


# --------------------------------------------------------------------------
# Scenario 1: plain FIFO, no eviction, no expiry.
# --------------------------------------------------------------------------
def scenario_1_fifo_order():
    section("1. Basic FIFO ordering (unbounded, nothing expires)")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=0, expiry_seconds=100.0, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    for name in ("a", "b", "c"):
        q.put(payload(name + "\n"))
        note("put({!r}) -> qsize={}".format(name, q.qsize()))

    order = [payload_text(q.get()) for _ in range(3)]
    note("got, in order: {}".format(order))

    check(order == ["a\n", "b\n", "c\n"], "FIFO order preserved")
    check(not drop_full.events and not drop_expired.events, "no drops during a plain unbounded run")
    check(q.qsize() == 0, "queue fully drained")


# --------------------------------------------------------------------------
# Scenario 2: overflow evicts the oldest entry to make room.
# --------------------------------------------------------------------------
def scenario_2_overflow_drops_oldest():
    section("2. Overflow: the oldest entry is evicted to make room")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=2, expiry_seconds=100.0, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("first\n"))
    note("put('first') -> qsize={}".format(q.qsize()))
    q.put(payload("second\n"))
    note("put('second') -> qsize={} (queue is now at maxsize=2)".format(q.qsize()))
    note("putting a third payload...")
    q.put(payload("third\n"))
    note("put('third') -> qsize={}".format(q.qsize()))

    check(q.qsize() == 2, "queue never grew past maxsize")
    check([payload_text(e) for e in drop_full.events] == ["first\n"], "the OLDEST entry was evicted via on_drop_queue_full")
    check(not drop_expired.events, "nothing was expired -- this was a pure capacity eviction")

    remaining = [payload_text(q.get()) for _ in range(2)]
    note("remaining, in order: {}".format(remaining))
    check(remaining == ["second\n", "third\n"], "the two newest survivors come out in FIFO order")


# --------------------------------------------------------------------------
# Scenario 3: an evicted oldest entry that's ALSO stale is attributed to expiry.
# --------------------------------------------------------------------------
def scenario_3_overflow_prefers_expiry_reason():
    section("3. Overflow where the evicted entry is ALSO already stale")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=1, expiry_seconds=0.2, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("stale\n"))
    note("put('stale'); sleeping 0.25s so it ages past the 0.2s expiry window...")
    time.sleep(0.25)

    note("queue is at maxsize=1; putting a fresh payload now forces an eviction")
    q.put(payload("fresh\n"))

    check(not drop_full.events, "NOT counted as a plain capacity drop")
    check([payload_text(e) for e in drop_expired.events] == ["stale\n"], "counted as an EXPIRY drop instead -- more informative")
    check(payload_text(q.get()) == "fresh\n", "the fresh payload survived")


# --------------------------------------------------------------------------
# Scenario 4: get() lazily drains every stale entry at the front.
# --------------------------------------------------------------------------
def scenario_4_get_drains_stale_entries():
    section("4. get() drains every stale entry at the front before returning")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=0, expiry_seconds=0.2, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("stale-1\n"))
    q.put(payload("stale-2\n"))
    note("put two payloads; sleeping 0.25s so both age past the 0.2s expiry window...")
    time.sleep(0.25)
    q.put(payload("fresh\n"))
    note("qsize before get(): {}".format(q.qsize()))

    item = q.get()
    note("qsize after get(): {}".format(q.qsize()))

    check(payload_text(item) == "fresh\n", "get() skipped both stale entries and returned the fresh one")
    check([payload_text(e) for e in drop_expired.events] == ["stale-1\n", "stale-2\n"], "both stale entries dropped, in order, along the way")


# --------------------------------------------------------------------------
# Scenario 5: replay_safe payloads never expire.
# --------------------------------------------------------------------------
def scenario_5_replay_safe_never_expires():
    section("5. replay_safe=True payloads are exempt from expiry")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=0, expiry_seconds=0.1, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("timestamped\n", replay_safe=True))
    note("put a replay_safe payload; sleeping 0.3s, well past the 0.1s expiry window...")
    time.sleep(0.3)

    item = q.get()
    note("get() returned: {!r}".format(payload_text(item) if item is not None else None))
    check(item is not None and payload_text(item) == "timestamped\n", "still returned by get(), never dropped")
    check(not drop_expired.events, "on_drop_expired was never called for it")


# --------------------------------------------------------------------------
# Scenario 6: requeue_front() -- the three outcomes.
# --------------------------------------------------------------------------
def scenario_6a_requeue_front_with_room():
    section("6a. requeue_front(): succeeds when there's room, rejoins at the FRONT")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=2, expiry_seconds=100.0, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("in-flight\n"))
    in_flight = q.get()
    note("sender thread picked up 'in-flight' and (simulated) failed to send it")
    q.requeue_front(in_flight)
    note("requeued 'in-flight'; qsize={}".format(q.qsize()))
    q.put(payload("new\n"))
    note("put 'new'; qsize={}".format(q.qsize()))

    order = [payload_text(q.get()) for _ in range(2)]
    note("got, in order: {}".format(order))
    check(order == ["in-flight\n", "new\n"], "the requeued item is retried BEFORE the newer one")
    check(not drop_full.events and not drop_expired.events, "nothing was dropped")


def scenario_6b_requeue_front_drops_when_full():
    section("6b. requeue_front(): dropped via on_drop_queue_full when the queue is already full")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=1, expiry_seconds=100.0, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("in-flight\n"))
    in_flight = q.get()
    note("sender thread picked up 'in-flight'; meanwhile a fresh payload fills the now-empty slot")
    q.put(payload("new\n"))
    note("qsize is already at maxsize=1; the failed send now tries to requeue 'in-flight'...")
    q.requeue_front(in_flight)

    check(q.qsize() == 1, "queue never grew past maxsize")
    check([payload_text(e) for e in drop_full.events] == ["in-flight\n"], "'in-flight' was dropped via on_drop_queue_full")
    check(payload_text(q.get()) == "new\n", "'new' is untouched and still gets sent")


def scenario_6c_requeue_front_drops_when_expired():
    section("6c. requeue_front(): dropped via on_drop_expired when it went stale in flight, even with room to spare")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=0, expiry_seconds=0.15, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("slow-send\n"))
    picked_up = q.get()
    note("sender thread picked up 'slow-send' and is (simulated) stuck retrying the connection...")
    time.sleep(0.2)
    note("...0.2s later the send finally fails; the queue is unbounded, so there is plenty of room")
    q.requeue_front(picked_up)

    check(q.qsize() == 0, "NOT requeued despite there being room -- expiry wins")
    check([payload_text(e) for e in drop_expired.events] == ["slow-send\n"], "dropped via on_drop_expired")


# --------------------------------------------------------------------------
# Scenario 7: _unfinished_tasks / task_done() / join() bookkeeping.
# --------------------------------------------------------------------------
def scenario_7_task_done_and_join():
    section("7. _unfinished_tasks bookkeeping across put()/task_done()/join()")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=0, expiry_seconds=100.0, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    for name in ("x", "y", "z"):
        q.put(payload(name + "\n"))
    note("put 3 payloads -> _unfinished_tasks={}".format(q._unfinished_tasks))
    check(q._unfinished_tasks == 3, "one unfinished task recorded per put()")

    joined = {"done": False}

    def joiner():
        q.join()
        joined["done"] = True

    t = threading.Thread(target=joiner)
    t.start()
    time.sleep(0.1)
    note("join() called on a background thread; joined={}".format(joined["done"]))
    check(not joined["done"], "join() is still blocked -- 3 tasks are still outstanding")

    for _ in range(3):
        item = q.get()
        note("get() -> {!r}, calling task_done()".format(payload_text(item)))
        q.task_done()

    t.join(timeout=2)
    note("after 3x task_done(): joined={} _unfinished_tasks={}".format(joined["done"], q._unfinished_tasks))
    check(joined["done"], "join() returned once every task was marked done")
    check(q._unfinished_tasks == 0, "_unfinished_tasks back to zero")


# --------------------------------------------------------------------------
# Scenario 8: the Stop sentinel bypasses capacity and expiry entirely.
# --------------------------------------------------------------------------
def scenario_8_stop_sentinel():
    section("8. The Stop sentinel bypasses capacity limits and expiry entirely")
    drop_full, drop_expired = new_recorders()
    q = SenderQueue(maxsize=1, expiry_seconds=100.0, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    q.put(payload("only-slot\n"))
    note("queue is at maxsize=1; putting Stop now...")
    q.put(Stop)
    note("qsize={} (Stop did not evict 'only-slot', nor was it evicted itself)".format(q.qsize()))

    check(q.qsize() == 2, "Stop was appended past maxsize instead of triggering eviction")

    first = q.get()
    second = q.get()
    check(payload_text(first) == "only-slot\n", "the real payload still comes out first (FIFO)")
    check(second is Stop, "Stop comes out exactly as put in, untouched by drop logic")
    q.task_done()
    q.task_done()


# --------------------------------------------------------------------------
# Scenario 9: concurrency smoke test -- multiple producers racing a consumer.
# --------------------------------------------------------------------------
def scenario_9_concurrency_smoke_test():
    section("9. Concurrency smoke test: 4 producer threads racing 1 consumer thread")
    note("this scenario can trigger hundreds of evictions -- using quiet_recorder() to summarize instead of narrating every one")
    drop_full, drop_expired = quiet_recorder("on_drop_queue_full"), quiet_recorder("on_drop_expired")
    q = SenderQueue(maxsize=20, expiry_seconds=5.0, on_drop_queue_full=drop_full, on_drop_expired=drop_expired)

    n_per_producer = 200
    n_producers = 4
    total = n_per_producer * n_producers
    received = []

    def producer(pid):
        for i in range(n_per_producer):
            q.put(payload("p{}-{}\n".format(pid, i)))

    def consumer():
        while True:
            item = q.get()
            if item is Stop:
                q.task_done()
                return
            received.append(item)
            q.task_done()
            # Artificial slowness so the 4 producers reliably outrun the
            # consumer and we actually get to see maxsize=20 evictions
            # happen, instead of everything just being consumed in time.
            time.sleep(0.0005)

    note("maxsize={} expiry_seconds={} total_payloads={}".format(q._maxsize, q._expiry_seconds, total))
    producers = [threading.Thread(target=producer, args=(pid,)) for pid in range(n_producers)]
    consumer_thread = threading.Thread(target=consumer)

    t0 = time.time()
    consumer_thread.start()
    for p in producers:
        p.start()
    for p in producers:
        p.join()
    note("all {} producers finished putting {} payloads in {:.3f}s".format(n_producers, total, time.time() - t0))

    q.put(Stop)
    consumer_thread.join(timeout=10)

    accounted = len(received) + len(drop_full.events) + len(drop_expired.events)
    note(
        "received={} dropped_full={} dropped_expired={} accounted_total={} expected_total={}".format(
            len(received), len(drop_full.events), len(drop_expired.events), accounted, total
        )
    )
    check(not consumer_thread.is_alive(), "consumer thread exited cleanly after Stop")
    check(accounted == total, "every put() payload is accounted for exactly once (sent, capacity-dropped, or expired)")
    check(q.qsize() == 0, "queue fully drained")
    check(q._unfinished_tasks == 0, "_unfinished_tasks settled back to zero under real concurrency")
    check(len(drop_full.events) > 0, "the slow consumer + maxsize=20 did trigger at least one real eviction")


# --------------------------------------------------------------------------
# Scenario 10: end-to-end through the real DogStatsd client.
# --------------------------------------------------------------------------
class ScriptedSocket(object):
    """Just enough of a socket to drive DogStatsd's send path without a real network."""

    family = socket.AF_UNIX

    def __init__(self):
        self.received = []

    def send(self, data):
        self.received.append(data)
        return len(data)

    def sendall(self, data):
        self.received.append(data)

    def settimeout(self, *_args):
        pass

    def getsockopt(self, *_args):
        return socket.SOCK_DGRAM

    def close(self):
        pass


def scenario_10a_client_drop_oldest():
    section("10a. End-to-end through DogStatsd: drop-oldest via the real client")
    # No background sender thread on purpose. With one running it races this
    # sequence: if it drains 'first' before 'second' is queued, the queue is
    # never full, nothing is evicted, and the checks below describe a schedule
    # that didn't happen (this scenario failed ~7 runs in 10 that way). Build
    # the queue by hand -- the same wiring _start_sender_thread() uses -- then
    # drive the real sender loop synchronously at the end.
    statsd = DogStatsd(disable_background_sender=True, disable_telemetry=True)
    statsd.socket = ScriptedSocket()
    statsd._queue = SenderQueue(
        1,
        base_module.PENDING_PAYLOAD_EXPIRY_SECONDS,
        statsd._account_dropped_queue_full,
        statsd._account_dropped_expired,
    )

    statsd._send_to_server("first")
    note("_send_to_server('first') -> qsize={}".format(statsd._queue.qsize()))
    statsd._send_to_server("second")
    note("_send_to_server('second') -> qsize={}".format(statsd._queue.qsize()))
    note("bytes_dropped_queue={} packets_dropped_queue={}".format(statsd.bytes_dropped_queue, statsd.packets_dropped_queue))

    check(statsd.packets_dropped_queue == 1, "one packet ('first') was dropped for capacity")

    # Drain through the real sender loop; Stop makes it return once done.
    statsd._queue.put(Stop)
    statsd._sender_main_loop(statsd._queue)
    note("socket received: {}".format(statsd.socket.received))
    check(statsd.socket.received == [b"second\n"], "only the surviving (newest) payload was actually sent")


def scenario_10b_client_real_time_expiry():
    section("10b. End-to-end through DogStatsd: real-time expiry with no reachable agent")
    # NOTE: base.py does `from datadog.dogstatsd.sender_queue import ... PENDING_PAYLOAD_EXPIRY_SECONDS`,
    # which binds its OWN name in base's namespace at import time. Patching
    # sender_queue.PENDING_PAYLOAD_EXPIRY_SECONDS after that has no effect on
    # _start_sender_thread(), which reads base's copy of the name -- so that's
    # the one that has to be patched here.
    original_expiry = base_module.PENDING_PAYLOAD_EXPIRY_SECONDS
    base_module.PENDING_PAYLOAD_EXPIRY_SECONDS = 0.3
    note("patched datadog.dogstatsd.base.PENDING_PAYLOAD_EXPIRY_SECONDS: {} -> {}".format(original_expiry, base_module.PENDING_PAYLOAD_EXPIRY_SECONDS))

    statsd = None
    try:
        statsd = DogStatsd(
            socket_path="/tmp/sender-queue-manual-test-nonexistent-{}.sock".format(os.getpid()),
            socket_connect_timeout=0.05,
            disable_background_sender=False,
            disable_telemetry=True,
        )
        statsd.increment("will.expire")
        note("queued 'will.expire' against a socket path that doesn't exist; waiting for wait_for_pending()...")

        t0 = time.time()
        statsd.wait_for_pending()
        elapsed = time.time() - t0
        note("wait_for_pending() returned after {:.3f}s".format(elapsed))

        check(statsd.packets_dropped_expired == 1, "the packet expired instead of being retried forever")
        check(statsd.packets_dropped_writer == 0, "it was NOT mistaken for a hard write failure")
        check(elapsed < 5.0, "expiry actually bounded how long wait_for_pending() took")
    finally:
        base_module.PENDING_PAYLOAD_EXPIRY_SECONDS = original_expiry
        note("restored PENDING_PAYLOAD_EXPIRY_SECONDS to {}".format(original_expiry))
        if statsd is not None:
            statsd.stop()


def scenario_10c_client_requeue_then_succeeds():
    section("10c. End-to-end through DogStatsd: requeue-and-retry survives a flaky reconnect, then succeeds")
    working_socket = ScriptedSocket()
    attempts = {"count": 0}
    fail_until = 4

    def flaky_get_uds_socket(_cls, _socket_path, _timeout, _connect_timeout):
        attempts["count"] += 1
        if attempts["count"] < fail_until:
            note("reconnect attempt #{}: still refused".format(attempts["count"]))
            raise socket.error(errno.ECONNREFUSED, "still refused")
        note("reconnect attempt #{}: agent is back up".format(attempts["count"]))
        return working_socket

    real_get_uds_socket = DogStatsd._get_uds_socket
    DogStatsd._get_uds_socket = classmethod(flaky_get_uds_socket)
    statsd = None
    try:
        statsd = DogStatsd(
            socket_path="/tmp/sender-queue-manual-test-flaky-{}.sock".format(os.getpid()),
            socket_connect_timeout=0.05,
            disable_background_sender=False,
            disable_telemetry=True,
        )
        statsd.gauge("eventually.sent", 1)
        t0 = time.time()
        statsd.wait_for_pending()
        elapsed = time.time() - t0
    finally:
        DogStatsd._get_uds_socket = real_get_uds_socket

    note("wait_for_pending() returned after {:.3f}s and {} reconnect attempts".format(elapsed, attempts["count"]))
    check(attempts["count"] >= fail_until, "it took multiple reconnect attempts, exercising requeue-and-retry")
    check(statsd.packets_dropped_writer == 0, "never hard-dropped as a write failure")
    check(statsd.packets_dropped_expired == 0, "never expired -- it succeeded well before the TTL")
    check(
        bool(working_socket.received) and working_socket.received[0].startswith(b"eventually.sent:1|g"),
        "the packet was actually delivered once the agent came back",
    )

    statsd.stop()


# --------------------------------------------------------------------------
def main():
    scenarios = [
        scenario_1_fifo_order,
        scenario_2_overflow_drops_oldest,
        scenario_3_overflow_prefers_expiry_reason,
        scenario_4_get_drains_stale_entries,
        scenario_5_replay_safe_never_expires,
        scenario_6a_requeue_front_with_room,
        scenario_6b_requeue_front_drops_when_full,
        scenario_6c_requeue_front_drops_when_expired,
        scenario_7_task_done_and_join,
        scenario_8_stop_sentinel,
        scenario_9_concurrency_smoke_test,
        scenario_10a_client_drop_oldest,
        scenario_10b_client_real_time_expiry,
        scenario_10c_client_requeue_then_succeeds,
    ]

    start = time.time()
    for scenario in scenarios:
        scenario()

    section("SUMMARY")
    print("  {} passed, {} failed, {:.2f}s total".format(_RESULTS["pass"], _RESULTS["fail"], time.time() - start))
    if _RESULTS["failures"]:
        print("  Failed checks:")
        for description in _RESULTS["failures"]:
            print("    - {}".format(description))

    sys.exit(1 if _RESULTS["fail"] else 0)


if __name__ == "__main__":
    main()
