import re
import time
# import unittest
import threading
from nose import tools as t

from datadog import lambda_stats, datadog_lambda_wrapper


class MemoryReporter(object):
    """ A reporting class that reports to memory for testing. """

    def __init__(self):
        self.metrics = []
        self.events = []

    def flush_metrics(self, metrics):
        self.metrics += metrics

    def flush_events(self, events):
        self.events += events


@datadog_lambda_wrapper
def wrapped_function(id):

    t.assert_greater(datadog_lambda_wrapper._counter, 1)
    # Increment
    lambda_stats.increment("counter", timestamp=12345)
    time.sleep(0.001)  # sleep makes the os continue another thread

    # Gauge
    lambda_stats.gauge("gauge_" + str(id), 42)
    time.sleep(0.001)  # sleep makes the os continue another thread

    # Histogram
    lambda_stats.histogram("histogram", id, timestamp=12345)
    time.sleep(0.001)  # sleep makes the os continue another thread

    # Event
    lambda_stats.event("title", "content")


class TestWrapperThreadSafety(object):

    def test_wrapper_thread_safety(self):
        lambda_stats.reporter = MemoryReporter()
        datadog_lambda_wrapper._counter = 1

        for i in range(10000):
            threading.Thread(target=wrapped_function, args=[i]).start()
        # Wait all threads to finish
        time.sleep(10)

        # Flush and check
        t.assert_equal(datadog_lambda_wrapper._counter, 1)
        lambda_stats.flush(float("inf"))

        metrics = lambda_stats.reporter.metrics
        events = lambda_stats.reporter.events

        # Overview
        t.assert_equal(len(metrics), 10009, len(metrics))

        # Sort metrics
        counter_metrics = []
        gauge_metrics = []
        histogram_metrics = []

        for m in metrics:
            if re.match("gauge_.*", m['metric']):
                gauge_metrics.append(m)
            elif re.match("histogram.*", m['metric']):
                histogram_metrics.append(m)
            else:
                counter_metrics.append(m)

        # Counter
        t.assert_equal(len(counter_metrics), 1, len(counter_metrics))
        counter = counter_metrics[0]
        t.assert_equal(counter['points'][0][1], 10000, counter['points'][0][1])

        # Gauge
        t.assert_equal(len(gauge_metrics), 10000, len(gauge_metrics))

        # Histogram
        t.assert_equal(len(histogram_metrics), 8, len(histogram_metrics))
        count_histogram = filter(lambda x: x['metric'] == "histogram.count", histogram_metrics)[0]
        t.assert_equal(count_histogram['points'][0][1], 10000, count_histogram['points'][0][1])
        sum_histogram = filter(lambda x: x['metric'] == "histogram.avg", histogram_metrics)[0]
        t.assert_equal(sum_histogram['points'][0][1], 4999.5, sum_histogram['points'][0][1])

        # Events
        t.assert_equal(10000, len(events), len(events))
