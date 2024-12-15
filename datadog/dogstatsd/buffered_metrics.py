import random
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.metrics import MetricAggregator


class BufferedMetric(object):
    def __init__(self, name, tags, metric_type, specified_rate=1.0, max_metric_samples=0):
        self.name = name
        self.tags = tags
        self.metric_type = metric_type
        self.max_metric_samples = max_metric_samples
        self.specified_rate = specified_rate
        self.data = []
        self.stored_metric_samples = 0
        self.total_metric_samples = 0

    def sample(self, value):
        self.data.append(value)
        self.stored_metric_samples += 1
        self.total_metric_samples += 1

    def maybe_keep_sample(self, value):
        if self.max_metric_samples > 0:
            if self.stored_metric_samples >= self.max_metric_samples:
                i = random.randint(0, self.total_metric_samples - 1)
                if i < self.max_metric_samples:
                    self.data[i] = value
            else:
                self.data.append(value)
                self.stored_metric_samples += 1
            self.total_metric_samples += 1
        else:
            self.sample(value)

    def skip_sample(self):
        self.total_metric_samples += 1

    def flush(self):
        total_metric_samples = self.total_metric_samples
        if self.specified_rate != 1.0:
            rate = self.specified_rate
        else:
            rate = self.stored_metric_samples / total_metric_samples

        return [
            MetricAggregator(self.name, self.tags, rate, self.metric_type, value)
            for value in self.data
        ]


class HistogramMetric(BufferedMetric):
    def __init__(self, name, tags, rate=1.0, max_metric_samples=0):
        super(HistogramMetric, self).__init__(name, tags, MetricType.HISTOGRAM, rate, max_metric_samples)


class DistributionMetric(BufferedMetric):
    def __init__(self, name, tags, rate=1.0, max_metric_samples=0):
        super(DistributionMetric, self).__init__(name, tags, MetricType.DISTRIBUTION, rate, max_metric_samples)


class TimingMetric(BufferedMetric):
    def __init__(self, name, tags, rate=1.0, max_metric_samples=0):
        super(TimingMetric, self).__init__(name, tags, MetricType.TIMING, rate, max_metric_samples)