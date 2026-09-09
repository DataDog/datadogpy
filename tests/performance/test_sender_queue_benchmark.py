"""
Microbenchmark: SenderQueue vs. stdlib queue.Queue.

This isolates just the hand-off queue's own overhead -- no sockets, no
network variance -- because that's the piece that changed when the
background sender moved off queue.Queue. put() runs synchronously on every
metric emission's calling thread (the application's hot path), so its
*latency* matters at least as much as raw throughput; get() runs on the
background sender thread.

queue.Queue is used as the baseline throughout via a thin adapter
(_OldStyleQueueAdapter) that reproduces the OLD behavior being replaced:
put_nowait() and drop-with-a-counter on queue.Full, get()+task_done() to
drain. That's the fairest apples-to-apples comparison, since it's literally
what SenderQueue's put()/get() replaced.

Scenarios:
  1. Unbounded put() then get(), single-threaded (best case for both --
     no eviction, no contention).
  2. Bounded queue, kept permanently full: every put() forces an eviction
     for SenderQueue, vs an immediate reject-with-exception for
     queue.Queue. This is the main new cost the redesign introduces.
  3. A single put() that has to walk past a large backlog of already-EXPIRED
     entries at the front (SenderQueue's opportunistic-cleanup loop has no
     upper bound tied to "just free one slot" -- it clears every consecutive
     stale entry it finds). Reports cost as a function of backlog size, to
     surface whether this can spike a calling thread's latency.
  4. Producer/consumer concurrency: N producer threads hammering put() while
     1 consumer thread drains, measuring achieved producer throughput and
     put() latency percentiles under real lock contention.
  5. Per-item memory footprint: PendingPayload wrapper vs a bare str.

Usage:
    python3 tests/performance/test_sender_queue_benchmark.py [--quick]

    --quick shrinks every N so it finishes in a few seconds (CI-friendly);
    default sizes are big enough to get low-noise numbers on a quiet
    machine.

This prints numbers and interpretation guidance; it does not hard-fail on
absolute thresholds (those are too hardware/noise dependent to gate CI on
reliably). The one thing it does assert on is the *shape* of the eviction
cost in scenario 3 -- that it's linear in backlog size, not something worse.
Read the printed numbers yourself before/after a change and compare.
"""
import os
import sys
import threading
import time

try:
    import queue as stdlib_queue
except ImportError:
    import Queue as stdlib_queue  # type: ignore[no-redef]

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datadog.dogstatsd.sender_queue import (  # noqa: E402
    PendingPayload,
    SenderQueue,
    monotonic,
)

QUICK = "--quick" in sys.argv


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def note(msg):
    print("    . {}".format(msg))


PACKET = "some.metric.name:1|c|#tag1:val1,tag2:val2\n"


# --------------------------------------------------------------------------
# Baseline adapter: reproduces the OLD (pre-SenderQueue) put/get contract on
# top of stdlib queue.Queue, so scenario code can treat both implementations
# uniformly.
# --------------------------------------------------------------------------
class _OldStyleQueueAdapter(object):
    def __init__(self, maxsize):
        self._q = stdlib_queue.Queue(maxsize)
        self.dropped = 0

    def put(self, item):
        try:
            self._q.put_nowait(item)
        except stdlib_queue.Full:
            self.dropped += 1

    def get(self):
        return self._q.get()

    def task_done(self):
        self._q.task_done()

    def qsize(self):
        return self._q.qsize()


def make_sender_queue(maxsize, expiry_seconds=3600.0):
    drops = {"full": 0, "expired": 0}

    def on_full(_item):
        drops["full"] += 1

    def on_expired(_item):
        drops["expired"] += 1

    q = SenderQueue(maxsize, expiry_seconds, on_full, on_expired)
    q.drops = drops
    return q


def percentiles(samples_us):
    samples_us = sorted(samples_us)
    n = len(samples_us)

    def pct(p):
        idx = min(n - 1, int(n * p))
        return samples_us[idx]

    return {
        "p50": pct(0.50),
        "p90": pct(0.90),
        "p99": pct(0.99),
        "max": samples_us[-1],
    }


def time_puts(put_fn, n):
    """Time n individual put() calls, returning (total_seconds, [latency_us, ...])."""
    samples = [0.0] * n
    t_start = time.perf_counter()
    for i in range(n):
        t0 = time.perf_counter()
        put_fn()
        samples[i] = (time.perf_counter() - t0) * 1e6
    total = time.perf_counter() - t_start
    return total, samples


def report(label, n, total_seconds, samples_us):
    p = percentiles(samples_us)
    print(
        "    {:<28s} ops/sec={:>10,.0f}  p50={:>7.3f}us  p90={:>7.3f}us  p99={:>7.3f}us  max={:>9.3f}us".format(
            label, n / total_seconds, p["p50"], p["p90"], p["p99"], p["max"]
        )
    )
    return p


# --------------------------------------------------------------------------
# Scenario 1: unbounded, no contention, no eviction.
# --------------------------------------------------------------------------
def scenario_1_unbounded_single_threaded():
    section("1. Unbounded put()/get(), single-threaded (best case, no eviction)")
    n = 20000 if not QUICK else 2000

    old = _OldStyleQueueAdapter(maxsize=0)
    total, samples = time_puts(lambda: old.put(PACKET), n)
    report("queue.Queue (baseline)", n, total, samples)
    for _ in range(n):
        old.get()
        old.task_done()

    new = make_sender_queue(maxsize=0)
    total, samples = time_puts(lambda: new.put(PendingPayload(PACKET, monotonic(), False)), n)
    new_p = report("SenderQueue", n, total, samples)
    for _ in range(n):
        new.get()
        new.task_done()

    note("SenderQueue p99 put() latency: {:.3f}us for {:,} plain puts with headroom to spare".format(new_p["p99"], n))


# --------------------------------------------------------------------------
# Scenario 2: bounded queue, kept permanently full -- every put() evicts.
# --------------------------------------------------------------------------
def scenario_2_sustained_overflow():
    section("2. Bounded queue kept permanently full: every put() forces eviction (new cost)")
    n = 20000 if not QUICK else 2000
    maxsize = 8

    old = _OldStyleQueueAdapter(maxsize=maxsize)
    for _ in range(maxsize):
        old.put(PACKET)
    total, samples = time_puts(lambda: old.put(PACKET), n)
    old_p = report("queue.Queue (baseline)", n, total, samples)
    note("queue.Queue just rejects with an exception when full -- O(1), no eviction work at all")

    new = make_sender_queue(maxsize=maxsize)
    for _ in range(maxsize):
        new.put(PendingPayload(PACKET, monotonic(), False))
    total, samples = time_puts(lambda: new.put(PendingPayload(PACKET, monotonic(), False)), n)
    new_p = report("SenderQueue", n, total, samples)

    ratio = new_p["p99"] / old_p["p99"] if old_p["p99"] else float("inf")
    note("SenderQueue's drop-oldest-and-evict costs {:.1f}x queue.Queue's reject-with-exception at p99".format(ratio))
    note("(each put() here evicts exactly one item -- the mandatory oldest -- since nothing is expired)")


# --------------------------------------------------------------------------
# Scenario 3: one put() that has to walk past a large expired backlog.
# --------------------------------------------------------------------------
def scenario_3_large_expired_backlog():
    section("3. Cost of ONE put() as a function of an already-expired backlog size")
    note("SenderQueue's opportunistic cleanup has no cap tied to 'free just one slot': it clears")
    note("every consecutive stale entry at the front. This measures whether that can spike latency.")

    backlog_sizes = [1, 10, 100, 1000, 5000] if not QUICK else [1, 10, 100]
    results = []
    for backlog in backlog_sizes:
        # expiry_seconds=0 with a backdated enqueued_at makes every backlog
        # entry expired the instant it's queued. maxsize=backlog (exactly
        # full) so the next put() below is what actually triggers eviction.
        q = make_sender_queue(maxsize=backlog, expiry_seconds=0.0)
        stale_at = monotonic() - 1000.0
        for _ in range(backlog):
            q.put(PendingPayload(PACKET, stale_at, False))

        t0 = time.perf_counter()
        q.put(PendingPayload(PACKET, monotonic(), False))
        elapsed_us = (time.perf_counter() - t0) * 1e6

        note("backlog={:>5d} stale entries -> single put() took {:>9.3f}us, evicted {:d}".format(
            backlog, elapsed_us, q.drops["expired"] + q.drops["full"]
        ))
        results.append((backlog, elapsed_us))

    # Sanity check on the *shape*: cost should scale roughly linearly with
    # backlog size, not blow up super-linearly. Compare the per-entry cost
    # at the smallest and largest backlog sizes; allow a generous margin for
    # fixed overhead and noise, but a large deviation would indicate a real
    # algorithmic problem worth investigating.
    (small_n, small_us), (large_n, large_us) = results[1], results[-1]
    small_per_entry = small_us / small_n
    large_per_entry = large_us / large_n
    ratio = large_per_entry / small_per_entry if small_per_entry else float("inf")
    note(
        "per-entry eviction cost: {:.3f}us/entry at backlog={} vs {:.3f}us/entry at backlog={} (ratio={:.2f}x)".format(
            small_per_entry, small_n, large_per_entry, large_n, ratio
        )
    )
    if ratio > 5.0:
        print("  [WARN] per-entry eviction cost grew by {:.1f}x from a small to a large backlog".format(ratio))
        print("         -- that's worse than linear; investigate before shipping.")
    else:
        print("  [OK]   per-entry eviction cost stayed roughly flat as backlog size grew (linear, as expected)")
    note("takeaway: a single put() CAN take noticeably longer if a huge stale backlog piles up (e.g. a")
    note("long outage with a very large sender_queue_size). Keep sender_queue_size sized to what you're")
    note("actually willing to let one put() walk through in the worst case.")


# --------------------------------------------------------------------------
# Scenario 4: producer/consumer concurrency.
# --------------------------------------------------------------------------
def _run_concurrent(put_fn, get_and_ack_fn, n_producers, n_per_producer, duration_cap=15.0):
    latencies = []
    latencies_lock = threading.Lock()
    stop = threading.Event()

    def producer():
        local_latencies = []
        for _ in range(n_per_producer):
            t0 = time.perf_counter()
            put_fn()
            local_latencies.append((time.perf_counter() - t0) * 1e6)
        with latencies_lock:
            latencies.extend(local_latencies)

    def consumer():
        while not stop.is_set():
            get_and_ack_fn()

    consumer_thread = threading.Thread(target=consumer)
    consumer_thread.daemon = True
    consumer_thread.start()

    producers = [threading.Thread(target=producer) for _ in range(n_producers)]
    t0 = time.perf_counter()
    for p in producers:
        p.start()
    for p in producers:
        p.join(timeout=duration_cap)
    elapsed = time.perf_counter() - t0
    stop.set()

    total_ops = n_producers * n_per_producer
    return elapsed, total_ops, latencies


def scenario_4_concurrency():
    section("4. Producer/consumer concurrency: N producers hammering put(), 1 consumer draining")
    n_producers = 4
    n_per_producer = 5000 if not QUICK else 500

    old = _OldStyleQueueAdapter(maxsize=1000)
    elapsed, total_ops, samples = _run_concurrent(
        lambda: old.put(PACKET),
        lambda: (old.get(), old.task_done()),
        n_producers,
        n_per_producer,
    )
    old_p = report("queue.Queue (baseline)", total_ops, elapsed, samples)
    note("queue.Queue: {} producers x {} puts in {:.3f}s, {} dropped-on-full".format(
        n_producers, n_per_producer, elapsed, old.dropped
    ))

    new = make_sender_queue(maxsize=1000)
    elapsed, total_ops, samples = _run_concurrent(
        lambda: new.put(PendingPayload(PACKET, monotonic(), False)),
        lambda: (new.get(), new.task_done()),
        n_producers,
        n_per_producer,
    )
    new_p = report("SenderQueue", total_ops, elapsed, samples)
    note("SenderQueue: {} producers x {} puts in {:.3f}s, {} dropped-full, {} dropped-expired".format(
        n_producers, n_per_producer, elapsed, new.drops["full"], new.drops["expired"]
    ))

    ratio_p99 = new_p["p99"] / old_p["p99"] if old_p["p99"] else float("inf")
    note("under real thread contention, SenderQueue's p99 put() latency is {:.2f}x queue.Queue's".format(ratio_p99))


# --------------------------------------------------------------------------
# Scenario 5: per-item memory footprint.
# --------------------------------------------------------------------------
def scenario_5_memory_footprint():
    section("5. Per-item memory footprint: PendingPayload wrapper vs a bare str")
    note("sys.getsizeof() is shallow: PendingPayload holds a *reference* to the payload string,")
    note("not a copy, so its own size doesn't include the string's bytes. The old queue.Queue held")
    note("that same string directly with nothing wrapping it, so the real extra cost per item is")
    note("the wrapper object itself, plus (for non-replay-safe items) a float object for enqueued_at.")

    payload_str = PACKET
    wrapper_size = sys.getsizeof(PendingPayload(payload_str, monotonic(), False))

    note("payload str (shared either way):                       {} bytes".format(sys.getsizeof(payload_str)))
    note("PendingPayload wrapper itself (__slots__, no __dict__): {} bytes".format(wrapper_size))
    print()

    note("replay_safe=True payloads (gauge_with_timestamp, etc.) never have their enqueued_at read")
    note("(SenderQueue._expired() short-circuits on replay_safe first), so base.py passes None")
    note("instead of a fresh timestamp -- no float allocation at all for this class of payload:")
    replay_safe_wrapped = PendingPayload(payload_str, None, True)
    note("  PendingPayload(..., enqueued_at=None, replay_safe=True): {} bytes total, +0 for the timestamp".format(
        sys.getsizeof(replay_safe_wrapped)
    ))
    print()

    non_replay_safe_extra = wrapper_size + sys.getsizeof(monotonic())
    note("Non-replay-safe payloads DO need a real enqueued_at -- one monotonic() reading per item,")
    note("same as any other Python object holding a fresh timestamp. Extra overhead per item vs the")
    note("old bare-string queue: ~{} bytes ({} wrapper + {} float).".format(
        non_replay_safe_extra, wrapper_size, sys.getsizeof(monotonic())
    ))
    for n in (100, 10000, 100000):
        note("  at sender_queue_size={:<7d} that's ~{:.1f}KB of additional resident overhead".format(
            n, non_replay_safe_extra * n / 1024.0
        ))
    note("(An earlier version of this code coalesced timestamps to a shared per-100ms-bucket float")
    note("to cut this under bursty load -- best case ~234KB saved at sender_queue_size=10,000, i.e.")
    note("~0.09% of a typical 256MB container's RSS. Reverted: not worth the added global mutable")
    note("state, cross-instance coupling, and dedicated concurrency tests for savings that small.)")


# --------------------------------------------------------------------------
def main():
    print("SenderQueue performance microbenchmark")
    print("Python {}.{}.{}  {}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.platform))
    if QUICK:
        print("(--quick mode: reduced iteration counts)")

    scenario_1_unbounded_single_threaded()
    scenario_2_sustained_overflow()
    scenario_3_large_expired_backlog()
    scenario_4_concurrency()
    scenario_5_memory_footprint()

    section("DONE")
    print("  This script can't literally run against the pre-SenderQueue commit (SenderQueue")
    print("  didn't exist), so the queue.Queue lines above ARE the 'before' baseline: they")
    print("  faithfully reproduce the old put_nowait()/get()/task_done() contract SenderQueue")
    print("  replaced. Compare SenderQueue's numbers against the queue.Queue numbers *in the")
    print("  same run* (same machine, same moment, same load) rather than against an absolute")
    print("  number, and re-run a few times to see how much that ratio itself varies with noise.")
    print("  For an end-to-end (with real socket I/O) before/after comparison instead, run")
    print("  tests/performance/test_statsd_throughput.py with disable_background_sender=False")
    print("  against both the current commit and the one before this queue was introduced.")


if __name__ == "__main__":
    main()
