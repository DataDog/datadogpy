"""
Reporter classes.
"""


from datadog import api


class Reporter(object):

    def flush(self, metrics):
        raise NotImplementedError()


class HttpReporter(Reporter):

    def __init__(self, compress_payload=False):
        self.compress_payload = compress_payload

    def flush_distributions(self, distributions):
        api.Distribution.send(distributions, compress_payload=self.compress_payload)

    def flush_metrics(self, metrics):
        api.Metric.send(metrics, compress_payload=self.compress_payload)

    def flush_events(self, events):
        for event in events:
            api.Event.create(**event)


class GraphiteReporter(Reporter):

    def flush(self, metrics):
        pass
