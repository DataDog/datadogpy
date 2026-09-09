import collections
import sys
import threading

try:
    # Python 3.3+
    from time import monotonic
except ImportError:
    # Python 2: no monotonic clock available, fall back to wall clock.
    from time import time as monotonic

if sys.version_info[:2] >= (3, 5):
    from typing import Callable, Optional, Union  # noqa: F401


# Sentinel telling the background sender thread to shut down. 
Stop = object()

# How long (in seconds) a non-replay-safe payload may sit in the background
# sender queue before it's considered stale and dropped instead of sent.
# Payloads that carry their own explicit timestamp (replay_safe) are exempt:
# delivering those late doesn't change what they mean, so they're kept
# around until they can actually be sent.
PENDING_PAYLOAD_EXPIRY_SECONDS = 10.0


class PendingPayload(object):
    """A single packet queued for the background sender.

    :ivar payload: The already-serialized packet text (including its
        trailing newline), ready to be written to the socket.
    :ivar enqueued_at: A monotonic timestamp recorded when the payload
        became eligible for sending (i.e. when it was put on the queue).
        Used to decide whether it has been sitting in the queue for too
        long to still be worth sending. None when replay_safe is True: it's
        never read in that case (see SenderQueue._expired()'s short-circuit),
        so skipping the allocation costs nothing.
    :ivar replay_safe: True when delayed delivery preserves the payload's
        meaning because it carries its own explicit timestamp. Such
        payloads are never dropped for being stale, and never need
        enqueued_at.
    """

    __slots__ = ("payload", "enqueued_at", "replay_safe")

    def __init__(self, payload, enqueued_at, replay_safe):
        # type: (str, Optional[float], bool) -> None
        self.payload = payload
        self.enqueued_at = enqueued_at
        self.replay_safe = replay_safe


class SenderQueue(object):
    """Bounded hand-off queue between application threads and the background sender thread.

    Unlike queue.Queue, put() never blocks and never rejects a payload. When
    the queue is already at its maximum size, the oldest entry is dropped to
    make room, along with any additional expired entries left at the front,
    so a backlog of stale payloads can't shut out fresh metrics indefinitely.

    get() drops expired entries lazily too, from the front, before returning
    the next payload actually worth handing to the sender.

    A payload that fails to send (e.g. because the connection is down) can be
    handed back with requeue_front() so it's retried first. That still
    respects both the expiry check and the size limit though: the queue
    must never grow past maxsize, and a payload that's gone stale while it
    was being (re)tried is dropped rather than requeued.
    """

    def __init__(self, maxsize, expiry_seconds, on_drop_queue_full, on_drop_expired):
        # type: (int, float, Callable[[PendingPayload], None], Callable[[PendingPayload], None]) -> None
        self._maxsize = maxsize
        self._expiry_seconds = expiry_seconds
        self._on_drop_queue_full = on_drop_queue_full
        self._on_drop_expired = on_drop_expired
        self._deque = collections.deque()  # type: collections.deque
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._all_tasks_done = threading.Condition(self._lock)

        # Keep track of the tasks that are being processed. A task pulled from the queue may
        # be returned if the connection fails, so we don't consider the queue empty until
        # all tasks have been dropped or sent.
        self._unfinished_tasks = 0

    def _expired(self, item, now):
        # type: (PendingPayload, float) -> bool
        if item.replay_safe:
            return False
        # enqueued_at is only ever None for replay_safe items (see
        # PendingPayload), which are already excluded above -- it's a plain
        # float here. mypy can't correlate that invariant across the two
        # attributes, hence the ignore.
        return (now - item.enqueued_at) > self._expiry_seconds  # type: ignore[operator]

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
        # The oldest entry is always dropped to make room. If it happens to
        # also be expired, attribute it to staleness rather than to the
        # queue being full, since that's the more useful signal.
        if self._expired(oldest, now):
            self._on_drop_expired(oldest)
        else:
            self._on_drop_queue_full(oldest)
        self._finish_task_locked()

        # Keep clearing out additional stale entries left at the front: they
        # would otherwise just sit there consuming a slot until they're
        # eventually popped.
        while self._deque and self._deque[0] is not Stop and self._expired(self._deque[0], now):
            self._on_drop_expired(self._deque.popleft())
            self._finish_task_locked()

    def put(self, item):
        # type: (Union[PendingPayload, object]) -> None
        """Queue a payload (or the Stop sentinel), evicting old entries if needed."""
        with self._not_empty:
            if item is not Stop and self._maxsize > 0 and len(self._deque) >= self._maxsize:
                self._make_room_locked()

            self._deque.append(item)
            self._unfinished_tasks += 1
            self._not_empty.notify()

    def requeue_front(self, item):
        # type: (PendingPayload) -> None
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
        # type: () -> Union[PendingPayload, object]
        """Block for the next payload, silently dropping expired entries along the way."""
        while True:
            with self._not_empty:
                while not self._deque:
                    self._not_empty.wait()
                item = self._deque.popleft()

            if item is Stop:
                return item

            if self._expired(item, monotonic()):
                self._on_drop_expired(item)
                self.task_done()
                continue

            return item

    def _finish_task_locked(self):
        # type: () -> None
        # Caller already holds self._lock (shared by _not_empty / _all_tasks_done).
        unfinished = self._unfinished_tasks - 1
        if unfinished < 0:
            raise ValueError("task_done() called too many times")
        self._unfinished_tasks = unfinished
        if unfinished == 0:
            self._all_tasks_done.notify_all()

    def task_done(self):
        # type: () -> None
        with self._all_tasks_done:
            self._finish_task_locked()

    def join(self):
        # type: () -> None
        with self._all_tasks_done:
            while self._unfinished_tasks:
                self._all_tasks_done.wait()

    def qsize(self):
        # type: () -> int
        with self._lock:
            return len(self._deque)

    def empty(self):
        # type: () -> bool
        with self._lock:
            return not self._deque

