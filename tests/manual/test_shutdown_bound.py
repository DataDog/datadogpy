"""Manual check that shutdown stays bounded while the sender is retrying.

Usage: python tests/manual/test_shutdown_bound.py [n_packets] [stop_timeout]

Fills the background sender queue while the agent is unreachable, with
socket_connect_timeout=2.0 so the sender keeps retrying the head-of-queue
payload indefinitely, backing off up to UDS_CONNECT_RETRY_MAX_BACKOFF (a minute)
between attempts.

Two things used to make stop() drag or hang here, both fixed:

  * The backoff was a plain time.sleep(), so stop() had to wait out whatever
    was left of it -- up to a minute.
  * requeue_front() puts the failed payload back at the *front* of the queue,
    ahead of the Stop sentinel, so the sender only ever noticed Stop once the
    head payload was finally resolved. Ordinary payloads resolve via the
    queue's expiry, but replay-safe ones (gauge_with_timestamp, events with
    date_happened, service checks with a timestamp) are exempt from expiry --
    so one of those at the head starved Stop forever and stop() never
    returned at all.

Both are now handled by a stopping Event that the sender waits on instead of
sleeping, so expect stop() to return promptly and report True regardless of
what is queued. Pass a replay-safe metric through (see REPLAY_SAFE below) to
exercise the case that used to hang.
"""
import os
import sys
import tempfile
import time

from datadog.dogstatsd.base import DogStatsd

n_packets = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
stop_timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
REPLAY_SAFE = os.environ.get("REPLAY_SAFE") == "1"

socket_path = os.path.join(tempfile.mkdtemp(), "dsd.socket")  # never created

client = DogStatsd(
    socket_path="unix://" + socket_path,
    socket_connect_timeout=2.0,
    disable_background_sender=False,
    disable_buffering=True,
    disable_aggregation=True,
    sender_queue_size=n_packets,
)

if REPLAY_SAFE:
    # Exempt from queue expiry -- this is the shape that used to hang stop().
    for i in range(n_packets):
        client.gauge_with_timestamp("metric.{}".format(i), 1, timestamp=int(time.time()))
else:
    for i in range(n_packets):
        client._send_to_server("metric.{}:1|c".format(i))

print("queued={} replay_safe={} socket_connect_timeout=2.0".format(n_packets, REPLAY_SAFE))
print("sender is retrying the head of the queue; stop() must interrupt that rather than wait it out")

started = time.time()
result = client.stop()
elapsed = time.time() - started

print("stop({!r}) returned {!r} after {:.2f}s".format(stop_timeout, result, elapsed))
print("packets_dropped_writer={} bytes_dropped_writer={}".format(
    client.packets_dropped_writer, client.bytes_dropped_writer))
if result and elapsed < 1.0:
    print("  -> shutdown was interrupted promptly, as intended")
else:
    print("  -> UNEXPECTED: shutdown was not prompt")
