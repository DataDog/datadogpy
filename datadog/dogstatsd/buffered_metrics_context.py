from threading import Lock
from random import random

from datadog.dogstatsd.buffered_metrics import BufferedMetric

class BufferedMetricContexts:
    def __init__(self, buffered_metric_type: BufferedMetric):
        self.nb_context = 0
        self.lock = Lock()
        self.values = {}
        self.buffered_metric_type = buffered_metric_type
        self.random = random.Random()
        self.random_lock = Lock()

    def flush(self, metrics):
        """Flush the metrics and reset the stored values."""
        with self.lock:
            values = self.values.copy()
            self.values.clear()

        for _, metric in values.items():
            with metric.lock:
                metrics.append(metric.flush())

        self.nb_context += len(values)
        return metrics

    def sample(self, name, value, tags, rate, context_key):
        """Sample a metric and store it if it meets the criteria."""
        keeping_sample = self.should_sample(rate)
        
        with self.lock:
            if context_key not in self.values:
                # Create a new metric if it doesn't exist
                self.values[context_key] = self.buffered_metric_type(name, value, tags, 0, rate)

            metric = self.values[context_key]

        if keeping_sample:
            with self.random_lock:
                metric.maybe_keep_sample(value, self.random, self.random_lock)
        else:
            metric.skip_sample()

    def should_sample(self, rate):
        """Determine if a sample should be kept based on the specified rate."""
        with self.random_lock:
            return self.random.random() < rate

    def get_nb_context(self):
        """Return the number of contexts."""
        return self.nb_context