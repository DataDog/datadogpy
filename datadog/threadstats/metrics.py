# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Metric roll-up classes.
"""
from collections import defaultdict
import random
import itertools
import threading

from datadog.util.compat import iternext
from datadog.threadstats.constants import MetricType


class Metric(object):
    """
    A base metric class that accepts points, slices them into time intervals
    and performs roll-ups within those intervals.
    """

    def add_point(self, value):
        """ Add a point to the given metric. """
        raise NotImplementedError()

    def flush(self, timestamp, interval):
        """ Flush all metrics up to the given timestamp. """
        raise NotImplementedError()


class Set(Metric):
    """ A set metric. """

    stats_tag = "g"

    def __init__(self, name, tags, host):
        self.name = name
        self.tags = tags
        self.host = host
        self.set = set()

    def add_point(self, value):
        self.set.add(value)

    def flush(self, timestamp, interval):
        return [(timestamp, len(self.set), self.name, self.tags, self.host, MetricType.Gauge, interval)]


class Gauge(Metric):
    """ A gauge metric. """

    stats_tag = "g"

    def __init__(self, name, tags, host):
        self.name = name
        self.tags = tags
        self.host = host
        self.value = None

    def add_point(self, value):
        self.value = value

    def flush(self, timestamp, interval):
        return [(timestamp, self.value, self.name, self.tags, self.host, MetricType.Gauge, interval)]


class Counter(Metric):
    """ A metric that tracks a counter value. """

    stats_tag = "c"

    def __init__(self, name, tags, host):
        self.name = name
        self.tags = tags
        self.host = host
        self.count = []

    def add_point(self, value):
        self.count.append(value)

    def flush(self, timestamp, interval):
        count = sum(self.count, 0)
        return [(timestamp, count / float(interval), self.name, self.tags, self.host, MetricType.Rate, interval)]


class Distribution(Metric):
    """ A distribution metric. """

    stats_tag = "d"

    def __init__(self, name, tags, host):
        self.name = name
        self.tags = tags
        self.host = host
        self.value = []

    def add_point(self, value):
        self.value.append(value)

    def flush(self, timestamp, interval):
        return [(timestamp, self.value, self.name, self.tags, self.host, MetricType.Distribution, interval)]


class Histogram(Metric):
    """ A histogram metric. """

    stats_tag = "h"

    def __init__(self, name, tags, host):
        self.name = name
        self.tags = tags
        self.host = host
        self.max = float("-inf")
        self.min = float("inf")
        self.sum = []
        self.iter_counter = itertools.count()
        self.count = iternext(self.iter_counter)
        self.sample_size = 1000
        self.samples = []
        self.percentiles = [0.75, 0.85, 0.95, 0.99]

    def add_point(self, value):
        self.max = self.max if self.max > value else value
        self.min = self.min if self.min < value else value
        self.sum.append(value)
        if self.count < self.sample_size:
            self.samples.append(value)
        else:
            self.samples[random.randrange(0, self.sample_size)] = value
        self.count = iternext(self.iter_counter)

    def flush(self, timestamp, interval):
        if not self.count:
            return []
        metrics = [
            (timestamp, self.min, "%s.min" % self.name, self.tags, self.host, MetricType.Gauge, interval),
            (timestamp, self.max, "%s.max" % self.name, self.tags, self.host, MetricType.Gauge, interval),
            (
                timestamp,
                self.count / float(interval),
                "%s.count" % self.name,
                self.tags,
                self.host,
                MetricType.Rate,
                interval,
            ),
            (timestamp, self.average(), "%s.avg" % self.name, self.tags, self.host, MetricType.Gauge, interval),
        ]
        length = len(self.samples)
        self.samples.sort()
        for p in self.percentiles:
            val = self.samples[int(round(p * length - 1))]
            name = "%s.%spercentile" % (self.name, int(p * 100))
            metrics.append((timestamp, val, name, self.tags, self.host, MetricType.Gauge, interval))
        return metrics

    def average(self):
        sum_metrics = sum(self.sum, 0)
        return float(sum_metrics) / self.count


class Timing(Histogram):
    """
    A timing metric.
    Inherit from Histogram to workaround and support it in API mode
    """

    stats_tag = "ms"


class MetricsAggregator(object):
    """
    A small class to handle the roll-ups of multiple metrics at once.
    """

    def __init__(self, roll_up_interval=10):
        self._lock = threading.RLock()
        self._metrics = defaultdict(lambda: {})
        self._roll_up_interval = roll_up_interval

    def add_point(self, metric, tags, timestamp, value, metric_class, sample_rate=1, host=None):
        # The sample rate is currently ignored for in process stuff
        interval = timestamp - timestamp % self._roll_up_interval
        key = (metric, host, tuple(sorted(tags)) if tags else None)
        with self._lock:
            if key not in self._metrics[interval]:
                self._metrics[interval][key] = metric_class(metric, tags, host)
            self._metrics[interval][key].add_point(value)

    def flush(self, timestamp):
        """ Flush all metrics up to the given timestamp. """
        if timestamp == float("inf"):
            interval = float("inf")
        else:
            interval = timestamp - timestamp % self._roll_up_interval

        with self._lock:
            past_intervals = [i for i in self._metrics.keys() if i < interval]
            metrics = []
            for i in past_intervals:
                for m in list(self._metrics.pop(i).values()):
                    metrics += m.flush(i, self._roll_up_interval)
        return metrics
