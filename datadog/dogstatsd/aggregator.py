import threading
from datadog.dogstatsd.metrics import (
    CountMetric,
    GaugeMetric,
    SetMetric,
)
from datadog.dogstatsd.metric_types import MetricType


class Aggregator(object):
    def __init__(self):
        self.metrics_map = {
            MetricType.COUNT: {},
            MetricType.GAUGE: {},
            MetricType.SET: {},
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
