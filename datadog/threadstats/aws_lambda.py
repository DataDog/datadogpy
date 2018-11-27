from datadog.threadstats import ThreadStats
from threading import Lock
from datadog import api
import os


"""
Usage:

from datadog import datadog_lambda_wrapper, lambda_stats

@datadog_lambda_wrapper
def my_lambda_handle(event, context):
    lambda_stats.increment("some_metric", 10)
"""


class _LambdaDecorator(object):
    """ Decorator to automatically init & flush metrics, created for Lambda functions"""

    # Number of opened wrappers, flush when 0
    _counter = 0
    _counter_lock = Lock()
    _flush_lock = Lock()
    _was_initialized = False

    def __init__(self, func):
        self.func = func

    @classmethod
    def _enter(cls):
        with cls._counter_lock:
            if not cls._was_initialized:
                cls._was_initialized = True
                api._api_key = os.environ.get('DATADOG_API_KEY')
                api._api_host = os.environ.get('DATADOG_HOST', 'https://api.datadoghq.com')
            cls._counter = cls._counter + 1

    @classmethod
    def _close(cls):
        should_flush = False
        with cls._counter_lock:
            cls._counter = cls._counter - 1

            # Flush only when all wrappers are closed
            if cls._counter <= 0:
                should_flush = True

        if should_flush:
            with cls._flush_lock:
                # Don't flush if other wrappers were opened while _flush_lock was locked
                with cls._counter_lock:
                    if cls._counter > 0:
                        should_flush = False
                if should_flush:
                    _lambda_stats.flush(float("inf"))

    def __call__(self, *args, **kw):
        _LambdaDecorator._enter()
        result = self.func(*args, **kw)
        _LambdaDecorator._close()
        return result


_lambda_stats = ThreadStats()
_lambda_stats.start(flush_in_greenlet=False, flush_in_thread=False)
datadog_lambda_wrapper = _LambdaDecorator


def lambda_stats(*args, **kw):
    """ Alias to expose only distributions for lambda functions"""
    _lambda_stats.distribution(*args, **kw)
