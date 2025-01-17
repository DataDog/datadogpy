import threading
from datadog.dogstatsd.metrics import (
    CountMetric,
    GaugeMetric,
    SetMetric,
)
from datadog.dogstatsd.max_sample_metric import (
    HistogramMetric,
    DistributionMetric,
    TimingMetric
)
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.max_sample_metric_context import MaxSampleMetricContexts


class Aggregator(object):
    def __init__(self, max_samples_per_context=0):
        self.max_samples_per_context = max_samples_per_context
        self.metrics_map = {
            MetricType.COUNT: {},
            MetricType.GAUGE: {},
            MetricType.SET: {},
        }
        self.max_sample_metric_map = {
            MetricType.HISTOGRAM: MaxSampleMetricContexts(HistogramMetric),
            MetricType.DISTRIBUTION: MaxSampleMetricContexts(DistributionMetric),
            MetricType.TIMING: MaxSampleMetricContexts(TimingMetric)
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

    def set_max_samples_per_context(self, max_samples_per_context=0):
        self.max_samples_per_context = max_samples_per_context

    def flush_aggregated_sampled_metrics(self):
        metrics = []
        for metric_type in self.max_sample_metric_map.keys():
            metric_context = self.max_sample_metric_map[metric_type]
            for metricList in metric_context.flush():
                metrics.extend(metricList)
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
        return self.add_max_sample_metric(
            MetricType.HISTOGRAM, name, value, tags, rate
        )

    def distribution(self, name, value, tags, rate):
        return self.add_max_sample_metric(
            MetricType.DISTRIBUTION, name, value, tags, rate
        )

    def timing(self, name, value, tags, rate):
        return self.add_max_sample_metric(
            MetricType.TIMING, name, value, tags, rate
        )

    def add_max_sample_metric(
        self, metric_type, name, value, tags, rate
    ):
        if rate is None:
            rate = 1
        context_key = self.get_context(name, tags)
        metric_context = self.max_sample_metric_map[metric_type]
        return metric_context.sample(name, value, tags, rate, context_key, self.max_samples_per_context)
