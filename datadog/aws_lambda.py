from datadog.threadstats import ThreadStats
from threading import Lock


"""
Usage:

from datadog import datadog_lambda_wrapper, lambda_stats

@datadog_lambda_wrapper
def my_lambda_handle(event, context):
    lambda_stats.increment("some_metric", 10)
"""


class _LambdaDecorator(object):
    _counter = 0  # Number of opened wrappers, flush when 0
    _counter_lock = Lock()
    _was_initialized = False

    def __init__(self, func):
        self.func = func

    def _enter(self):
        with self._counter_lock:
            if not self._was_initialized:
                self._was_initialized = True
                from datadog import initialize  # Got blood on my hands now
                initialize()
                lambda_stats.start(flush_in_greenlet=False, flush_in_thread=False)
            self._counter = self._counter + 1

    def _close(self):
        should_flush = False
        with self._counter_lock:
            self._counter = self._counter - 1

            if self._counter <= 0:  # Flush only when all wrappers are closed
                should_flush = True

        if should_flush:
            lambda_stats.flush(float("inf"))

    def __call__(self, *args, **kw):
        self._enter()
        result = self.func(*args, **kw)
        self._close()
        return result


lambda_stats = ThreadStats()
datadog_lambda_wrapper = _LambdaDecorator
