from decorator import decorator
from datadog import initialize
from datadog.threadstats import ThreadStats
from threading import Lock

import logging
log = logging.getLogger('datadog.lambda')

lambda_stats = ThreadStats()
_counter_lock = Lock()


class _Wrappers_state(object):  # Trick used to share state variables between modules
    opened_wrappers = 0  # Flush only once all wrapped functions are done running
    was_initalized = False


@decorator
def datadog_lambda_wrapper(func, *args, **kw):
    """ Wrapper to automatically initialize the client & flush

    Usage for lambdas:

    @datadog_lambda_wrapper  # Use env variables DATADOG_API_KEY & DATADOG_APP_KEY
    def my_lambda_function(event, context):
        ....

    """

    with _counter_lock:
        if not(_Wrappers_state.was_initalized):
            _Wrappers_state.was_initalized = True
            initialize()
            lambda_stats.start(flush_in_greenlet=False, flush_in_thread=False)
        _Wrappers_state.opened_wrappers = _Wrappers_state.opened_wrappers + 1

    result = func(*args, **kw)  # Run the lambda

    with _counter_lock:
        _Wrappers_state.opened_wrappers = _Wrappers_state.opened_wrappers - 1
        if _Wrappers_state.opened_wrappers <= 0:
            lambda_stats.flush(float("inf"))

    return result
