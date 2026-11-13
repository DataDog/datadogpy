#!/usr/bin/env python3
"""
Benchmark: does self._telemetry_lock (added to fix the telemetry counter
race, see rfcs/telemetry_counters.md and _try_claim_telemetry_flush's
docstring) cost anything measurable?

Methodology
-----------
Two things that DON'T work for this, and why:

1. "Checkout the old commit, run it, checkout the new commit, run it, diff
   the wall times." This sandbox's scheduling noise is large enough that
   the SAME unchanged code, run in two separate process invocations a few
   minutes apart, swings by 2-3x on its own -- that swamps the
   sub-microsecond effect being measured.

2. "Swap self._telemetry_lock for a hand-rolled no-op context manager on
   the same instance." This looked like it fixed (1) by staying in one
   process, but it introduces a different bug: threading.RLock's
   __enter__/__exit__ are implemented in C; a hand-rolled Python class's
   __enter__/__exit__ are not, and calling into a Python method (frame
   setup, bytecode dispatch) is *more* expensive than calling a C builtin
   that does nothing. That consistently made the "real lock" look as fast
   or faster than the "no-op" control, which is a property of the
   benchmark, not of the lock.

What actually works: load the real, unmodified pre-fix datadog/dogstatsd/
base.py as a second module, *in the same process*, via `git show` of the
commit before the lock was added. Then build one DogStatsd instance from
each class and interleave timing real increment() calls on both -- same
process, same moment, same scheduler conditions, and both sides are
running actual shipped source, not a stand-in for either side.

Usage
-----
    python3 benchmarks/telemetry_lock_bench.py [--quick]
    python3 benchmarks/telemetry_lock_bench.py --tls [--quick]
    python3 benchmarks/telemetry_lock_bench.py --micro

Requires being run inside a git checkout of this repo (it shells out to
`git show` to fetch the pre-fix source; nothing is written outside a
temporary file that is cleaned up on exit).

--tls additionally benchmarks TlsCounterDogStatsd (defined below), a
prototype of the thread-local sharded-counter design floated as the way to
remove self._telemetry_lock's cost entirely (see this file's conclusion and
rfcs/telemetry_counters.md). It is NOT a proposed implementation -- it
exists purely to answer one open question with real numbers instead of
estimates: does that design's win survive realistic thread churn, or does
the one-time per-thread registration cost (WeakSet.add() under a registry
lock, on every new thread's first increment) eat the saved lock-acquire
cost when threads are short-lived rather than long-lived producers.

--micro decomposes the --tls end-to-end result (increment() calls, which
also pay for tag normalization, payload formatting, etc.) into the handful
of primitive operations that actually differ between the locked and TLS
counting mechanisms: a bare RLock/Lock acquire, a bare threading.local
getattr, and the real counting line from each implementation, called
directly (not through increment()), single-threaded, no sends, no flushes
-- isolating exactly where the per-call cost difference comes from.
"""
import argparse
import gc
import importlib.util
import os
import random
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import weakref

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from datadog.dogstatsd.base import DogStatsd as NewDogStatsd  # noqa: E402
from datadog.dogstatsd.base import MetricType, validate_cardinality  # noqa: E402
from datadog.dogstatsd.base import random as base_random  # noqa: E402

# The commit that introduced self._telemetry_lock; its parent is "before".
LOCK_INTRODUCED_COMMIT_FINDER = [
    "git", "-C", REPO_ROOT, "log", "--format=%H", "-S", "_telemetry_lock",
    "--", "datadog/dogstatsd/base.py",
]

# The commit that introduced the TLS-sharded metrics_count alternative
# (_MetricsCountBucket); its parent is the single-lock implementation this
# branch is proposed as an alternative to (PR #1016).
TLS_INTRODUCED_COMMIT_FINDER = [
    "git", "-C", REPO_ROOT, "log", "--format=%H", "-S", "_MetricsCountBucket",
    "--", "datadog/dogstatsd/base.py",
]


def _git(*args):
    return subprocess.check_output(["git", "-C", REPO_ROOT] + list(args)).decode().strip()


def _load_dogstatsd_at_commit(commit, module_name):
    """Load datadog/dogstatsd/base.py as it existed at `commit`, as a
    sibling module in this same process, and return its DogStatsd class.

    Shared by load_pre_fix_dogstatsd() and load_locked_dogstatsd() -- both
    need the same "real shipped source, not a stand-in" loading trick (see
    this file's module docstring), just rooted at a different commit.
    """
    source = subprocess.check_output(
        ["git", "-C", REPO_ROOT, "show", "%s:datadog/dogstatsd/base.py" % commit]
    ).decode()

    tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w")
    tmp.write(source)
    tmp.close()

    try:
        spec = importlib.util.spec_from_file_location(module_name, tmp.name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        os.unlink(tmp.name)

    return module.DogStatsd


def load_pre_fix_dogstatsd():
    """Load the real, unmodified pre-fix base.py as a sibling module.

    Returns the pre-fix DogStatsd class. Only datadog/dogstatsd/base.py
    changed in the fix (verified: `git diff --stat <before> <after> --
    datadog/` touches nothing else), so the pre-fix base.py can safely
    import the current repo's other datadog.* submodules (aggregator,
    sender_queue, context, etc.) unchanged.
    """
    commits = subprocess.check_output(LOCK_INTRODUCED_COMMIT_FINDER).decode().split()
    if not commits:
        raise RuntimeError(
            "Could not find the commit that introduced _telemetry_lock. "
            "Run this from a git checkout that includes that history."
        )
    lock_commit = commits[-1]  # oldest match = the commit that introduced it
    before_commit = _git("rev-parse", "%s^" % lock_commit)
    cls = _load_dogstatsd_at_commit(before_commit, "dogstatsd_base_pre_fix")
    return cls, before_commit, lock_commit


def load_locked_dogstatsd():
    """Load the real, unmodified single-global-lock base.py (this repo's
    state immediately before the TLS-sharded metrics_count alternative in
    this branch, i.e. PR #1016 as it stood) as a sibling module.

    Unlike load_pre_fix_dogstatsd()'s pre-fix/post-fix comparison, this
    compares two *fixed* implementations against each other -- both close
    the original telemetry counter race, just with different write-side
    synchronization for metrics_count. Requires the TLS commit (this
    branch's own first commit) to already exist in history, which it does
    once this branch has at least one commit on top of the single-lock
    baseline.
    """
    commits = subprocess.check_output(TLS_INTRODUCED_COMMIT_FINDER).decode().split()
    if not commits:
        raise RuntimeError(
            "Could not find the commit that introduced _MetricsCountBucket. "
            "Run this from a git checkout that includes that history."
        )
    tls_commit = commits[-1]  # oldest match = the commit that introduced it
    locked_commit = _git("rev-parse", "%s^" % tls_commit)
    cls = _load_dogstatsd_at_commit(locked_commit, "dogstatsd_base_locked")
    return cls, locked_commit, tls_commit


class FakeSocket(object):
    """No-op socket for CPU-bound scenarios: isolates lock cost from real I/O."""

    def send(self, data):
        return len(data)

    def sendall(self, data):
        return None

    def settimeout(self, *_):
        pass

    def close(self):
        pass


class _MetricsCountBucket(object):
    """One thread's private metrics_count cell. A plain int/list can't be
    weakly referenced (weakref.WeakSet.add() raises TypeError on either);
    a bare object instance can, via its default __weakref__ slot."""

    def __init__(self):
        self.value = 0


class TlsCounterDogStatsd(NewDogStatsd):
    """Prototype only -- not a proposed implementation.

    Shards metrics_count (the single hottest counter: touched on every
    _report() call, unlike events_count/service_checks_count) across a
    threading.local bucket per producer thread, written without taking
    self._telemetry_lock at all. The lock is only acquired by whichever
    thread performs a flush, to fold every live bucket's value into
    self.metrics_count immediately beforehand -- after that, the existing,
    unmodified snapshot/subtract protocol in _flush_telemetry/
    _reset_telemetry runs exactly as it does today.

    Known, deliberately accepted gaps (fine for a benchmark prototype, not
    for production -- see "TLS prototype, iteration 2" in
    benchmarks/README.md for a corrected, real implementation and what
    fixing these actually cost):

    1. A bucket's owning thread incrementing it concurrently with a fold
       reading-then-zeroing that same bucket is the identical lost-update
       hazard that self._telemetry_lock was introduced to close (see
       _try_claim_telemetry_flush's docstring and the regression tests in
       test_telemetry_flush_does_not_lose_concurrent_increments /
       test_telemetry_flush_is_claimed_by_only_one_thread).
    2. self._metrics_count_buckets being a weakref.WeakSet means a bucket
       disappears -- taking its increments with it, permanently, not just
       delayed -- the instant its owning thread exits, if that happens
       before the next flush folds it in. Found the hard way while turning
       this into a real implementation: see _MetricsCountBucket in
       datadog/dogstatsd/base.py on this branch for the fix (a strong-
       referencing set, trading this data loss for unbounded memory growth
       instead) and test_metrics_count_survives_thread_exit_before_any_flush
       for the regression test that caught it.
    """

    def __init__(self, *args, **kwargs):
        super(TlsCounterDogStatsd, self).__init__(*args, **kwargs)
        self._metrics_count_buckets = weakref.WeakSet()
        self._metrics_count_registry_lock = threading.Lock()
        self._metrics_count_tls = threading.local()

    def _metrics_count_bucket(self):
        bucket = getattr(self._metrics_count_tls, "bucket", None)
        if bucket is None:
            # A plain list/int can't be weakly referenced (WeakSet.add()
            # raises TypeError on one); a bare object instance's default
            # __weakref__ slot can, so that's the thread's private counter.
            bucket = _MetricsCountBucket()
            self._metrics_count_tls.bucket = bucket
            # One-time cost per thread's first increment, not per call --
            # this is exactly the cost the thread-churn scenario stresses.
            with self._metrics_count_registry_lock:
                self._metrics_count_buckets.add(bucket)
        return bucket

    def _report(self, metric, metric_type, value, tags, sample_rate, timestamp=0, sampling=True, cardinality=None):
        # Identical to DogStatsd._report() except the counting line: no
        # self._telemetry_lock, write straight to this thread's own bucket.
        if value is None:
            return True

        if self._enabled is not True:
            return True

        if self._telemetry:
            self._metrics_count_bucket().value += 1

        if sampling:
            if sample_rate is None:
                sample_rate = self.default_sample_rate

            if sample_rate != 1 and base_random() > sample_rate:
                return True

        allows_timestamp = metric_type == MetricType.GAUGE or metric_type == MetricType.COUNT
        if not allows_timestamp or timestamp < 0:
            timestamp = 0

        if cardinality is None:
            cardinality = self.cardinality

        validate_cardinality(cardinality)

        payload = self._serialize_metric(metric, metric_type, value, tags, sample_rate, timestamp, cardinality)
        timestamped = timestamp > 0
        return self._send(payload, timestamped)

    def _fold_metrics_count_buckets(self):
        """Merge every live thread's bucket into self.metrics_count, under
        self._telemetry_lock, immediately before the inherited flush logic
        reads self.metrics_count into its snapshot."""
        with self._metrics_count_registry_lock:
            buckets = list(self._metrics_count_buckets)
        for bucket in buckets:
            self.metrics_count += bucket.value
            bucket.value = 0

    def _flush_telemetry(self):
        with self._telemetry_lock:
            self._fold_metrics_count_buckets()
        return super(TlsCounterDogStatsd, self)._flush_telemetry()


def best_of(fn, repeats):
    best = None
    for _ in range(repeats):
        gc.disable()
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        gc.enable()
        dt = t1 - t0
        if best is None or dt < best:
            best = dt
    return best


def ab_measure(run_after, run_before, total_ops, pairs, repeats_per_side=1,
                settle_after=None, settle_before=None):
    """Interleave timings of the real after-fix and real before-fix call paths.

    settle_after/settle_before, if given, are called (untimed, after the
    elapsed time for that trial has already been recorded) once a side's
    trial finishes. Use this when a side leaves background work running
    past the end of its own measured call (e.g. a background sender thread
    still draining a queue) -- without draining it before the other side's
    turn, that leftover work competes for CPU/GIL with whichever side is
    measured next, contaminating its timing with noise that has nothing to
    do with what's actually being compared.
    """
    after_results = []
    before_results = []
    for i in range(pairs):
        order = ("after", "before") if i % 2 == 0 else ("before", "after")
        for which in order:
            run = run_after if which == "after" else run_before
            elapsed = best_of(run, repeats_per_side)
            ns_per_op = elapsed / total_ops * 1e9
            (after_results if which == "after" else before_results).append(ns_per_op)
            settle = settle_after if which == "after" else settle_before
            if settle is not None:
                settle()
    return after_results, before_results


def scenario_single_thread(OldDogStatsd, n, pairs):
    """Steady-state increment() calls on one thread, no telemetry flush."""
    after = NewDogStatsd(disable_background_sender=True, disable_telemetry=False)
    after.socket = FakeSocket()
    after._last_flush_time = float("inf")

    before = OldDogStatsd(disable_background_sender=True, disable_telemetry=False)
    before.socket = FakeSocket()
    before._last_flush_time = float("inf")

    def run_after():
        for _ in range(n):
            after.increment("bench.metric", tags=["a:b", "c:d"])

    def run_before():
        for _ in range(n):
            before.increment("bench.metric", tags=["a:b", "c:d"])

    return ab_measure(run_after, run_before, n, pairs)


def scenario_multi_thread(OldDogStatsd, n_threads, per_thread, pairs):
    """N threads sharing one client, synchronous send (disable_background_sender=True,
    the default) -- every increment() call reaches _xmit_packet_with_telemetry
    directly on its own thread. This is the scenario
    _try_claim_telemetry_flush's docstring calls out.
    """
    after = NewDogStatsd(disable_background_sender=True, disable_telemetry=False)
    after.socket = FakeSocket()
    after._last_flush_time = float("inf")

    before = OldDogStatsd(disable_background_sender=True, disable_telemetry=False)
    before.socket = FakeSocket()
    before._last_flush_time = float("inf")

    def make_run(statsd):
        def worker():
            for _ in range(per_thread):
                statsd.increment("bench.metric", tags=["a:b", "c:d"])

        def run():
            threads = [threading.Thread(target=worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        return run

    return ab_measure(make_run(after), make_run(before), n_threads * per_thread, pairs)


def scenario_background_sender(OldDogStatsd, n_threads, per_thread, pairs):
    """N producer threads + 1 real background sender thread each, real UDP sockets.

    Unlike scenario_multi_thread, the sender thread's socket call genuinely
    releases the GIL, so this is the scenario where real inter-thread
    overlap (not just GIL-serialized timeslicing) can occur near the lock.
    """
    def make_client(cls):
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        stop = threading.Event()

        def drain():
            listener.settimeout(0.1)
            while not stop.is_set():
                try:
                    listener.recvfrom(65535)
                except socket.timeout:
                    pass

        dthread = threading.Thread(target=drain)
        dthread.daemon = True
        dthread.start()

        statsd = cls(host="127.0.0.1", port=port, disable_background_sender=False, disable_telemetry=False)
        teardown = (statsd, stop, dthread, listener)
        return statsd, teardown

    after, after_teardown = make_client(NewDogStatsd)
    before, before_teardown = make_client(OldDogStatsd)

    def make_run(statsd):
        def worker():
            for _ in range(per_thread):
                statsd.increment("bench.metric", tags=["a:b", "c:d"])

        def run():
            threads = [threading.Thread(target=worker) for _ in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        return run

    # Both clients' background sender threads keep running for the whole
    # scenario. Without draining a side's queue right after its own trial,
    # it keeps churning through a backlog -- competing for CPU/GIL -- while
    # the *other* side is being timed next, contaminating that measurement
    # with noise that has nothing to do with what's being compared. This is
    # untimed: it runs after best_of() has already recorded the trial's
    # elapsed time, so it doesn't inflate the measured per-call cost itself.
    results = ab_measure(
        make_run(after), make_run(before), n_threads * per_thread, pairs,
        settle_after=lambda: after.wait_for_pending(timeout=5),
        settle_before=lambda: before.wait_for_pending(timeout=5),
    )

    for statsd, stop, dthread, listener in (after_teardown, before_teardown):
        statsd.wait_for_pending(timeout=5)
        statsd.stop()
        stop.set()
        dthread.join(2)
        listener.close()

    return results


def _make_multi_thread_run(statsd, n_threads, per_thread):
    def worker():
        for _ in range(per_thread):
            statsd.increment("bench.metric", tags=["a:b", "c:d"])

    def run():
        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    return run


def scenario_multi_thread_locked_vs_tls(LockedDogStatsd, n_threads, per_thread, pairs):
    """Steady state: N long-lived producer threads sharing one client,
    synchronous send -- identical workload to scenario_multi_thread, but
    comparing the real single-lock implementation (loaded via
    load_locked_dogstatsd(), i.e. PR #1016 as it stood) against the real
    TLS-sharded implementation (NewDogStatsd -- this branch's working
    tree) instead of the superseded in-benchmark prototype class. Each
    thread does `per_thread` increments, so the one-time per-thread TLS
    bucket registration cost is amortized over many calls: this is the
    regime the TLS design should look best in.
    """
    locked = LockedDogStatsd(disable_background_sender=True, disable_telemetry=False)
    locked.socket = FakeSocket()
    locked._last_flush_time = float("inf")

    tls = NewDogStatsd(disable_background_sender=True, disable_telemetry=False)
    tls.socket = FakeSocket()
    tls._last_flush_time = float("inf")

    locked_results, tls_results = ab_measure(
        _make_multi_thread_run(locked, n_threads, per_thread),
        _make_multi_thread_run(tls, n_threads, per_thread),
        n_threads * per_thread, pairs,
    )
    return locked_results, tls_results


def scenario_thread_churn_locked_vs_tls(LockedDogStatsd, threads_per_wave, increments_per_thread, waves, pairs):
    """Short-lived threads: each thread does only `increments_per_thread`
    calls before exiting, repeated over `waves` generations of
    `threads_per_wave` fresh threads. Unlike
    scenario_multi_thread_locked_vs_tls, this stresses TLS bucket
    registration (set.add() under _metrics_count_registry_lock) on nearly
    every thread instead of amortizing it over thousands of calls -- this
    is the regime that could erode or erase the TLS design's win, and is
    the open question this benchmark extension exists to answer. Compares
    the real single-lock implementation against the real TLS
    implementation (NewDogStatsd), same as scenario_multi_thread_locked_vs_tls.
    """
    total_ops = threads_per_wave * increments_per_thread * waves

    locked = LockedDogStatsd(disable_background_sender=True, disable_telemetry=False)
    locked.socket = FakeSocket()
    locked._last_flush_time = float("inf")

    tls = NewDogStatsd(disable_background_sender=True, disable_telemetry=False)
    tls.socket = FakeSocket()
    tls._last_flush_time = float("inf")

    def make_run(statsd):
        def worker():
            for _ in range(increments_per_thread):
                statsd.increment("bench.metric", tags=["a:b", "c:d"])

        def run():
            for _ in range(waves):
                threads = [threading.Thread(target=worker) for _ in range(threads_per_wave)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

        return run

    locked_results, tls_results = ab_measure(
        make_run(locked), make_run(tls), total_ops, pairs,
    )

    # Not timed (recorded after ab_measure returns): does the bucket
    # registry actually shrink back down as churned-through threads exit,
    # or does it grow unboundedly (the data-loss-vs-memory-growth trade-off
    # documented on _MetricsCountBucket)? Relevant to whether this design
    # is safe for a thread-pool-per-request workload. Expected: it does NOT
    # shrink back to 0 any more (that was the bug) -- it should land at
    # exactly threads_per_wave * waves (every thread's bucket kept alive).
    gc.collect()
    surviving_buckets = len(tls._metrics_count_buckets)

    return locked_results, tls_results, surviving_buckets


def multi_measure(variants, total_ops, pairs, repeats_per_side=1):
    """Like ab_measure, generalized to any number of labeled variants.

    `variants` is a dict of label -> zero-arg callable. Each of `pairs`
    rounds times every variant once, rotating which label goes first so no
    variant is systematically measured first or last (which would bias it
    from whatever warmup/cooldown scheduling effect goes with that
    position, the same concern ab_measure's alternating order addresses
    for the two-variant case).

    Returns a dict of label -> list of ns-per-op samples, one list per
    variant, aligned by round (results[label][i] and results[other][i]
    were measured in the same round i, so paired-diff statistics are
    valid the same way they are for ab_measure's two-variant case).
    """
    labels = list(variants.keys())
    results = {label: [] for label in labels}
    for i in range(pairs):
        order = labels[i % len(labels):] + labels[:i % len(labels)]
        for label in order:
            elapsed = best_of(variants[label], repeats_per_side)
            ns_per_op = elapsed / total_ops * 1e9
            results[label].append(ns_per_op)
    return results


def report_multi(name, results, baseline_label):
    """Report every variant in `results` against `baseline_label`'s median,
    each with its own bootstrap CI on the mean paired difference -- same
    statistics as report()/report_locked_vs_tls(), generalized to N-1
    comparisons against one shared baseline instead of a single A/B pair.
    """
    baseline = results[baseline_label]
    baseline_median = statistics.median(baseline)
    print("%s  [n=%d trials each]" % (name, len(baseline)))
    print("  %-32s %7.0f ns  (baseline)" % (baseline_label, baseline_median))
    for label, values in results.items():
        if label == baseline_label:
            continue
        med = statistics.median(values)
        delta_ns = med - baseline_median
        delta_pct = delta_ns / baseline_median * 100 if baseline_median else float("nan")
        diffs = [v - b for v, b in zip(values, baseline)]
        mean_diff = statistics.mean(diffs)
        random.seed(0)
        boot_means = []
        for _ in range(2000):
            sample = [random.choice(diffs) for _ in diffs]
            boot_means.append(statistics.mean(sample))
        boot_means.sort()
        ci_lo = boot_means[int(0.025 * len(boot_means))]
        ci_hi = boot_means[int(0.975 * len(boot_means))]
        print(
            "  %-32s %7.0f ns  delta=%+6.0f ns (%+5.1f%%)  mean paired diff=%+6.0f ns  "
            "95%% CI: [%+.0f, %+.0f] ns" % (label, med, delta_ns, delta_pct, mean_diff, ci_lo, ci_hi)
        )
    for label in results:
        print("  %-32s samples: %s" % (label, [round(x) for x in results[label]]))


def scenario_micro(LockedDogStatsd, n, pairs):
    """Decompose the counting-mechanism cost into its primitive pieces.

    Single-threaded, no sends, no flushes (both statsd instances have
    _last_flush_time pinned to the far future): this isolates exactly the
    lines that differ between the two implementations' _report(), called
    directly rather than through the much larger increment()/_report()
    (tag normalization, payload formatting, sampling, etc. -- all shared,
    all unaffected by this change, and would otherwise dilute the
    difference being measured here).

    locked = LockedDogStatsd(...): the real #1016 implementation, loaded
    via git by load_locked_dogstatsd() in the caller, so "real_locked_write"
    below calls that real instance's real self._telemetry_lock -- not a
    reimplementation of it.
    """
    locked = LockedDogStatsd(disable_background_sender=True, disable_telemetry=False)
    locked.socket = FakeSocket()
    locked._last_flush_time = float("inf")

    tls = NewDogStatsd(disable_background_sender=True, disable_telemetry=False)
    tls.socket = FakeSocket()
    tls._last_flush_time = float("inf")

    bare_rlock = threading.RLock()
    bare_rlock_counter = [0]

    bare_lock = threading.Lock()
    bare_lock_counter = [0]

    bare_tls = threading.local()
    bare_tls.bucket = object()  # already populated: isolates the getattr itself, not first-touch setup

    def bare_rlock_increment():
        for _ in range(n):
            with bare_rlock:
                bare_rlock_counter[0] += 1

    def bare_lock_increment():
        for _ in range(n):
            with bare_lock:
                bare_lock_counter[0] += 1

    def bare_tls_getattr():
        for _ in range(n):
            getattr(bare_tls, "bucket", None)

    def real_locked_write():
        # The exact line from the locked implementation's _report(), via a
        # real instance -- not a hand-rolled stand-in (see this file's
        # module docstring on why that distinction matters).
        for _ in range(n):
            with locked._telemetry_lock:
                locked.metrics_count += 1

    def real_tls_bucket_lookup_only():
        # Isolates DogStatsd._metrics_count_bucket() itself -- the Python
        # method call plus its internal threading.local getattr -- without
        # the bucket.lock acquisition that follows it in _report().
        for _ in range(n):
            tls._metrics_count_bucket()

    def real_tls_write():
        # The exact lines from the TLS implementation's _report(), via a
        # real instance.
        for _ in range(n):
            bucket = tls._metrics_count_bucket()
            with bucket.lock:
                bucket.value += 1

    variants = {
        "bare_rlock_increment": bare_rlock_increment,
        "bare_lock_increment": bare_lock_increment,
        "bare_tls_getattr": bare_tls_getattr,
        "real_locked_write": real_locked_write,
        "real_tls_bucket_lookup_only": real_tls_bucket_lookup_only,
        "real_tls_write": real_tls_write,
    }
    return multi_measure(variants, n, pairs)


def report_locked_vs_tls(name, locked_results, tls_results):
    """Like report(), but labeled for the locked-counter-vs-TLS-prototype
    comparison instead of the post-fix-vs-pre-fix one, so the two are never
    confused in the output."""
    locked_median = statistics.median(locked_results)
    tls_median = statistics.median(tls_results)
    delta_ns = tls_median - locked_median
    delta_pct = delta_ns / locked_median * 100 if locked_median else float("nan")
    print("%-28s locked=%7.0f ns  tls=%7.0f ns  delta=%+7.0f ns (%+5.1f%%)  [n=%d pairs]" % (
        name, locked_median, tls_median, delta_ns, delta_pct, len(locked_results),
    ))

    diffs = [t - l for t, l in zip(tls_results, locked_results)]
    mean_diff = statistics.mean(diffs)
    if len(diffs) > 1:
        random.seed(0)
        boot_means = []
        for _ in range(2000):
            sample = [random.choice(diffs) for _ in diffs]
            boot_means.append(statistics.mean(sample))
        boot_means.sort()
        ci_lo = boot_means[int(0.025 * len(boot_means))]
        ci_hi = boot_means[int(0.975 * len(boot_means))]
        print("  mean paired diff (tls - locked): %+.0f ns   95%% bootstrap CI: [%+.0f, %+.0f] ns" % (
            mean_diff, ci_lo, ci_hi,
        ))
    print("  locked samples: %s" % [round(x) for x in locked_results])
    print("  tls    samples: %s" % [round(x) for x in tls_results])


def report(name, after_results, before_results):
    a = statistics.median(after_results)
    b = statistics.median(before_results)
    delta_ns = a - b
    delta_pct = delta_ns / b * 100 if b else float("nan")
    print("%-28s after=%7.0f ns  before=%7.0f ns  delta=%+7.0f ns (%+5.1f%%)  [n=%d pairs]" % (
        name, a, b, delta_ns, delta_pct, len(after_results),
    ))

    # Paired difference (after[i] - before[i], same trial i on both sides) is
    # the statistic that actually matters here -- it cancels out whatever
    # process-wide drift happened between the two measurements in a pair,
    # which two independent medians don't. A bootstrap 95% CI on its mean
    # says whether the effect is distinguishable from pair-to-pair noise, not
    # just what the point estimate happens to be.
    diffs = [a - b for a, b in zip(after_results, before_results)]
    mean_diff = statistics.mean(diffs)
    if len(diffs) > 1:
        random.seed(0)
        boot_means = []
        for _ in range(2000):
            sample = [random.choice(diffs) for _ in diffs]
            boot_means.append(statistics.mean(sample))
        boot_means.sort()
        ci_lo = boot_means[int(0.025 * len(boot_means))]
        ci_hi = boot_means[int(0.975 * len(boot_means))]
        print("  mean paired diff: %+.0f ns   95%% bootstrap CI: [%+.0f, %+.0f] ns" % (mean_diff, ci_lo, ci_hi))
    print("  after  samples: %s" % [round(x) for x in after_results])
    print("  before samples: %s" % [round(x) for x in before_results])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="smaller sizes, fewer pairs, faster/less precise")
    parser.add_argument(
        "--tls", action="store_true",
        help="also benchmark the real single-lock implementation (PR #1016) against the "
             "real TLS-sharded implementation (this branch's working tree), in both a "
             "long-lived-thread and a thread-churn scenario (see load_locked_dogstatsd() "
             "and _MetricsCountBucket's docstrings)",
    )
    parser.add_argument(
        "--micro", action="store_true",
        help="decompose the --tls end-to-end result into its primitive sub-costs (bare "
             "RLock/Lock acquire, bare threading.local getattr, and each implementation's "
             "real counting line called directly) -- see scenario_micro()",
    )
    args = parser.parse_args()

    OldDogStatsd, before_commit, lock_commit = load_pre_fix_dogstatsd()
    print(
        "comparing: %s (pre-fix, no lock at all) vs current working tree "
        "(telemetry_lock introduced at %s; this branch's working tree also carries the "
        "TLS-sharded metrics_count alternative on top -- see --tls for that comparison "
        "specifically)" % (before_commit[:10], lock_commit[:10])
    )
    print()

    if args.quick:
        # Deliberately noisy/fast. Thread creation+join alone costs 50-250us
        # with a 2-5x run-to-run spread (measured independently of anything
        # here), and these trials are too small to average that out -- do
        # not trust the per-scenario percentage from --quick for the
        # threaded scenarios, only use it to sanity-check the script runs.
        single_n, single_pairs = 10_000, 10
        mt_pairs, bg_pairs = 6, 6
        mt_budget, bg_budget = 6_000, 3_000
    else:
        # single_thread is cheap (no thread spawn/socket overhead), so it gets
        # many more independent pairs for a tight confidence interval.
        #
        # The threaded budgets are calibrated, not arbitrary: at the --quick
        # budget (6,000-12,000 total ops/trial), thread spawn/join noise
        # (50-250us, 2-5x run-to-run swing) dominated the measurement and
        # produced unstable, meaningless percentages (+95% in one run, -4% in
        # the next, for the identical scenario). Diluting to 120,000 total
        # ops/trial with 20 pairs collapsed that into a stable, CI-backed
        # ~9-16% result consistent across t=2/4/8 and with single_thread.
        single_n, single_pairs = 20_000, 150
        mt_pairs, bg_pairs = 20, 20
        mt_budget, bg_budget = 120_000, 60_000

    report("single_thread", *scenario_single_thread(OldDogStatsd, single_n, single_pairs))
    print()

    for n_threads in (2, 4, 8):
        per_thread = max(500, mt_budget // n_threads)
        report(
            "multi_thread[t=%d]" % n_threads,
            *scenario_multi_thread(OldDogStatsd, n_threads, per_thread, mt_pairs)
        )
        print()

    for n_threads in (2, 4, 8):
        per_thread = max(300, bg_budget // n_threads)
        report(
            "background_sender[t=%d]" % n_threads,
            *scenario_background_sender(OldDogStatsd, n_threads, per_thread, bg_pairs)
        )
        print()

    if args.tls:
        LockedDogStatsd, locked_commit, tls_commit = load_locked_dogstatsd()
        print(
            "--- real single-lock implementation (%s, PR #1016) vs real TLS-sharded "
            "implementation (%s, current working tree) ---" % (locked_commit[:10], tls_commit[:10])
        )
        print()

        if args.quick:
            tls_mt_pairs, tls_mt_budget = 6, 6_000
            waves, threads_per_wave, increments_per_thread, churn_pairs = 3, 8, 2, 6
        else:
            tls_mt_pairs, tls_mt_budget = 20, 120_000
            # Calibrated the same way the multi_thread budgets above were:
            # enough waves/threads that thread-spawn noise (50-250us/thread,
            # 2-5x run-to-run swing) doesn't swamp the per-call effect being
            # measured, while keeping increments_per_thread small (2) so
            # registration dominates each thread's own work, which is the
            # whole point of this scenario.
            waves, threads_per_wave, increments_per_thread, churn_pairs = 15, 20, 2, 20

        for n_threads in (2, 4, 8):
            per_thread = max(500, tls_mt_budget // n_threads)
            report_locked_vs_tls(
                "multi_thread_tls[t=%d] (long-lived)" % n_threads,
                *scenario_multi_thread_locked_vs_tls(LockedDogStatsd, n_threads, per_thread, tls_mt_pairs)
            )
            print()

        locked_results, tls_results, surviving_buckets = scenario_thread_churn_locked_vs_tls(
            LockedDogStatsd, threads_per_wave, increments_per_thread, waves, churn_pairs
        )
        report_locked_vs_tls(
            "thread_churn_tls[%d threads/wave x %d waves]" % (threads_per_wave, waves),
            locked_results, tls_results,
        )
        print(
            "  surviving TLS buckets after churn + gc.collect(): %d (threads spawned: %d "
            "-- %d waves x %d threads/wave x %d pairs, since the tls client is reused "
            "across every interleaved pair in ab_measure)" % (
                surviving_buckets, threads_per_wave * waves * churn_pairs,
                waves, threads_per_wave, churn_pairs,
            )
        )
        print()

    if args.micro:
        LockedDogStatsd, locked_commit, tls_commit = load_locked_dogstatsd()
        print(
            "--- micro: decomposing the counting-mechanism cost (%s locked vs %s tls) ---"
            % (locked_commit[:10], tls_commit[:10])
        )
        print()

        micro_n, micro_pairs = (2_000, 8) if args.quick else (50_000, 30)
        results = scenario_micro(LockedDogStatsd, micro_n, micro_pairs)
        report_multi("metrics_count counting mechanism, per call", results, "real_locked_write")
        print()
        print(
            "  Read top to bottom: bare_rlock/bare_lock/bare_tls_getattr are generic "
            "primitives (not tied to either implementation), included so the two "
            "real_* rows below can be explained in terms of them. real_locked_write is "
            "the baseline (today's #1016 implementation); real_tls_bucket_lookup_only "
            "isolates DogStatsd._metrics_count_bucket() alone (the Python method call "
            "plus its internal threading.local getattr, no lock use yet); "
            "real_tls_write adds the per-bucket Lock acquire on top, i.e. the full TLS "
            "write path, directly comparable to real_locked_write."
        )
        print()


if __name__ == "__main__":
    main()
