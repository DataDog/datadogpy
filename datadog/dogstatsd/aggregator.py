import threading
import time
from datadog.dogstatsd.metrics import MetricAggregator, CountMetric, GaugeMetric, SetMetric
from datadog.dogstatsd.metric_types import MetricType

class Aggregator(object):
    def __init__(self, client):
        self.client = client

        self.metrics_map = {
            MetricType.COUNT: {},
            MetricType.GAUGE: {},
            MetricType.SET: {}
        }
        self.locks = {
            MetricType.COUNT: threading.RLock(),
            MetricType.GAUGE: threading.RLock(),
            MetricType.SET: threading.RLock()
        }

        self.closed = threading.Event()
        self.exited = threading.Event()

    def start(self, flush_interval):
        self.flush_interval = flush_interval
        self.ticker = threading.Timer(self.flush_interval, self.tick)
        self.ticker.start()

    def tick(self):
        while not self.closed.is_set():
            self.send_metrics()
            time.sleep(self.flush_interval)
        self.exited.set()

    def send_metrics(self):
        for metric in self.flush_metrics():
            self.client._report(metric.name, metric.type, metric.value, metric.tags, metric.timestamp)

    def stop(self):
        self.closed.set()
        self.ticker.cancel()
        self.exited.wait()
        self.send_metrics()

    def flush_metrics(self):
        metrics: list[MetricAggregator] = []

        for metric_type in self.metrics_map.keys():
            with self.locks[metric_type]:
                current_metrics = self.metrics_map[metric_type]
                self.metrics_map[metric_type] = {}

            for metric in current_metrics.values():
                metrics.extend(metric.get_data() if isinstance(metric, SetMetric) else [metric])

        return metrics

    def get_context(self, name, tags):
        return "{}:{}".format(name, ",".join(tags))

    def count(self, name, value, tags, rate, timestamp=0):
        return self.add_metric(MetricType.COUNT, CountMetric, name, value, tags, rate, timestamp)

    def gauge(self, name, value, tags, rate, timestamp=0):
        return self.add_metric(MetricType.GAUGE, GaugeMetric, name, value, tags, rate, timestamp)

    def set(self, name, value, tags, rate, timestamp=0):
        return self.add_metric(MetricType.SET, SetMetric, name, value, tags, rate, timestamp)

    def add_metric(self, metric_type, metric_class, name, value, tags, rate, timestamp=0):
        context = self.get_context(name, tags)
        with self.locks[metric_type]:
            if context in self.metrics_map[metric_type]:
                self.metrics_map[metric_type][context].aggregate(value)
            else:
                self.metrics_map[metric_type][context] = metric_class(name, value, tags, rate, timestamp)
