from threading import Lock
import random


class MaxSampleMetricContexts:
    def __init__(self, max_sample_metric_type):
        self.lock = Lock()
        self.values = {}
        self.max_sample_metric_type = max_sample_metric_type

    def flush(self):
        metrics = []
        """Flush the metrics and reset the stored values."""
        for _, metric in self.values.items():
            metrics.append(metric.flush())
        self.values = {}
        return metrics

    def sample(self, name, value, tags, rate, context_key, max_samples_per_context):
        """Sample a metric and store it if it meets the criteria."""
        keeping_sample = self.should_sample(rate)
        with self.lock:
            if context_key not in self.values:
                # Create a new metric if it doesn't exist
                self.values[context_key] = self.max_sample_metric_type(name, tags, rate, max_samples_per_context)
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
