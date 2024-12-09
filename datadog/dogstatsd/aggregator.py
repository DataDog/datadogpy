import threading
from datadog.dogstatsd.metrics import (
    CountMetric,
    GaugeMetric,
    SetMetric,
)
from datadog.dogstatsd.buffered_metrics import (
    HistogramMetric,
    DistributionMetric,
    TimingMetric
)
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.buffered_metrics_context import BufferedMetricContexts


class Aggregator(object):
    def __init__(self):
        self.metrics_map = {
            MetricType.COUNT: {},
            MetricType.GAUGE: {},
            MetricType.SET: {},
            MetricType.HISTOGRAM: BufferedMetricContexts(HistogramMetric),
            MetricType.DISTRIBUTION: BufferedMetricContexts(DistributionMetric),
            MetricType.TIMING: BufferedMetricContexts(TimingMetric)
        }
        self._locks = {
            MetricType.COUNT: threading.RLock(),
            MetricType.GAUGE: threading.RLock(),
            MetricType.SET: threading.RLock(),
        }

    def flush_aggregated_metrics(self):
        metrics = []
        for metric_type in self.metrics_map.keys():
            with self._locks[metric_type]:
                current_metrics = self.metrics_map[metric_type]
                self.metrics_map[metric_type] = {}
            for metric in current_metrics.values():
                metrics.extend(metric.get_data() if isinstance(metric, SetMetric) else [metric])
        return metrics

    def flush_aggregated_buffered_metrics(self):
        metrics = []
        for metric_type in self.buffered_metrics_map.keys():
            with self._locks[metric_type]:
                current_metrics = self.buffered_metrics_map[metric_type]
                self.buffered_metrics_map[metric_type] = {}
            for metric in current_metrics.values():
                metrics.append(metric)
        return metrics

    def get_context(self, name, tags):
        tags_str = ",".join(tags) if tags is not None else ""
        return "{}:{}".format(name, tags_str)

    def count(self, name, value, tags, rate, timestamp=0):
        return self.add_metric(
            MetricType.COUNT, CountMetric, name, value, tags, rate, timestamp
        )

    def gauge(self, name, value, tags, rate, timestamp=0):
        return self.add_metric(
            MetricType.GAUGE, GaugeMetric, name, value, tags, rate, timestamp
        )

    def set(self, name, value, tags, rate, timestamp=0):
        return self.add_metric(
            MetricType.SET, SetMetric, name, value, tags, rate, timestamp
        )

    def add_metric(
        self, metric_type, metric_class, name, value, tags, rate, timestamp=0
    ):
        context = self.get_context(name, tags)
        with self._locks[metric_type]:
            if context in self.metrics_map[metric_type]:
                self.metrics_map[metric_type][context].aggregate(value)
            else:
                self.metrics_map[metric_type][context] = metric_class(
                    name, value, tags, rate, timestamp
                )

    def histogram(self, name, value, tags, rate):
        return self.add_buffered_metric(
            MetricType.HISTOGRAM, name, value, tags, rate
        )

    def distribution(self, name, value, tags, rate):
        return self.add_buffered_metric(
            MetricType.DISTRIBUTION, name, value, tags, rate
        )

    def timing(self, name, value, tags, rate):
        return self.add_buffered_metric(
            MetricType.TIMING, name, value, tags, rate
        )

    def add_buffered_metric(
        self, metric_type, name, value, tags, rate
    ):
        context_key = self.get_context(name, tags)
        metric_context = self.metrics_map[metric_type]
        return metric_context.sample(name, value, tags, rate, context_key)
        
    
