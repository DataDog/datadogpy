import threading
import time

from datadog.dogstatsd.metrics import CountMetric, GaugeMetric, SetMetric

class Aggregator(object):
    def __init__(self, client):
        self.client = client

        self.metrics_map = {
            'counts': {},
            'gauges': {},
            'sets': {}
        }
        self.locks = {
            'counts': threading.RLock(),
            'gauges': threading.RLock(),
            'sets': threading.RLock()
        }

        self.closed = threading.Event()
        self.exited = threading.Event()

    def start(self, flush_interval):
        self.flush_interval = flush_interval
        self.ticker = threading.Timer(self.flush_interval, self._tick)
        self.ticker.start()

    def tick(self):
        while not self.closed.is_set():
            self.send_metrics()
            time.sleep(self.flush_interval)
        self.exited.set()

    def send_metrics(self):
        for metric in self.flush_metrics():
            self.client.send(metric)

    def stop(self):
        self.closed.set()
        self.ticker.cancel()
        self.exited.wait()
        self.send_metrics()

    def flush_metrics(self):
        metrics = []

        for metric_type in self.metrics_maps.keys():
            with self.locks[metric_type]:
                current_metrics = self.metrics_map[metric_type]
                self.metrics_map[metric_type] = {}

            # TODO: the data type for unsafe_flush still needs to be decided.
            for metric in current_metrics.values():
                metrics.extend(metric.unsafe_flush() if isinstance(metric, SetMetric) else [metric.unsafe_flush()])

        return metrics

    def get_context(self, name, tags):
        return "{}:{}".format(name, ",".join(tags))

    # This function may not be necessary, can just call add_metric directly
    def count(self, name, value, tags, rate, timestamp=0):
        return self.add_metric('counts', CountMetric, name, value, tags, rate, timestamp)
    # This function may not be necessary, can just call add_metric directly
    def gauge(self, name, value, tags, rate, timestamp=0):
        return self.add_metric('gauges', GaugeMetric, name, value, tags, rate, timestamp)
    # This function may not be necessary, can just call add_metric directly
    def set(self, name, value, tags, rate, timestamp=0):
        return self.add_metric('sets', SetMetric, name, value, tags, rate, timestamp)

    def add_metric(self, metric_type, metric_class, name, value, tags, rate, timestamp=0):
        context = self.get_context(name, tags)
        with self.locks[metric_type]:
            if context in self.metrics_map[metric_type]:
                self.metrics_map[metric_type][context].aggregate(value)
            else:
                self.metrics_map[metric_type][context] = metric_class(name, value, tags, rate, timestamp)
        return None
