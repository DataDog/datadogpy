from threading import Lock


class MetricAggregator(object):
    def __init__(self, name, tags, rate):
        self.name = name
        self.tags = tags
        self.rate = rate

    def aggregate(self, value):
        raise NotImplementedError("Subclasses should implement this method.")

    def flush_unsafe(self):
        raise NotImplementedError("Subclasses should implement this method.")


class CountMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate):
        super(CountMetric, self).__init__(name, tags, rate)
        self.value = value

    def aggregate(self, v):
        self.value += v

    def flush_unsafe(self):
        return {
            "metric_type": "count",
            "name": self.name,
            "tags": self.tags,
            "rate": self.rate,
            "ivalue": self.value,
        }


class GaugeMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate):
        super(GaugeMetric, self).__init__(name, tags, rate)
        self.value = value

    def aggregate(self, v):
        self.value = v

    def flush_unsafe(self):
        return {
            "metric_type": "gauge",
            "name": self.name,
            "tags": self.tags,
            "rate": self.rate,
            "fvalue": self.value,
        }


class SetMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate):
        super(SetMetric, self).__init__(name, tags, rate)
        self.data = set()
        self.data.add(value)
        self.lock = Lock()

    def aggregate(self, v):
        with self.lock:
            self.data.add(v)

    def flush_unsafe(self):
        with self.lock:
            if not self.data:
                return []
            return [
                {
                    "metric_type": "set",
                    "name": self.name,
                    "tags": self.tags,
                    "rate": self.rate,
                    "svalue": value,
                }
                for value in self.data
            ]
