#!/usr/bin/env python3

import logging
import multiprocessing
import os
import random
import sys
import threading
import time
import unittest
import warnings
from multiprocessing import Event

from datadog.dogstatsd.base import DogStatsd

from tests.util.fake_statsd_server import FakeServer

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


class TestDogStatsdMultiprocessing(unittest.TestCase):
    """
    DogStatsd multiprocessing tests
    """

    DEFAULT_NUM_DATAPOINTS = 50000
    DEFAULT_NUM_RUNS = 5
    DEFAULT_NUM_PROCESSES = 5
    DEFAULT_TRANSPORT = "udp"

    def setUp(self):
        self.transport = os.getenv(
            "BENCHMARK_TRANSPORT", str(self.DEFAULT_TRANSPORT)
        ).upper()

        self.num_processes = int(
            os.getenv("BENCHMARK_NUM_PROCESSES", str(self.DEFAULT_NUM_PROCESSES))
        )

        self.num_datapoints = int(
            os.getenv("BENCHMARK_NUM_DATAPOINTS", str(self.DEFAULT_NUM_DATAPOINTS))
        )

        self.server = FakeServer(transport=self.transport, debug=False)

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

        self.start_event = Event()

        random.seed(1234)

    @staticmethod
    def _send_some_metrics(server, statsd_instance, num_datapoints, start_event):
        def _print_message(message):
            print(
                "Process '{} (pid: {})': {}".format(
                    multiprocessing.current_process().name,
                    multiprocessing.current_process().pid,
                    message,
                )
            )

        start_event.wait()

        for idx in range(num_datapoints):
            metric_idx = idx % len(StatsdSender.METRICS_TYPE)
            StatsdSender.send(metric_idx, statsd_instance, idx)

    def test_multiprocessing(self):
        if sys.version_info >= (3, 0):
            print("Available start methods: {}".format(multiprocessing.get_all_start_methods()))
            print("Current start method: {}".format(multiprocessing.get_start_method()))

            # On at least 1 platform (Darwin), we have to force our context to use a fork
            # See here for more info: https://bugs.python.org/issue33725
            # XXX: "fork" cannot be used on Windows
            multiprocessing.set_start_method("fork", force=True)

            print("New start method: {}".format(multiprocessing.get_start_method()))

        with self.server:
            statsd_instance = DogStatsd(
                constant_tags=["foo = {}".format(random.random())],
                host="localhost",
                port=self.server.port,
                socket_path=self.server.socket_path,
            )

            process_runners = []
            for idx in range(self.num_processes):
                process_runner = multiprocessing.Process(
                    name='statsd_test_process_runner_{}'.format(idx),
                    target=self._send_some_metrics,
                    args=(self.server, statsd_instance, self.num_datapoints, self.start_event),
                )
                process_runners.append(process_runner)

            for process_runner in process_runners:
                process_runner.start()

            self.start_event.set()

            for process_runner in process_runners:
                process_runner.join()

        time.sleep(0.5)

        print(self.server.metrics_captured)
