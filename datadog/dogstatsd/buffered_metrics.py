import random
from datadog.dogstatsd.metric_types import MetricType


class BufferedMetric(object):
    def __init__(self, name, tags, metric_type, max_metrics=0, specified_rate=1.0):
        self.name = name
        self.tags = tags
        self.metric_type = metric_type
        self.max_metrics = max_metrics
        self.specified_rate = specified_rate
        self.data = []
        self.stored_metrics = 1
        self.total_metrics = 1

    def aggregate(self, value):
        self.data.append(value)
        self.stored_metrics += 1
        self.total_metrics += 1

    def maybe_add_metric(self, value):
        if self.max_metrics > 0:
            if self.stored_metrics >= self.max_metrics:
                i = random.randint(0, self.total_metrics - 1)
                if i < self.max_metrics:
                    self.data[i] = value
            else:
                self.data.append(value)
                self.stored_metrics += 1
            self.total_metrics += 1
        else:
            self.aggregate(value)

    def skip_metric(self):
        self.total_metrics += 1

    def flush(self):
        total_metrics = self.total_metrics
        if self.specified_rate != 1.0:
            rate = self.specified_rate
        else:
            rate = self.stored_metrics / total_metrics
   
        return {
            'name': self.name,
            'tags': self.tags,
            'metric_type': self.metric_type,
            'rate': rate,
            'values': self.data[:]
        }


class HistogramMetric(BufferedMetric):
    def __init__(self, name, value, tags, max_metrics=0, rate=1.0):
        super(HistogramMetric, self).__init__(name, tags, MetricType.HISTOGRAM, max_metrics, rate)
        self.aggregate(value)


class DistributionMetric(BufferedMetric):
    def __init__(self, name, value, tags, max_metrics=0, rate=1.0):
        super(DistributionMetric, self).__init__(name, tags, MetricType.DISTRIBUTION, max_metrics, rate)
        self.aggregate(value)


class TimingMetric(BufferedMetric):
    def __init__(self, name, value, tags, max_metrics=0, rate=1.0):
        super(TimingMetric, self).__init__(name, tags, MetricType.TIMING, max_metrics, rate)
        self.aggregate(value)
