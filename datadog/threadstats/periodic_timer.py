# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
A small class to run a task periodically in a thread.
"""


from threading import Thread, Event
import sys


class PeriodicTimer(Thread):
    def __init__(self, interval, function, *args, **kwargs):
        Thread.__init__(self)
        self.daemon = True
        assert interval > 0
        self.interval = interval
        assert function
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.finished = Event()

    def end(self):
        self.finished.set()

    def run(self):
        while not self.finished.wait(self.interval):
            try:
                self.function(*self.args, **self.kwargs)
            except Exception:
                # If `sys` is None, it means the interpreter is shutting down
                # and it's very likely the reason why we got an exception.
                if sys is not None:
                    raise
