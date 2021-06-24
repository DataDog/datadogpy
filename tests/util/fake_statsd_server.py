# Unless explicitly stated otherwise all files in this repository are licensed
# under the BSD-3-Clause License. This product includes software developed at
# Datadog (https://www.datadoghq.com/).

# Copyright 2021-Present Datadog, Inc

import ctypes
import os
import shutil
import socket
import tempfile
import threading
import time
import warnings
from multiprocessing import Array, Event, Process, Value

from datadog.util.compat import is_p3k

# pylint: disable=too-many-instance-attributes,useless-object-inheritance
class FakeServer(object):
    """
    Fake statsd server that can be used for testing/benchmarking. Implementation
    Uses a separate process to run and manage the context to not poison the
    benchmarking results.
    """

    SOCKET_NAME = "fake_statsd_server_socket"
    ALLOWED_TRANSPORTS = ["UDS", "UDP"]
    MIN_RECV_BUFFER_SIZE = 32 * 1024

    def __init__(self, transport="UDS", debug=False):
        if transport not in self.ALLOWED_TRANSPORTS:
            raise ValueError(
                "Transport {} is not a valid transport type. Only {} are allowed!".format(
                    transport,
                    self.ALLOWED_TRANSPORTS,
                )
            )

        self.transport = transport
        self.debug = debug

        self.server_process = None
        self.socket_dir = None

        # Inter-process coordination events
        self.exit = Event()
        self.ready = Event()

        # Shared-mem property value holders for inter-process communication
        self._socket_path = Array(ctypes.c_char, 1024, lock=True)
        self._port = Value(ctypes.c_long, 0, lock=True)
        self._metric_counter_shmem_var = Value(ctypes.c_long, 0, lock=True)
        self._payload_counter_shmem_var = Value(ctypes.c_long, 0, lock=True)

    def _run_server(self):
        payload_counter = 0
        metric_counter = 0

        if self.transport == "UDS":
            self.socket_dir = tempfile.mkdtemp(prefix=self.__class__.__name__)
            socket_path = os.path.join(self.socket_dir, self.SOCKET_NAME)

            if os.path.exists(socket_path):
                os.unlink(socket_path)

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.settimeout(3)

            # Increase the receiving buffer size where needed (e.g. MacOS has 4k RX
            # buffers which is half of the max packet size that the client will send.
            if os.name != 'nt':
                recv_buff_size = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                if recv_buff_size <= self.MIN_RECV_BUFFER_SIZE:
                    sock.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_RCVBUF,
                        self.MIN_RECV_BUFFER_SIZE,
                    )

                    recv_buff_size = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
            sock.bind(socket_path)

            # We are using ctypes for shmem so we have to use a consistent
            # datatype across Python versions
            if is_p3k():
                self._socket_path.value = socket_path.encode("utf-8")
            else:
                self._socket_path.value = socket_path

        elif self.transport == "UDP":
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(3)
            sock.bind(("", 0))

            _, self._port.value = sock.getsockname()

        # Run an async thread to update our shared-mem counters. We don't want to update
        # the shared memory values when we get data due to performance reasons.
        def _update_counters():
            while not self.exit.is_set():
                self._payload_counter_shmem_var.value = payload_counter
                self._metric_counter_shmem_var.value = metric_counter
                time.sleep(0.2)

        counter_update_timer = threading.Thread(target=_update_counters)
        counter_update_timer.daemon = True
        counter_update_timer.start()

        try:
            self.ready.set()

            while not self.exit.is_set():
                payload, _ = sock.recvfrom(8192)

                payload_counter += 1
                metric_counter += len(payload.split(b"\n"))

                if self.debug:
                    print(
                        "Got '{}' (pkts: {}, payloads: {}, metrics: {}".format(
                            payload,
                            len(payload.split(b"\n")),
                            payload_counter,
                            metric_counter,
                        )
                    )

        except socket.timeout as ste:
            if not self.exit.is_set():
                raise ste
        finally:
            counter_update_timer.join()
            sock.close()

    def __enter__(self):
        if self.server_process:
            raise RuntimeError("Server already running")

        self.server_process = Process(
            target=self._run_server,
            name=FakeServer.__class__.__name__,
            args=(),
        )
        self.server_process.daemon = True
        self.server_process.start()

        self.ready.wait(5)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        # Allow grace time to capture all metrics
        time.sleep(2)

        self.exit.set()
        self.server_process.join(10)

        if self.socket_dir:
            shutil.rmtree(self.socket_dir, ignore_errors=True)

        if self.server_process.exitcode != 0:
            raise RuntimeError("Server process did not exit successfully!")

    @property
    def port(self):
        return self._port.value

    @property
    def socket_path(self):
        return self._socket_path.value or None

    @property
    def payloads_captured(self):
        return self._payload_counter_shmem_var.value

    @property
    def metrics_captured(self):
        return self._metric_counter_shmem_var.value

    def __repr__(self):
        return "<FakeThreadedUDPServer(Packets RX: {}, Metrics RX: {}".format(
            self._payload_counter_shmem_var.value, self._metric_counter_shmem_var.value
        )
