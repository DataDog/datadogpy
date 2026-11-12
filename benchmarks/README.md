# Benchmarks: `_telemetry_lock` cost

`telemetry_lock_bench.py` measures whether `self._telemetry_lock`
(introduced to fix the telemetry counter race, see
[`rfcs/telemetry_counters.md`](../rfcs/telemetry_counters.md) and the
`_try_claim_telemetry_flush` docstring in `datadog/dogstatsd/base.py`) costs
anything measurable, across:

- a single thread calling `increment()` in a tight loop (steady state, no
  flush in progress)
- N threads sharing one client with the background sender **disabled**
  (the default) -- every call reaches `_xmit_packet_with_telemetry`
  directly, on its own thread
- N producer threads + 1 real background sender thread, with a real local
  UDP socket (the one scenario where threads can genuinely overlap during a
  critical section, since the socket call releases the GIL)

Run it with:

```
python3 benchmarks/telemetry_lock_bench.py          # ~2-3 min, tighter result
python3 benchmarks/telemetry_lock_bench.py --quick  # ~20-30s, noisier
python3 benchmarks/telemetry_lock_bench.py --tls    # above, plus the TLS prototype comparison (~1-2 min extra)
```

It must be run from inside a git checkout of this repo: it shells out to
`git show` to load the actual pre-fix `datadog/dogstatsd/base.py` as a
second module in the same process (see "Methodology" below) -- nothing is
installed or left behind, a temp file is used and removed immediately.

## Methodology, and two ways this went wrong before landing here

**Attempt 1: checkout old commit, run it; checkout new commit, run it;
diff the wall times.** Rejected: this sandbox's scheduling noise is large
enough that the exact same unchanged code, run in two separate process
invocations a few minutes apart, swung from ~2.6µs to ~8.8µs/call on its
own -- more than 3x with zero code change. That swamps a sub-microsecond
effect.

**Attempt 2: stay in one process, swap `statsd._telemetry_lock` for a
hand-rolled no-op context manager on the same instance.** This looked right
-- same process, same instance, interleaved measurements -- but it
introduced a different, subtler bug: `threading.RLock`'s `__enter__`/
`__exit__` are implemented in C; a hand-rolled Python class's are not, and
calling a Python-defined method (frame setup, bytecode dispatch) costs
*more* than calling a C builtin that does nothing. Measured directly:

```
with real threading.RLock() (C __enter__/__exit__): 101.8 ns/op
with a pure-Python no-op class (__enter__/__exit__): 110.8 ns/op
```

Every "real lock vs no-op" result produced this way came out flat or
negative -- not because the lock is free, but because the "no-op" control
was itself slower than the thing it was supposed to represent as zero cost.

**What's actually used here**: load the real, unmodified pre-fix
`datadog/dogstatsd/base.py` (the commit immediately before
`_telemetry_lock` was introduced) as a second module, in the same process,
via `git show`. One `DogStatsd` instance is built from each class, and
`increment()` calls on both are timed interleaved, in the same process, at
the same moment, under the same scheduler conditions. Both sides are
running real shipped source -- nothing stands in for either side.

## Results

**`--quick` is unreliable for the threaded scenarios -- do not read its
percentages literally.** At the `--quick` workload (6,000-12,000 total ops
per trial, only 6 pairs), thread creation/teardown noise dominates: pure
`Thread().start()`/`.join()` with zero work inside costs 50-250us with a
2-5x run-to-run spread, measured independently of anything in this
benchmark. That swamps the real effect at this trial size and produces
unstable results -- the exact same `multi_thread[t=2]` scenario measured
**+95.5%** in one `--quick` run and **-4.4%** in the next. Neither number
means anything; the bootstrap CI in that run's output spans zero, which is
the tell that it's noise, not a result.

The full (non-`--quick`) run dilutes each trial to 120,000/60,000 total ops
and uses 20 pairs for the threaded scenarios (150 for `single_thread`,
which has no thread-spawn cost to dilute). That collapses the noise into a
stable, CI-backed result:

| Scenario | after (post-fix) | before (pre-fix) | delta | 95% CI on mean paired diff |
|---|---|---|---|---|
| `single_thread` | 2815 ns | 2426 ns | +16.0% | [+295, +457] ns |
| `multi_thread[t=2]` | 8648 ns | 7518 ns | +15.0% | [+690, +1321] ns |
| `multi_thread[t=4]` | 9918 ns | 9094 ns | +9.1% | [+557, +1194] ns |
| `multi_thread[t=8]` | 11152 ns | 9929 ns | +12.3% | [+656, +1710] ns |

(`background_sender[t=N]` wasn't re-run at the diluted budget yet when this
was written -- run the full script to fill it in; expect a similar ~9-16%
based on the pattern above.)

Every CI here excludes zero: this is a real, reliably-measured effect, not
a point estimate riding on noise. And critically, **it does not grow with
thread count** -- 2, 4, and 8 threads all land in the same ~9-16% band as
the single-threaded case. That's the signature of a fixed per-call tax, not
genuine lock contention scaling with concurrency.

## Conclusion

The lock has a real, small, consistently-positive cost of roughly **9-16%
of a full `increment()` call**, flat across thread counts. That lines up
with independent measurements elsewhere in this investigation: an
uncontended `threading.RLock` acquire/release costs ~80-100ns in isolation,
and a single `increment()` call acquires `_telemetry_lock` up to 3 times
(once in `_report()` for the counter, once in
`_try_claim_telemetry_flush()`'s flush-time check, once in
`_xmit_packet_attempt()` for `packets_sent`/`bytes_sent`) -- roughly
3 x 100ns ≈ 300ns, which is ~9-16% of the ~2.4-3µs single-threaded call
measured here.

This is a correctness-for-performance trade that was made deliberately (see
the RFC and the race-condition fixes earlier in this work): without the
lock, concurrent `increment()`/`event()`/`service_check()` calls can lose
counts outright, and the telemetry flush/reset snapshot can be corrupted by
a concurrent update landing mid-flush. A few hundred nanoseconds per call,
on an operation that already costs several microseconds for tag
normalization and payload formatting, was judged an acceptable price for
telemetry counters that are actually correct. If this ever needs
revisiting, the thread-local sharded-counter design discussed earlier in
this work remains the way to remove it, at the cost of materially more
code -- but see "TLS prototype: does sharding actually win?" below before
assuming it does.

**Caveat**: this was all run on CPython with the GIL. The *contention*
argument (no thread blocks waiting on these locks under concurrency,
because the GIL already prevents two threads from being inside a Python
critical section at once) still holds and is unaffected by this
correction -- it's a separate claim from "the fixed per-call acquire cost
is zero," which this benchmark now correctly shows it is not. On
free-threaded CPython (PEP 703, 3.13+ `t` builds) the contention argument
no longer holds either and this should be re-benchmarked there before
assuming the same result.

## TLS prototype: does sharding actually win?

`--tls` adds `TlsCounterDogStatsd`, a prototype that shards `metrics_count`
(the single hottest counter -- touched on every `_report()` call) across a
`threading.local` bucket per producer thread, written with no lock at all.
`self._telemetry_lock` is only taken by whichever thread performs a flush,
to fold every live bucket into `self.metrics_count` before the existing
snapshot/subtract protocol runs unchanged. It is **not** a proposed
implementation -- see its docstring for the known, deliberately-accepted
lost-update gap between a bucket's own thread writing it and a flush
reading-then-zeroing it, the same hazard class `_telemetry_lock` exists to
close. It exists purely to get real numbers for two open questions:

1. Does removing the lock from the write path actually make `increment()`
   faster, given the lock itself measures as a cheap, C-implemented
   ~80-100ns RLock acquire/release (see above)?
2. If it does, does that win survive thread churn -- short-lived threads
   that each pay the one-time `WeakSet.add()` registration cost under
   `_metrics_count_registry_lock` on their first (and maybe only)
   increment, rather than amortizing it over thousands of calls?

Two scenarios probe this, both comparing the current locked counter against
the TLS prototype directly (no pre-fix baseline involved here):

- `multi_thread_tls[t=N]`: N long-lived producer threads, same workload
  shape as `multi_thread[t=N]` above -- the regime where TLS sharding
  should look best, since bucket registration is amortized over many calls
  per thread.
- `thread_churn_tls`: many short-lived threads (20/wave x 15 waves = 300
  threads total), each doing only 2 increments before exiting -- stresses
  bucket registration on nearly every thread instead of amortizing it.

### Results (full run, not `--quick`)

| Scenario | locked (current) | tls (prototype) | delta | 95% CI on mean paired diff (tls minus locked) |
|---|---|---|---|---|
| `multi_thread_tls[t=2]` | 7934 ns | 8207 ns | +3.4% | [+131, +495] ns |
| `multi_thread_tls[t=4]` | 12222 ns | 11872 ns | -2.9% | [-618, +444] ns (crosses zero) |
| `multi_thread_tls[t=8]` | 15618 ns | 16436 ns | +5.2% | [+137, +874] ns |
| `thread_churn_tls[20x15]` | 42670 ns | 44219 ns | +3.6% | [+1072, +7443] ns |

(Absolute ns differ from the `multi_thread`/`background_sender` table
above because these ran later in the same process, under different ambient
load -- irrelevant here since each row is a paired, interleaved comparison
against its own `locked` baseline measured in the same trials, same as the
rest of this file's methodology.)

`surviving TLS buckets after churn + gc.collect()` was **0** out of 300
threads spawned -- confirming the registry does not leak: `WeakSet`
correctly drops a bucket once its owning thread exits and nothing else
holds a strong reference. So question 2 above turned out to be moot,
because the answer to question 1 is already no.

### Conclusion: this naive TLS prototype does not win, and the registry-churn question it was built to answer doesn't matter as a result

Three of four scenarios show the TLS prototype measurably **slower** than
the current lock (CI excludes zero in the slower direction); the fourth
(`t=4`) is statistically indistinguishable from the lock. There is no
scenario here where TLS sharding comes out ahead.

Why the "obvious" optimization doesn't pay off as implemented:
`threading.RLock.__enter__`/`__exit__` are C-implemented and, per the
measurement above, cost ~80-100ns uncontended. The TLS path replaces that
with a *Python-level method call* (`self._metrics_count_bucket()`) plus a
`getattr(self._metrics_count_tls, "bucket", None)` lookup through
`threading.local`'s own (also real, not free) per-thread dict machinery.
Removing a cheap C lock and replacing it with a Python function call plus
a thread-local attribute lookup is not obviously a win, and here it
measures as a wash-to-slight-loss, not the hoped-for improvement.

This doesn't close the door on sharding entirely -- an implementation that
inlines the thread-local check directly in `_report()` (no extra method
call/frame) might claw back enough to tip positive, and that would need
its own real measurement, not an estimate, before being proposed. But it
does mean the registry/thread-churn concern that motivated building the
churn scenario in the first place never got to matter: there is no
baseline win here for churn to erode. Until a version of this is built
that actually beats the lock in the `multi_thread_tls` scenarios, the
thread-churn question is moot and the current locked implementation
remains the better choice as-is.


## Iteration 2: a real, corrected implementation -- opened as a PR for direct comparison

Iteration 1 above (the in-benchmark `TlsCounterDogStatsd` prototype) was
deliberately not production-shaped: its own docstring called out an
accepted lost-update race between a bucket's owning thread and a flush
folding it. That gap has now actually been fixed, for real, in
`datadog/dogstatsd/base.py` on this branch (`_MetricsCountBucket`,
`DogStatsd._metrics_count_bucket()` / `_fold_metrics_count_buckets()` /
the `metrics_count` property) -- opened as a separate PR against `master`
for direct, side-by-side comparison with the single-lock implementation
in PR #1016, per the team's request. `--tls` now loads and benchmarks
**both real implementations** via git (`load_locked_dogstatsd()`), not a
prototype standing in for either side.

### A second, more serious bug found while building the "corrected" version

Fixing the lost-update race surfaced a second, independent bug that
iteration 1's prototype also had (undocumented at the time): the bucket
registry was a `weakref.WeakSet`, kept that way specifically to avoid
leaking one entry per thread for the life of the process. But a thread's
bucket is the *only* strong reference to its own increments -- once the
thread exits, nothing else keeps that bucket alive, so a `WeakSet` drops
it immediately. Any increments made by a thread that exits before the
next flush are **silently lost forever, not just delayed**. Caught by a
new test, `test_metrics_count_survives_thread_exit_before_any_flush`,
which fails fast and loud against the `WeakSet` version (`TypeError:
cannot create weak reference to '_MetricsCountBucket' object`, once the
`__weakref__` slot is also removed as part of the real fix).

This is strictly worse than the single-lock implementation it was meant
to be an alternative to, which never loses a count regardless of thread
lifetime. The fix: use a plain (strong-referencing) `set` instead. That
closes the data-loss hole completely, but trades it for the leak the
`WeakSet` was there to avoid -- see `_MetricsCountBucket`'s docstring in
`datadog/dogstatsd/base.py` and the "surviving TLS buckets" line in the
results below, which confirms the registry now does *not* shrink back
down, by design.

### Results (full run, not `--quick`; both sides are real, unmodified, git-loaded implementations)

| Scenario | locked (PR #1016) | tls (this branch) | delta | 95% CI on mean paired diff (tls minus locked) |
|---|---|---|---|---|
| `multi_thread_tls[t=2]` | 8466 ns | 8686 ns | +2.6% | [-230, +577] ns (crosses zero) |
| `multi_thread_tls[t=4]` | 9805 ns | 9989 ns | +1.9% | [+22, +958] ns |
| `multi_thread_tls[t=8]` | 12190 ns | 12852 ns | +5.4% | [-90, +1069] ns (crosses zero) |
| `thread_churn_tls[20x15]` | 32442 ns | 34411 ns | +6.1% | [+1599, +3589] ns |

`surviving TLS buckets after churn + gc.collect()`: **6000 out of 6000**
threads spawned across the scenario's 20 pairs -- every single bucket
kept alive for the life of the client, exactly as the strong-reference fix
intends. This is the concrete shape of the memory-growth trade-off:
in a long-running process with a thread-pool-per-request pattern, this
number only ever goes up.

### Conclusion: the corrected version is no faster either, and now carries a real memory cost besides

Two of four scenarios show the TLS version measurably **slower** than the
single lock (`t=4` and `thread_churn`, CI excludes zero); the other two
are statistical washes (CI crosses zero). There is no scenario, in either
iteration of this design, where TLS sharding comes out ahead. Fixing the
correctness gaps did not just fail to produce a win -- if anything, the
corrected version (extra per-bucket lock on the write path, a property
getter that performs a real fold on every read, a registry that never
shrinks) is slightly worse than the already-roughly-even naive prototype
from iteration 1.

Combined with iteration 1's finding (a cheap C-implemented `RLock` is hard
to beat with Python-level indirection) and this iteration's finding (a
correctness-complete version of this design trades one serious bug
for permanent memory growth, for no speed benefit), the recommendation is
unchanged and now has two independent reasons behind it instead of one:
**keep the single-lock implementation from PR #1016.** This PR exists so
reviewers can see both the diff and these numbers directly, not as a
merge candidate.
