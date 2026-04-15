from threading import Lock
import random
import sys

if sys.version_info[:2] >= (3, 5):
    from typing import Any, Dict, List, Optional, TYPE_CHECKING  # noqa: F401

    if TYPE_CHECKING:
        from datadog.dogstatsd.max_sample_metric import MaxSampleMetric
        from datadog.dogstatsd.metrics import MetricAggregator


class MaxSampleMetricContexts:
    def __init__(self, max_sample_metric_type):
        # type: (Any) -> None
        self.lock = Lock()
        self.values = {}  # type: Dict[str, MaxSampleMetric]
        self.max_sample_metric_type = max_sample_metric_type

    def flush(self):
        # type: () -> List[List[MetricAggregator]]
        metrics = []  # type: List[List[MetricAggregator]]
        """Flush the metrics and reset the stored values."""
        with self.lock:
            temp = self.values
            self.values = {}
        for _, metric in temp.items():
            metrics.append(metric.flush())
        return metrics

    def sample(self, name, value, tags, rate, context_key, max_samples_per_context, cardinality=None):
        # type: (str, Any, Optional[List[str]], float, str, int, Optional[str]) -> None
        """Sample a metric and store it if it meets the criteria."""
        keeping_sample = self.should_sample(rate)
        with self.lock:
            if context_key not in self.values:
                # Create a new metric if it doesn't exist
                self.values[context_key] = self.max_sample_metric_type(
                    name=name, tags=tags, rate=rate, max_metric_samples=max_samples_per_context, cardinality=cardinality
                )
            metric = self.values[context_key]
            metric.lock.acquire()
        if keeping_sample:
            metric.maybe_keep_sample_work_unsafe(value)
        else:
            metric.skip_sample()
        metric.lock.release()

    def should_sample(self, rate):
        # type: (float) -> bool
        """Determine if a sample should be kept based on the specified rate."""
        if rate >= 1:
            return True
        return random.random() < rate
