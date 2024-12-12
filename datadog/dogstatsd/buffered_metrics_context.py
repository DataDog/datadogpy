from threading import Lock
import secrets

from datadog.dogstatsd.buffered_metrics import BufferedMetric

class BufferedMetricContexts:
    def __init__(self, buffered_metric_type: BufferedMetric):
        self.nb_context = 0
        self.lock = Lock()
        self.values = {}
        self.buffered_metric_type = buffered_metric_type
        self.random = secrets

    def flush(self):
        metrics = []
        """Flush the metrics and reset the stored values."""
        with self.lock:
            values = self.values.copy()
            self.values.clear()

        for _, metric in values.items():
            metrics.append(metric.flush())

        self.nb_context += len(values)
        return metrics

    def sample(self, name, value, tags, rate, context_key):
        """Sample a metric and store it if it meets the criteria."""
        keeping_sample = self.should_sample(rate)
        print("keeping sample is ", keeping_sample)
        print("context_key is ", context_key)
        with self.lock:
            if context_key not in self.values:
                # Create a new metric if it doesn't exist
                self.values[context_key] = self.buffered_metric_type(name, tags, rate)
            metric = self.values[context_key]
        print("values are :", self.values.keys())
        if keeping_sample:
            metric.maybe_keep_sample(value)
        else:
            metric.skip_sample()

    def should_sample(self, rate):
        """Determine if a sample should be kept based on the specified rate."""
        if rate >= 1:
            return True
        return secrets.SystemRandom().random() < rate

    def get_nb_context(self):
        """Return the number of contexts."""
        return self.nb_context