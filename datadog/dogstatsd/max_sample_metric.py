import random
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.metrics import MetricAggregator
from threading import Lock


class MaxSampleMetric(object):
    def __init__(self, name, tags, metric_type, specified_rate=1.0, max_metric_samples=0, cardinality=None):
        self.name = name
        self.tags = tags
        self.lock = Lock()
        self.metric_type = metric_type
        self.max_metric_samples = max_metric_samples
        self.cardinality = cardinality
        self.specified_rate = specified_rate
        self.data = [None] * max_metric_samples if max_metric_samples > 0 else []
        self.stored_metric_samples = 0
        self.total_metric_samples = 0

    def sample(self, value):
        if self.max_metric_samples == 0:
            self.data.append(value)
        else:
            self.data[self.stored_metric_samples] = value
        self.stored_metric_samples += 1
        self.total_metric_samples += 1

    def maybe_keep_sample_work_unsafe(self, value):
        if self.max_metric_samples > 0:
            self.total_metric_samples += 1
            if self.stored_metric_samples < self.max_metric_samples:
                self.data[self.stored_metric_samples] = value
                self.stored_metric_samples += 1
            else:
                i = random.randint(0, self.total_metric_samples - 1)
                if i < self.max_metric_samples:
                    self.data[i] = value
        else:
            self.sample(value)

    def skip_sample(self):
        self.total_metric_samples += 1

    def flush(self):
        rate = self.stored_metric_samples / self.total_metric_samples
        with self.lock:
            return [
                MetricAggregator(
                    self.name, self.tags, rate, self.metric_type, self.data[i], cardinality=self.cardinality
                )
                for i in range(self.stored_metric_samples)
            ]


class HistogramMetric(MaxSampleMetric):
    def __init__(self, name, tags, rate=1.0, max_metric_samples=0, cardinality=None):
        super(HistogramMetric, self).__init__(name, tags, MetricType.HISTOGRAM, rate, max_metric_samples, cardinality)


class DistributionMetric(MaxSampleMetric):
    def __init__(self, name, tags, rate=1.0, max_metric_samples=0, cardinality=None):
        super(DistributionMetric, self).__init__(
            name, tags, MetricType.DISTRIBUTION, rate, max_metric_samples, cardinality
        )


class TimingMetric(MaxSampleMetric):
    def __init__(self, name, tags, rate=1.0, max_metric_samples=0, cardinality=None):
        super(TimingMetric, self).__init__(name, tags, MetricType.TIMING, rate, max_metric_samples, cardinality)
