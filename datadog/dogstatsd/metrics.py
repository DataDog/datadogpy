class MetricAggregator(object):
    def __init__(self, name, tags, rate, timestamp=0):
        self.name = name
        self.tags = tags
        self.rate = rate
        self.timestamp = timestamp

    def aggregate(self, value):
        raise NotImplementedError("Subclasses should implement this method.")

    # TODO: This may be implemented if flushing aggregated metrics is supported
    def unsafe_flush(self):
        pass


class CountMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0):
        super(CountMetric, self).__init__(name, tags, rate, timestamp)
        self.value = value

    def aggregate(self, v):
        self.value += v

    # TODO: This may be implemented if flushing aggregated metrics is supported
    def unsafe_flush(self):
        pass


class GaugeMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0):
        super(GaugeMetric, self).__init__(name, tags, rate, timestamp)
        self.value = value

    def aggregate(self, v):
        self.value = v

    # TODO: This may be implemented once flushing aggregated metrics is supported
    def unsafe_flush(self):
        pass


class SetMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate, timestamp=0):
        super(SetMetric, self).__init__(name, tags, rate, timestamp)
        self.data = set()
        self.data.add(value)

    def aggregate(self, v):
        self.data.add(v)

    # TODO: This may be implemented once flushing aggregated metrics is supported
    def unsafe_flush(self):
        pass
