from datadog.dogstatsd.metric_types import MetricType


class MetricAggregator(object):
    def __init__(self, name, tags, rate, metric_type, value=0, timestamp=0, cardinality=None):
        self.name = name
        self.tags = tags
        self.rate = rate
        self.metric_type = metric_type
        self.value = value
        self.timestamp = timestamp
        self.cardinality = cardinality

    def aggregate(self, value):
        raise NotImplementedError("Subclasses should implement this method.")


class CountMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0, cardinality=None):
        super(CountMetric, self).__init__(
            name, tags, rate, MetricType.COUNT, value, timestamp, cardinality
        )

    def aggregate(self, v):
        self.value += v


class GaugeMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0, cardinality=None):
        super(GaugeMetric, self).__init__(
            name, tags, rate, MetricType.GAUGE, value, timestamp, cardinality
        )

    def aggregate(self, v):
        self.value = v


class SetMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0, cardinality=None):
        default_value = 0
        super(SetMetric, self).__init__(
            name, tags, rate, MetricType.SET, default_value, default_value, cardinality
        )
        self.data = set()
        self.data.add(value)

    def aggregate(self, v):
        self.data.add(v)

    def get_data(self):
        return [
            MetricAggregator(self.name, self.tags, self.rate, MetricType.SET, value)
            for value in self.data
        ]
