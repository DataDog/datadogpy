# coding: utf8
# Unless explicitly stated otherwise all files in this repository are licensed
# under the BSD-3-Clause License. This product includes software developed at
# Datadog (https://www.datadoghq.com/).

# Copyright 2015-Present Datadog, Inc

# stdlib
import cProfile
import io
import logging
import os
import pstats
import random
import sys
import threading
import timeit
import unittest
import warnings

try:
    import queue
except ImportError:
    import Queue as queue

# datadog
from datadog.dogstatsd.base import DogStatsd
from datadog.util.compat import is_p3k

# test utils
from tests.util.fake_statsd_server import FakeServer
from tests.util.system_info_observer import SysInfoObserver


# StatsdSender is a static helper for sending mock metrics to statsd via a simple API
# pylint: disable=too-few-public-methods,useless-object-inheritance
class StatsdSender(object):
    EXTRA_TAGS = ["bar = barval", "baz = bazval"]
    STATIC_TIMING_SET = set(range(100))

    # Enums are not part of 2.7 built-ins
    METRICS_TYPE = [
        "decrement",
        "distribution",
        "gauge",
        "histogram",
        "increment",
        "set",
        "timing",
    ]

    @staticmethod
    def send(metric, statsd_instance, value):
        getattr(StatsdSender, "_submit_{}".format(StatsdSender.METRICS_TYPE[metric]))(
            statsd_instance, threading.current_thread().name, value
        )

    @staticmethod
    def _submit_decrement(statsd_instance, metric_prefix, _):
        statsd_instance.decrement(
            "{}.counter".format(metric_prefix), tags=StatsdSender.EXTRA_TAGS
        )

    @staticmethod
    def _submit_distribution(statsd_instance, metric_prefix, value):
        statsd_instance.distribution(
            "{}.distribution".format(metric_prefix), value, tags=StatsdSender.EXTRA_TAGS
        )

    @staticmethod
    def _submit_gauge(statsd_instance, metric_prefix, value):
        statsd_instance.gauge(
            "{}.gauge".format(metric_prefix), value, tags=StatsdSender.EXTRA_TAGS
        )

    @staticmethod
    def _submit_histogram(statsd_instance, metric_prefix, value):
        statsd_instance.histogram(
            "{}.histogram".format(metric_prefix), value, tags=StatsdSender.EXTRA_TAGS
        )

    @staticmethod
    def _submit_increment(statsd_instance, metric_prefix, _):
        statsd_instance.increment(
            "{}.counter".format(metric_prefix), tags=StatsdSender.EXTRA_TAGS
        )

    @staticmethod
    def _submit_set(statsd_instance, metric_prefix, value):
        statsd_instance.set(
            "{}.set".format(metric_prefix), value, tags=StatsdSender.EXTRA_TAGS
        )

    @staticmethod
    def _submit_timing(statsd_instance, metric_prefix, _):
        statsd_instance.timing(
            "{}.set".format(metric_prefix),
            StatsdSender.STATIC_TIMING_SET,
            tags=StatsdSender.EXTRA_TAGS,
        )


class TestDogStatsdThroughput(unittest.TestCase):
    """
    DogStatsd throughput tests.
    """

    DEFAULT_NUM_DATAPOINTS = 50000
    DEFAULT_NUM_THREADS = 1
    DEFAULT_NUM_RUNS = 5
    DEFAULT_TRANSPORT = "udp"

    RUN_MESSAGE = (
        "Run #{:2d}/{:2d}: {:.4f}s (latency: {:.2f}μs, cpu: {:.4f},"
        + " mem.rss_diff: {:.0f}kb, recv: {:.2f}%)"
    )

    def setUp(self):
        # Parse the benchmark parameters and use sensible defaults for values
        # that are not configured
        self.num_datapoints = int(
            os.getenv("BENCHMARK_NUM_DATAPOINTS", str(self.DEFAULT_NUM_DATAPOINTS))
        )
        self.num_threads = int(
            os.getenv("BENCHMARK_NUM_THREADS", str(self.DEFAULT_NUM_THREADS))
        )
        self.num_runs = int(os.getenv("BENCHMARK_NUM_RUNS", str(self.DEFAULT_NUM_RUNS)))
        self.profiling_enabled = os.getenv("BENCHMARK_PROFILING", "false") in ["1", "true", "True", "Y", "yes", "Yes"]
        self.transport = os.getenv(
            "BENCHMARK_TRANSPORT", str(self.DEFAULT_TRANSPORT)
        ).upper()

        # We do want to see any problems if they occur in the statsd library
        logger = logging.getLogger()
        logger.level = logging.DEBUG
        logger.addHandler(logging.StreamHandler(sys.stdout))

        # Ensure that warnings don't print the stack trace
        def one_line_warning(message, category, filename, lineno, *_):
            return "%s:%s: %s: %s" % (filename, lineno, category.__name__, message)

        warnings.formatwarning = one_line_warning

        # Add a newline so that we don't get clobbered by the test output
        print("")

    # pylint: disable=too-many-locals
    def test_statsd_performance(self):
        print(
            "Starting: {} run(s), {} thread(s), {} points/thread via {} (profiling: {}) on Python{}.{} ...".format(
                self.num_runs,
                self.num_threads,
                self.num_datapoints,
                self.transport,
                str(self.profiling_enabled).lower(),
                sys.version_info[0],
                sys.version_info[1],
            )
        )

        # We want a stable random sequence so that parallel runs
        # are consistent and repeatable
        random.seed(1234)

        # Pre-calculate a random order of metric types for each thread
        metrics_order = []
        for _ in range(self.num_threads):
            thread_metrics_order = []
            for _ in range(self.num_datapoints):
                thread_metrics_order.append(
                    random.randrange(len(StatsdSender.METRICS_TYPE))
                )

            metrics_order.append(thread_metrics_order)

        run_cpu_stats = []
        run_durations = []
        run_latencies = []
        run_memory_stats = []
        received_packet_pcts = []

        for run_idx in range(self.num_runs):
            (
                duration,
                total_latency,
                sys_stats,
                received_packet_pct,
            ) = self._execute_test_run(
                FakeServer(transport=self.transport),
                metrics_order,
                self.num_threads,
                self.num_datapoints,
            )
            avg_latency_secs = total_latency / (self.num_threads * self.num_datapoints)
            avg_latency = avg_latency_secs * 1000000
            print(
                self.RUN_MESSAGE.format(
                    run_idx + 1,
                    self.num_runs,
                    duration,
                    avg_latency,
                    sys_stats["cpu.user"] + sys_stats["cpu.system"],
                    sys_stats["mem.rss_diff_kb"],
                    received_packet_pct,
                )
            )

            run_durations.append(duration)
            run_cpu_stats.append(sys_stats["cpu.user"] + sys_stats["cpu.system"])
            run_memory_stats.append(sys_stats["mem.rss_diff_kb"])
            run_latencies.append(float(avg_latency))
            received_packet_pcts.append(received_packet_pct)

        result_msg = "\nTotal for {} run(s), {} thread(s), {} points/thread via {} on Python{}.{}:\n"
        result_msg += "\tDuration:\t\t{:.4f}s\n"
        result_msg += "\tLatency:\t\t{:.2f}μs\n"
        result_msg += "\tCPU:\t\t\t{:.4f}\n"
        result_msg += "\tMemory (rss) diff:\t{:.0f}kb\n"
        result_msg += "\tReceived packets:\t{:.2f}%"
        print(
            result_msg.format(
                self.num_runs,
                self.num_threads,
                self.num_datapoints,
                self.transport,
                sys.version_info[0],
                sys.version_info[1],
                sum(run_durations) / len(run_durations),
                sum(run_latencies) / len(run_latencies),
                sum(run_cpu_stats) / len(run_cpu_stats),
                sum(run_memory_stats) / len(run_memory_stats),
                sum(received_packet_pcts) / len(received_packet_pcts),
            )
        )

    # pylint: disable=too-many-locals,no-self-use
    def _execute_test_run(self, server, metrics_order, num_threads, num_datapoints):
        # Setup all the threads and get them in a waiting state
        threads = []
        start_signal = threading.Event()

        latency_results = queue.Queue()
        observer = SysInfoObserver()

        with server:
            # Create a DogStatsd client with a mocked socket
            statsd_instance = DogStatsd(
                constant_tags=["foo = {}".format(random.random())],
                host="localhost",
                port=server.port,
                socket_path=server.socket_path,
            )

            for thread_idx in range(num_threads):
                thread = threading.Thread(
                    name="test_statsd_throughput_thread_{}".format(thread_idx),
                    target=TestDogStatsdThroughput._thread_runner,
                    args=(
                        statsd_instance,
                        start_signal,
                        metrics_order[thread_idx],
                        latency_results,
                        self.profiling_enabled,
                    ),
                )
                thread.daemon = True
                threads.append(thread)
                thread.start()

            # `timeit.timeit` is not easily usable here since we need to pass in state
            # and Python 2 version of `timeit()` does not accept the `global` keyword.
            start_time = timeit.default_timer()

            # Let the thread know that it can start sending metrics
            start_signal.set()

            # Observe system utilization while we wait for the threads to exit
            with observer:
                for thread in threads:
                    thread.join()

            total_latency = 0.0
            for thread in threads:
                if latency_results.empty():
                    warnings.warn("One or more threads did not report their results!")
                    continue

                total_latency += latency_results.get()

            duration = timeit.default_timer() - start_time

        # Sanity checks: Verify that metric transfer expectations are correct
        expected_metrics = num_threads * num_datapoints

        # Verify that dropped metric count is matching our statsd expectations. This
        # type of inconsistency should never happen.
        if (
            expected_metrics - server.metrics_captured
            != statsd_instance.packets_dropped
        ):
            error_msg = (
                "WARN: Statsd dropped packet count ({}) did not match the server "
            )
            error_msg += "missing received packet count expectation ({})!\n"
            warnings.warn(
                error_msg.format(
                    statsd_instance.packets_dropped,
                    expected_metrics - server.metrics_captured,
                )
            )

        # Verify that received metric count is matching our metric totals expectations. Note
        # that in some scenarios, some data is expected to be dropped.
        if server.metrics_captured != expected_metrics:
            error_msg = "WARN: Received metrics count ({}) did not match the sent "
            error_msg += "metrics count ({})!\n"
            warnings.warn(error_msg.format(server.metrics_captured, expected_metrics))

        received_packet_pct = server.metrics_captured * 100.0 / expected_metrics

        return (duration, total_latency, observer.stats, received_packet_pct)

    @staticmethod
    def _thread_runner(
        statsd_instance,
        start_event,
        thread_metrics_order,
        latency_results,
        profiling_enabled,
    ):
        # We wait for a global signal to start running our events
        start_event.wait(5)

        if profiling_enabled:
            profiler = cProfile.Profile()
            profiler.enable()

        duration = 0.0
        for metric_idx, metric in enumerate(thread_metrics_order):
            start_time = timeit.default_timer()

            StatsdSender.send(metric, statsd_instance, metric_idx)

            duration += timeit.default_timer() - start_time

        if hasattr(statsd_instance, 'flush'):
            statsd_instance.flush()

        latency_results.put(duration)

        if profiling_enabled:
            TestDogStatsdThroughput.print_profiling_stats(profiler)


    @staticmethod
    def print_profiling_stats(profiler, sort_by='cumulative'):
        """
        Prints profiling results for the thread that finishes its run. Options for
        sorting include 'tottime', 'pcalls', 'ncalls', 'cumulative', etc but you can
        check https://github.com/python/cpython/blob/3.9/Lib/pstats.py#L37-L45 for
        other options.
        """

        profiler.disable()

        if is_p3k():
            output_stream = io.StringIO()
        else:
            output_stream = io.BytesIO()

        profiling_stats = pstats.Stats(
                profiler,
                stream=output_stream,
        ).sort_stats(sort_by)

        profiling_stats.print_stats()
        print(output_stream.getvalue())
