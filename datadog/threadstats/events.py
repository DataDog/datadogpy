# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
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
