# Unless explicitly stated otherwise all files in this repository are licensed
# under the BSD-3-Clause License. This product includes software developed at
# Datadog (https://www.datadoghq.com/).

# Copyright 2021-Present Datadog, Inc

from threading import Event, Thread
import os
import time

# pylint: disable=import-error
import psutil


# pylint: disable=useless-object-inheritance
class SysInfoObserver(object):
    """
    SysInfoObserver collects timed CPU and memory usage stats in a separate
    thread about the current process.
    """

    def __init__(self, interval=0.1):
        self._stats = []

        self.interval = interval

        self.exit = None
        self.initial_cpu_user = None
        self.initial_cpu_system = None
        self.observer_thread = None
        self.proc_info = None

    def __enter__(self):
        if self.observer_thread:
            raise RuntimeError("Observer already running")

        self.exit = Event()

        pid = os.getpid()
        self.proc_info = psutil.Process(pid)

        # Record baselines
        self.initial_cpu_user = self.proc_info.cpu_times().user
        self.initial_cpu_system = self.proc_info.cpu_times().system
        self.initial_mem_rss = self.proc_info.memory_full_info().rss
        self.initial_mem_vms = self.proc_info.memory_full_info().vms

        self.observer_thread = Thread(
            name=self.__class__.__name__,
            target=self.poll_system_info,
            args=(
                self.proc_info,
                self.interval,
            ),
        )
        self.observer_thread.daemon = True
        self.observer_thread.start()

        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.exit.set()
        self.observer_thread.join()

    def poll_system_info(self, proc_info, interval):
        while not self.exit.is_set():
            time.sleep(interval)

            mem_info = proc_info.memory_full_info()
            datapoint = {
                "interval": interval,
                "mem.rss_diff_kb": (mem_info.rss - self.initial_mem_rss) / 1024,
                "mem.vms_diff_kb": (mem_info.vms- self.initial_mem_vms)  / 1024,
            }

            self._stats.append(datapoint)

    @property
    def stats(self):
        # CPU data is cumulative
        agg_stats = {
            "cpu.user": self.proc_info.cpu_times().user - self.initial_cpu_user,
            "cpu.system": self.proc_info.cpu_times().system - self.initial_cpu_system,
        }

        if not self.exit.is_set():
            raise RuntimeError(
                "You can only collect aggregated stats after context manager exits"
            )

        datapoints = len(self._stats)
        for datapoint in self._stats:
            for key, val in datapoint.items():
                if key.startswith("cpu"):
                    continue

                if key not in agg_stats:
                    agg_stats[key] = 0.0

                agg_stats[key] += val

        for key, val in agg_stats.items():
            if not key.startswith("cpu"):
                agg_stats[key] = val / datapoints

        return agg_stats
