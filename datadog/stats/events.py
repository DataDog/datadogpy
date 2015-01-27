from datadog.util.compat import is_p3k


class EventsAggregator(object):
    """
    A simple event aggregator
    """
    def __init__(self):
        self._events = []

    def add_event(self, **event):
        # Clean empty values
        if is_p3k():
            event = {k: v for k, v in event.items() if v}
        else:
            event = {k: v for k, v in event.iteritems() if v}
        self._events.append(event)

    def flush(self):
        events = self._events
        self._events = []
        return events
