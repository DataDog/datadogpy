"""
Emulates: server crashes -> write fails -> client reconnects -> reconnect
succeeds -> the very next write fails again.

This is a controlled, deterministic emulation (not a probabilistic race): we
puppet the "agent" side explicitly so every step happens in the exact order
described, every time you run this script.

Two parts:

  1. `raw_socket_narrative()` - plain UDS SOCK_DGRAM sockets, no datadogpy
     involved, just to show the sequence of syscalls/return values in
     isolation.

  2. `through_dogstatsd_client()` - drives the actual
     `datadog.dogstatsd.base.DogStatsd` client through the same induced
     sequence (by monkeypatching `_get_uds_socket` to kill the "agent" at the
     right moments) so you can see how the real retry/backoff code reacts:
     does it recover, retry again, or drop the packet.

Run:
    python3 tests/manual/emulate_reconnect_then_write_fails.py
"""
import errno
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

SOCK_PATH = "/tmp/emulate_reconnect_then_write_fails.sock"


def errname(exc):
    return errno.errorcode.get(getattr(exc, "errno", None), str(exc))


def _fresh_path():
    try:
        os.unlink(SOCK_PATH)
    except OSError:
        pass


def _bind_server():
    """Start a UDS SOCK_DGRAM 'agent' bound at SOCK_PATH."""
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    srv.bind(SOCK_PATH)
    return srv


def raw_socket_narrative():
    print("=" * 70)
    print("PART 1: raw UDS sockets, step by step")
    print("=" * 70)

    _fresh_path()

    # --- Step 0: agent v1 is up, client is connected and happily sending ---
    print("\n[step 0] agent v1 starts, client connects")
    agent1 = _bind_server()
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    client.connect(SOCK_PATH)
    client.send(b"metric.a:1|c")
    print("  client wrote successfully:", agent1.recv(1024))

    # --- Step 1: agent crashes ---
    print("\n[step 1] agent v1 CRASHES (socket closed, file left on disk)")
    agent1.close()

    # --- Step 2: client's next write fails ---
    print("[step 2] client writes on the now-dead connection ...")
    try:
        client.send(b"metric.b:1|c")
        print("  unexpectedly succeeded")
    except OSError as e:
        print(f"  write FAILED as expected: {errname(e)} ({e})")

    # --- Step 3: supervisor restarts the agent (agent v2) very quickly ---
    print("\n[step 3] supervisor restarts the agent (agent v2 binds at the same path)")
    _fresh_path()
    agent2 = _bind_server()

    # --- Step 4: client reconnects ---
    print("[step 4] client closes its old socket and reconnects")
    client.close()
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.connect(SOCK_PATH)
        print("  reconnect SUCCEEDED (agent v2 is genuinely up right now)")
    except OSError as e:
        print(f"  reconnect failed: {errname(e)} ({e}) -- unexpected for this narrative")
        return

    # --- Step 5: agent v2 crashes immediately (flaky restart) ---
    print("\n[step 5] agent v2 CRASHES immediately, before the client's next write")
    agent2.close()

    # --- Step 6: the very next write after the successful reconnect fails too ---
    print("[step 6] client writes again, right after the successful reconnect ...")
    try:
        client.send(b"metric.c:1|c")
        print("  unexpectedly succeeded")
    except OSError as e:
        print(f"  write FAILED again: {errname(e)} ({e})")
        print("\n  >>> proven: a successful reconnect does not guarantee the next write survives <<<")

    client.close()
    _fresh_path()


def through_dogstatsd_client():
    print("\n" + "=" * 70)
    print("PART 2: the same sequence, driven through the real DogStatsd client")
    print("=" * 70)
    print("_get_uds_socket now makes exactly one connect attempt -- no internal")
    print("retry loop. Reconnect-and-retry is the background sender's job now, gated")
    print("by socket_connect_retry, and it lives in _sender_main_loop: call")
    print("_xmit_packet(..., queue_mode=True), and if it reports a retryable failure")
    print("(None), back off and call it again. That's what this drives directly, to")
    print("keep watching the same connect/send failures _xmit_packet_attempt sees.")

    from datadog.dogstatsd.base import (
        DogStatsd,
        UDS_CONNECT_RETRY_INITIAL_BACKOFF,
        UDS_CONNECT_RETRY_MAX_BACKOFF,
    )

    _fresh_path()
    agent = {"sock": _bind_server(), "generation": 0}

    statsd = DogStatsd(socket_path=SOCK_PATH, socket_connect_timeout=2.0)

    real_get_uds_socket = DogStatsd._get_uds_socket.__func__
    call_log = []
    state = {"restart_soon_scheduled": False, "post_reconnect_crash_done": False}

    def scripted_get_uds_socket(cls, socket_path, timeout):
        """
        Wraps the real (now single-attempt) connect, but scripts the agent's
        state around it so the narrative is deterministic regardless of
        exactly which attempt number the retry loop below is on when each
        event happens:
          first call ever: agent is already dead (crashed) before this
                    connect -- this attempt fails; the retry loop below
                    (standing in for _sender_main_loop) is what waits for
                    agent v2 and calls again
          first call that actually succeeds: connect succeeds against agent
                    v2, which we then kill immediately afterwards so the
                    following send fails again
        """
        call_log.append(1)
        n = len(call_log)

        if not state["restart_soon_scheduled"]:
            state["restart_soon_scheduled"] = True
            print("\n[client] first connect attempt -- agent is currently down")
            agent["sock"].close()
            _fresh_path()

            # Simulate the supervisor's restart happening a little while into
            # the retry loop below, so its backoff-and-retry is what catches
            # the agent coming back -- not necessarily the very next attempt.
            def restart_soon():
                time.sleep(0.15)
                _fresh_path()
                agent["sock"] = _bind_server()
                agent["generation"] = 1
            import threading
            threading.Thread(target=restart_soon, daemon=True).start()

        try:
            sock = real_get_uds_socket(cls, socket_path, timeout)
        except Exception as e:
            print(f"[client] connect attempt #{n} failed: {errname(e)} (agent still down)")
            raise

        print(f"[client] connect attempt #{n} SUCCEEDED (agent v2 is up)")
        if not state["post_reconnect_crash_done"]:
            state["post_reconnect_crash_done"] = True
            print("[client] ...but agent v2 crashes again immediately, before the send:")
            agent["sock"].close()
            _fresh_path()

            # Agent v3 comes back shortly after -- this is what lets a *later*
            # retry attempt (triggered by the send failure right after this
            # connect) actually succeed, so we can see the client ride out
            # both failures end to end.
            def restart_again():
                time.sleep(0.15)
                _fresh_path()
                agent["sock"] = _bind_server()
                agent["generation"] = 2
            import threading
            threading.Thread(target=restart_again, daemon=True).start()

        return sock

    DogStatsd._get_uds_socket = classmethod(scripted_get_uds_socket)
    try:
        t0 = time.time()
        backoff = UDS_CONNECT_RETRY_INITIAL_BACKOFF
        attempt = 0
        sent = None  # None means "retryable failure, try again" -- see _xmit_packet.
        while sent is None:
            attempt += 1
            sent = statsd._xmit_packet("emulated.metric:1|c", False, queue_mode=True)
            if sent is None:
                time.sleep(backoff)
                backoff = min(backoff * 2, UDS_CONNECT_RETRY_MAX_BACKOFF)
        elapsed = time.time() - t0
    finally:
        DogStatsd._get_uds_socket = classmethod(real_get_uds_socket)
        try:
            agent["sock"].close()
        except OSError:
            pass
        _fresh_path()

    print(f"\n[result] _xmit_packet(..., queue_mode=True) -> sent={sent}, elapsed={elapsed:.3f}s, "
          f"retry-loop attempts={attempt}, get_uds_socket calls={len(call_log)}")
    print(f"[result] packets_dropped_writer={statsd.packets_dropped_writer}")
    if sent:
        print("  -> the retry loop (standing in for the background sender) absorbed BOTH")
        print("     failures (the initial dead-agent connect AND the post-reconnect send")
        print("     failure) and eventually delivered the packet once the agent stayed up.")
    else:
        print("  -> the packet was dropped.")


if __name__ == "__main__":
    raw_socket_narrative()
    through_dogstatsd_client()
