from threading import Lock
from datadog.dogstatsd.metric_types import MetricType

class MetricAggregator(object):
    def __init__(self, name, tags, rate, timestamp=0):
        self.name = name
        self.tags = tags
        self.rate = rate
        self.timestamp = timestamp

    def aggregate(self, value):
        raise NotImplementedError("Subclasses should implement this method.")

    def unsafe_flush(self):
        raise NotImplementedError("Subclasses should implement this method.")


class CountMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0):
        super(CountMetric, self).__init__(name, tags, rate, timestamp)
        self.value = value

    def aggregate(self, v):
        self.value += v

    def unsafe_flush(self):
        return {
            'metric_type': MetricType.COUNT,
            'name': self.name,
            'tags': self.tags,
            'rate': self.rate,
            'value': self.value,
            'timestamp': self.timestamp
        }


class GaugeMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0):
        super(GaugeMetric, self).__init__(name, tags, rate, timestamp)
        self.value = value

    def aggregate(self, v):
        self.value = v

    def unsafe_flush(self):
        return {
            'metric_type': MetricType.GAUGE,
            'name': self.name,
            'tags': self.tags,
            'rate': self.rate,
            'value': self.value,
            'timestamp': self.timestamp
        }


class SetMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0):
        super(SetMetric, self).__init__(name, tags, rate, timestamp)
        self.data = set()
        self.data.add(value)
        self.lock = Lock()

    def aggregate(self, v):
        with self.lock:
            self.data.add(v)

    def unsafe_flush(self):
        if not self.data:
            return []
        return [
            {
                'metric_type': MetricType.SET,
                'name': self.name,
                'tags': self.tags,
                'rate': self.rate,
                'value': value,
            }
            for value in self.data
        ]
