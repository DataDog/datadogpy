"""
Event aggregator class.
"""

from datadog.util.compat import iteritems


class EventsAggregator(object):
    """
    A simple event aggregator
    """
    def __init__(self):
        self._events = []

    def add_event(self, **event):
        # Clean empty values
        event = dict((k, v) for k, v in iteritems(event) if v is not None)
        self._events.append(event)

    def flush(self):
        events = self._events
        self._events = []
        return events
