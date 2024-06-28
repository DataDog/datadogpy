class MetricAggregator(object):
    def __init__(self, name, tags, rate):
        self.name = name
        self.tags = tags
        self.rate = rate

    def aggregate(self, value):
        raise NotImplementedError("Subclasses should implement this method.")

    # TODO: This may be implemented once flushing aggregated metrics is supported
    def unsafe_flush():
        pass


class CountMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate):
        super(CountMetric, self).__init__(name, tags, rate)
        self.value = value

    def aggregate(self, v):
        self.value += v

    # TODO: This may be implemented once flushing aggregated metrics is supported
    def unsafe_flush():
        pass


class GaugeMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate):
        super(GaugeMetric, self).__init__(name, tags, rate)
        self.value = value

    def aggregate(self, v):
        self.value = v

    # TODO: This may be implemented once flushing aggregated metrics is supported
    def unsafe_flush():
        pass


class SetMetric(MetricAggregator):
    def __init__(self, name, value, tags, rate):
        super(SetMetric, self).__init__(name, tags, rate)
        self.data = set()
        self.data.add(value)

    def aggregate(self, v):
        self.data.add(v)

    # TODO: This may be implemented once flushing aggregated metrics is supported
    def unsafe_flush():
        pass
