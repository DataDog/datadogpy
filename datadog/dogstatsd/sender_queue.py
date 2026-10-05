import collections
import logging
import sys
import threading

from datadog.util.compat import monotonic

log = logging.getLogger("datadog.dogstatsd")

if sys.version_info[:2] >= (3, 5):
    from typing import Callable, Dict, Optional, Union  # noqa: F401


# Sentinel telling the background sender thread to shut down.
Stop = object()

# What the queue can hold. A payload is either a bare string (replay-safe, no
# expiry state needed) or a PendingPayload (subject to expiry); Stop is the
# only other thing that ever goes in, and is matched by identity.
if sys.version_info[:2] >= (3, 5):
    QueuedItem = Union[str, "PendingPayload"]  # noqa: F401
    QueuedItemOrStop = Union[str, "PendingPayload", object]  # noqa: F401


class PendingPayload(object):
    """A packet queued for the background sender that can go stale.

    Only payloads subject to expiry are wrapped in this. A replay-safe
    payload -- one carrying its own explicit timestamp, so that delivering it
    late doesn't change what it means -- is queued as the bare packet string
    instead, because it needs none of the state here. The queue therefore
    reads replay-safety off the entry's *type* rather than a stored flag (see
    SenderQueue._expired() and is_replay_safe()), which keeps ~56 bytes per
    replay-safe entry out of the queue and keeps those entries out of the
    cyclic GC's traversal set entirely, since str holds no references.

    :ivar payload: The already-serialized packet text (including its
        trailing newline), ready to be written to the socket.
    :ivar enqueued_at: A monotonic timestamp recorded when the payload
        became eligible for sending (i.e. when it was put on the queue).
        Used to decide whether it has been sitting in the queue for too
        long to still be worth sending.
    """

    __slots__ = ("payload", "enqueued_at")

    def __init__(self, payload, enqueued_at):
        # type: (str, float) -> None
        self.payload = payload
        self.enqueued_at = enqueued_at


def is_replay_safe(item):
    # type: (Union[str, PendingPayload]) -> bool
    """True when this queue entry is exempt from expiry.

    Replay-safe entries are queued as bare strings; everything subject to
    expiry is wrapped in PendingPayload. Centralised here so the type test
    isn't repeated at every site that cares.
    """
    return not isinstance(item, PendingPayload)


def payload_text(item):
    # type: (Union[str, PendingPayload]) -> str
    """The serialized packet text of a queue entry, whichever form it took."""
    if isinstance(item, PendingPayload):
        return item.payload
    return item


class SenderQueue(object):
    """Bounded hand-off queue between application threads and the background sender thread.

    put() never rejects a payload outright. When the queue is already at its
    maximum size, what happens depends on put_timeout:
      - 0 (the default): no waiting at all -- the oldest entry is dropped
        immediately to make room, along with any additional expired entries
        left at the front.
      - None: put() blocks the calling thread indefinitely, waiting for the
        sender thread to drain a slot. It will wait forever if nothing ever
        does -- this is an explicit opt-in to unbounded backpressure on the
        calling thread.
      - a positive number: put() blocks the calling thread for up to that
        many seconds waiting for a slot; if the wait times out without one
        opening up, it falls back to the same drop-oldest eviction as the
        0 case.

    get() drops expired entries lazily too, from the front, before returning
    the next payload actually worth handing to the sender.

    A payload that fails to send (e.g. because the connection is down) can be
    handed back with requeue_front() so it's retried first. That still
    respects both the expiry check and the size limit though: the queue
    must never grow past maxsize, and a payload that's gone stale while it
    was being (re)tried is dropped rather than requeued. requeue_front()
    never blocks on put_timeout.
    """

    def __init__(self, maxsize, expiry_seconds, on_drop_queue_full, on_drop_expired, put_timeout=0):
        # type: (int, float, Callable[[QueuedItem], None], Callable[[QueuedItem], None], Optional[float]) -> None  # noqa: E501
        self._maxsize = maxsize
        self._expiry_seconds = expiry_seconds
        self._on_drop_queue_full = on_drop_queue_full
        self._on_drop_expired = on_drop_expired
        self._put_timeout = put_timeout
        self._deque = collections.deque()  # type: collections.deque
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._all_tasks_done = threading.Condition(self._lock)

        # Keep track of the tasks that are being processed. A task pulled from the queue may
        # be returned if the connection fails, so we don't consider the queue empty until
        # all tasks have been dropped or sent.
        self._unfinished_tasks = 0

        # Set by close(): tells a put() that is (or will be) waiting for room
        # to stop waiting immediately instead of riding out put_timeout, or
        # forever if put_timeout is None. See close()'s docstring for why
        # this exists.
        self._closing = False

        # The items currently handed out by get() and not yet finished via
        # requeue_front() or task_done(), keyed by id(item). SenderQueue is
        # single-consumer by design (one background sender thread), so this
        # normally holds at most one entry at a time. Tracking it lets
        # requeue_front()/task_done() verify their precondition -- that the
        # item they're handed really is the one get() currently has out of
        # the queue -- so the misuse that would otherwise silently corrupt
        # _unfinished_tasks (a double finish, a double requeue, or a requeue
        # of an already-finished item) fails loudly instead of drifting the
        # counter. The item itself is held in the value to keep it alive
        # (and its id stable) for as long as the entry exists.
        self._in_flight = {}  # type: Dict[int, QueuedItemOrStop]

    def _expired(self, item, now):
        # type: (QueuedItem, float) -> bool
        if not isinstance(item, PendingPayload):
            # A bare string is a replay-safe payload: it carries its own
            # timestamp, so it never goes stale (see PendingPayload).
            return False
        return (now - item.enqueued_at) > self._expiry_seconds

    def _make_room_locked(self):
        # type: () -> None
        """Drop the oldest entry, plus any further expired entries at the front.

        Called with self._lock already held, and only when the queue is at
        capacity. Never touches the Stop sentinel: by the time it's queued,
        nothing else is ever put on the queue again, so it can only ever be
        the newest entry, never the one being evicted here.
        """
        if not self._deque or self._deque[0] is Stop:
            return

        now = monotonic()
        oldest = self._deque.popleft()
        # The oldest entry is always dropped to make room.
        if self._expired(oldest, now):
            self._on_drop_expired(oldest)
        else:
            self._on_drop_queue_full(oldest)
        self._finish_task_locked()

        # Keep clearing out additional stale entries left at the front.
        # If any additional entries were cleared out notify not_full as the
        # queue will now have available space for additional entries.
        reclaimed = 0
        while self._deque and self._deque[0] is not Stop and self._expired(self._deque[0], now):
            self._on_drop_expired(self._deque.popleft())
            self._finish_task_locked()
            reclaimed += 1

        if reclaimed:
            self._not_full.notify(reclaimed)

    def put(self, item):
        # type: (QueuedItemOrStop) -> None
        """Queue a payload (or the Stop sentinel).

        If the queue is full: waits for room according to put_timeout --
        forever if it's None, up to put_timeout seconds if it's a positive
        number, or not at all if it's 0 (the default) -- then falls back to
        evicting the oldest entry (see _make_room_locked()) if the queue is
        still full once the wait is over. Either way, put() never rejects
        the payload outright. A close() call (from any thread) cuts any of
        that waiting short immediately, regardless of put_timeout.
        """
        with self._not_empty:
            if item is not Stop and self._maxsize > 0 and len(self._deque) >= self._maxsize:
                if self._closing:
                    pass  # Already closing: don't wait at all, straight to eviction below.
                elif self._put_timeout is None:
                    # Wait forever: an explicit opt-in to unbounded
                    # backpressure on the calling thread. close() is what
                    # keeps this from actually being forever once a shutdown
                    # is underway.
                    while len(self._deque) >= self._maxsize and not self._closing:
                        self._not_full.wait()
                elif self._put_timeout > 0:
                    deadline = monotonic() + self._put_timeout
                    while len(self._deque) >= self._maxsize and not self._closing:
                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            break
                        self._not_full.wait(remaining)
                # else: put_timeout is 0 (or negative) -- no wait at all,
                # straight to eviction below.

                if len(self._deque) >= self._maxsize:
                    self._make_room_locked()

            self._deque.append(item)
            self._unfinished_tasks += 1
            self._not_empty.notify()

    def close(self):
        # type: () -> None
        """Wake any put() currently waiting for room, immediately.

        A put() blocked waiting for space in a full queue holds no lock this
        method needs -- Condition.wait() releases the underlying lock while
        waiting -- so this always runs promptly, even while some other
        thread is stuck inside that wait (that stuck thread is exactly what
        this is for). Without it, a put() with put_timeout=None waits
        forever for room that will never open up once nothing is draining
        the queue, and even a bounded put_timeout can outlast whatever
        timeout a caller trying to shut things down asked for -- see
        DogStatsd._stop_sender_thread(), which calls this before it needs
        the *caller's* lock (_buffer_lock) that a stuck put() would
        otherwise be holding for the entire wait.

        Sticky: once closed, no future put() on this queue ever waits for
        room again, regardless of put_timeout -- it goes straight to
        eviction, like put_timeout=0. There is no matching "reopen": a fresh
        shutdown starts with a fresh SenderQueue instead.

        This does not stop put()/get() from working, and does not reject or
        drop anything by itself -- it only ends a wait early. Refusing new
        payloads outright is the caller's job (see DogStatsd._send_to_server(),
        which checks _sender_stopping before ever calling put()).
        """
        with self._not_full:
            self._closing = True
            self._not_full.notify_all()

    def requeue_front(self, item):
        # type: (QueuedItem) -> None
        """Put an in-flight payload back at the front after a failed send attempt.

        The payload was already accounted for by the put() that originally
        queued it (its task isn't done yet), so a successful requeue here
        doesn't touch _unfinished_tasks. But it's still subject to the same
        rules as any other entry: an item that's expired while it was being
        (re)tried is dropped instead of requeued, and the queue is never
        allowed to grow past maxsize -- if it's already full, the requeue is
        dropped too rather than evicting something else to make room for it.
        Either way, a drop here finishes the task that put() started.
        """
        with self._not_empty:
            # The item handed back must be exactly the one get() currently has
            # out of the queue. SenderQueue is single-consumer; a double
            # requeue or a requeue of an already-finished item would otherwise
            # corrupt _unfinished_tasks. If the item isn't in flight, log and
            # bail out without touching the deque or the counter -- it's
            # already been accounted for elsewhere, so this is a no-op rather
            # than a crash. (Releasing it from in flight here is correct in
            # every branch below: it's either requeued back onto the deque --
            # where a future get() will pick it up again -- or dropped for
            # good.)
            if not self._release_in_flight_locked(item, "requeue_front"):
                return

            if self._expired(item, monotonic()):
                self._on_drop_expired(item)
                self._finish_task_locked()
                return

            if self._maxsize > 0 and len(self._deque) >= self._maxsize:
                self._on_drop_queue_full(item)
                self._finish_task_locked()
                return

            self._deque.appendleft(item)
            self._not_empty.notify()

    def get(self):
        # type: () -> QueuedItemOrStop
        """Block for the next payload, silently dropping expired entries along the way."""
        while True:
            with self._not_empty:
                while not self._deque:
                    self._not_empty.wait()
                item = self._deque.popleft()
                # A slot just opened up: wake one thread blocked in put()'s
                # wait-for-room loop, if any (harmless no-op otherwise).
                self._not_full.notify()
                # Record this item as in flight, owned by the current thread,
                # until requeue_front() or task_done() releases it (see
                # _in_flight in __init__).
                self._take_in_flight_locked(item)

            if item is Stop:
                return item

            # Guard the monotonic() call on the type test rather than letting
            # _expired() do it: the argument is evaluated BEFORE the call, so
            # `self._expired(item, monotonic())` read the clock on every get()
            # including for bare strings, which are replay-safe and can never
            # expire, so the value was computed and immediately discarded.
            if isinstance(item, PendingPayload) and self._expired(item, monotonic()):
                self._on_drop_expired(item)
                self.task_done(item)
                continue

            return item

    def _take_in_flight_locked(self, item):
        # type: (QueuedItemOrStop) -> None
        # Caller already holds self._lock (shared by _not_empty / _all_tasks_done).
        # Records `item` as the one currently handed out by get(). A duplicate
        # here means a previous get() was never finished (or the same object
        # was queued twice); we log it and overwrite so the new handout is the
        # one tracked, rather than crashing the sender thread.
        key = id(item)
        if key in self._in_flight:
            log.error(
                "dogstatsd sender queue: get() handed out an item already tracked as "
                "in flight; a previous get() was never finished with task_done() / "
                "requeue_front(), or the same object was queued more than once. "
                "Counter bookkeeping may drift."
            )
        self._in_flight[key] = item

    def _release_in_flight_locked(self, item, action):
        # type: (QueuedItemOrStop, str) -> bool
        # Caller already holds self._lock (shared by _not_empty / _all_tasks_done).
        # Verifies `item` is currently in flight, then drops it from the
        # in-flight map. `action` names the caller ("requeue_front"/
        # "task_done") for the log message. Returns False (after logging) when
        # the item is not in flight, so the caller can skip the counter/deque
        # mutation that would otherwise drift _unfinished_tasks -- without
        # crashing the sender thread.
        key = id(item)
        if key not in self._in_flight:
            log.error(
                "dogstatsd sender queue: %s() was called on an item that is not "
                "currently in flight (it was never returned by get(), or was "
                "already finished). Ignoring it to keep the task counter consistent.",
                action,
            )
            return False
        del self._in_flight[key]
        return True

    def _finish_task_locked(self):
        # type: () -> None
        # Caller already holds self._lock (shared by _not_empty / _all_tasks_done).
        unfinished = self._unfinished_tasks - 1
        if unfinished < 0:
            # More finishes than puts: a real bookkeeping bug. Log it and
            # clamp at zero rather than raising, so the sender thread stays
            # alive. Notify in case a join() is waiting, so it doesn't hang.
            log.error(
                "dogstatsd sender queue: task accounting went negative "
                "(_unfinished_tasks below zero); clamping. This indicates a "
                "double finish or a finish without a matching put()."
            )
            unfinished = 0
        self._unfinished_tasks = unfinished
        if unfinished == 0:
            self._all_tasks_done.notify_all()

    def task_done(self, item):
        # type: (QueuedItemOrStop) -> None
        with self._all_tasks_done:
            # The item being finished must be the one get() currently has out
            # of the queue. This is the counterpart to get()'s
            # _take_in_flight_locked(); a second task_done() (double finish)
            # would otherwise let _unfinished_tasks drift. If it's not in
            # flight, log and bail out without decrementing -- the task was
            # already finished elsewhere -- rather than crashing the sender.
            if not self._release_in_flight_locked(item, "task_done"):
                return
            self._finish_task_locked()

    def join(self, timeout=None):
        # type: (Optional[float]) -> bool
        """Wait until every queued payload has been sent, dropped or expired.

        :param timeout: Maximum number of seconds to wait. None (the default)
            waits indefinitely.
        :return: True if nothing is outstanding any more, False if timeout
            elapsed while payloads were still in flight.
        """
        with self._all_tasks_done:
            if timeout is None:
                while self._unfinished_tasks:
                    self._all_tasks_done.wait()
                return True

            # Condition.wait()'s return value can't be used to detect a
            # timeout: on Python 2 it is always None. Track the deadline
            # ourselves instead, the same way put() does for put_timeout.
            deadline = monotonic() + timeout
            while self._unfinished_tasks:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return False
                self._all_tasks_done.wait(remaining)
            return True

    def qsize(self):
        # type: () -> int
        with self._lock:
            return len(self._deque)

    def empty(self):
        # type: () -> bool
        with self._lock:
            return not self._deque
