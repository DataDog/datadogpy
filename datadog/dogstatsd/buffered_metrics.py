import random
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.metrics import MetricAggregator


class BufferedMetric(object):
    def __init__(self, name, tags, metric_type, max_metric_samples=0, specified_rate=1.0):
        self.name = name
        self.tags = tags
        self.metric_type = metric_type
        self.max_metric_samples = max_metric_samples
        self.specified_rate = specified_rate
        self.data = []
        self.stored_metric_samples = 1
        self.total_metric_samples = 1

    def sample(self, value):
        self.data.append(value)
        self.stored_metric_samples += 1
        self.total_metric_samples += 1

    def maybe_keep_sample(self, value):
        print("max metric samples is ", self.max_metric_samples)
        print("stored metric samples is ", self.stored_metric_samples)
        if self.max_metric_samples > 0:
            if self.stored_metric_samples >= self.max_metric_samples:
                i = random.randint(0, self.total_metric_samples - 1)
                if i < self.max_metric_samples:
                    print("REPLACE")
                    self.data[i] = value
            else:
                print("APPEND")
                self.data.append(value)
                self.stored_metric_samples += 1
            self.total_metric_samples += 1
        else:
            print("APPEND2")
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
    def __init__(self, name, tags, max_metric_samples=0, rate=1.0):
        super(HistogramMetric, self).__init__(name, tags, MetricType.HISTOGRAM, max_metric_samples, rate)


class DistributionMetric(BufferedMetric):
    def __init__(self, name, tags, max_metric_samples=0, rate=1.0):
        super(DistributionMetric, self).__init__(name, tags, MetricType.DISTRIBUTION, max_metric_samples, rate)


class TimingMetric(BufferedMetric):
    def __init__(self, name, tags, max_metric_samples=0, rate=1.0):
        super(TimingMetric, self).__init__(name, tags, MetricType.TIMING, max_metric_samples, rate)
