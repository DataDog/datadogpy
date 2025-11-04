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
        with self.lock:
            temp = self.values
            self.values = {}
        for _, metric in temp.items():
            metrics.append(metric.flush())
        return metrics

    def sample(self, name, value, tags, rate, context_key, max_samples_per_context, cardinality=None):
        """Sample a metric and store it if it meets the criteria."""
        keeping_sample = self.should_sample(rate)
        with self.lock:
            if context_key not in self.values:
                # Create a new metric if it doesn't exist
                self.values[context_key] = self.max_sample_metric_type(
                    name, tags, max_samples_per_context, cardinality=cardinality
                )
            metric = self.values[context_key]
            metric.lock.acquire()
        if keeping_sample:
            metric.maybe_keep_sample_work_unsafe(value)
        else:
            metric.skip_sample()
        metric.lock.release()

    def should_sample(self, rate):
        """Determine if a sample should be kept based on the specified rate."""
        if rate >= 1:
            return True
        return random.random() < rate
