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

    @classmethod
    def _enter(cls):
        with cls._counter_lock:
            if not cls._was_initialized:
                cls._was_initialized = True
                from datadog import initialize  # Got blood on my hands now
                initialize()
                lambda_stats.start(flush_in_greenlet=False, flush_in_thread=False)
            cls._counter = cls._counter + 1

    @classmethod
    def _close(cls):
        should_flush = False
        with cls._counter_lock:
            cls._counter = cls._counter - 1

            if cls._counter <= 0:  # Flush only when all wrappers are closed
                should_flush = True

        if should_flush:
            lambda_stats.flush(float("inf"))

    def __call__(self, *args, **kw):
        _LambdaDecorator._enter()
        result = self.func(*args, **kw)
        _LambdaDecorator._close()
        return result


lambda_stats = ThreadStats()
datadog_lambda_wrapper = _LambdaDecorator
