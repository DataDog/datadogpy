from threading import Lock
import random


class BufferedMetricContexts:
    def __init__(self, buffered_metric_type, max_metric_samples=0):
        self.nb_context = 0
        self.lock = Lock()
        self.values = {}
        self.max_metric_samples = max_metric_samples
        self.buffered_metric_type = buffered_metric_type

    def flush(self):
        metrics = []
        """Flush the metrics and reset the stored values."""
        with self.lock:
            copiedValues = self.values.copy()
            self.values.clear()
        self.values = {}
        for _, metric in copiedValues.items():
            metrics.append(metric.flush())

        self.nb_context += len(copiedValues)
        return metrics

    def sample(self, name, value, tags, rate, context_key):
        """Sample a metric and store it if it meets the criteria."""
        keeping_sample = self.should_sample(rate)
        with self.lock:
            if context_key not in self.values:
                # Create a new metric if it doesn't exist
                self.values[context_key] = self.buffered_metric_type(name, tags, rate, self.max_metric_samples)
            metric = self.values[context_key]
        if keeping_sample:
            metric.maybe_keep_sample(value)
        else:
            metric.skip_sample()

    def should_sample(self, rate):
        """Determine if a sample should be kept based on the specified rate."""
        if rate >= 1:
            return True
        return random.random() < rate
