# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
from functools import wraps
from typing import Any, Callable, List, Optional, Text, TYPE_CHECKING, Union

try:
    from time import monotonic  # type: ignore[attr-defined]
except ImportError:
    from time import time as monotonic

# datadog
from datadog.dogstatsd.context_async import _get_wrapped_co
from datadog.util.compat import iscoroutinefunction

if TYPE_CHECKING:
    from datadog.dogstatsd.base import DogStatsd


class TimedContextManagerDecorator(object):
    """
    A context manager and a decorator which will report the elapsed time in
    the context OR in a function call.
    """

    def __init__(
        self,
        statsd,  # type: DogStatsd
        metric=None,  # type: Optional[Text]
        tags=None,  # type: Optional[List[str]]
        sample_rate=1,  # type: Optional[float]
        use_ms=None,  # type: Optional[bool]
    ):  # type(...) -> None
        self.statsd = statsd
        self.timing_func = statsd.timing
        self.metric = metric
        self.tags = tags
        self.sample_rate = sample_rate
        self.use_ms = use_ms
        self.elapsed = None  # type: Optional[Union[float, int]]

    def __call__(
        self, func  # type: Callable[..., Any]
    ):  # type(...) -> Callable[..., Any]
        """
        Decorator which returns the elapsed time of the function call.

        Default to the function name if metric was not provided.
        """
        if not self.metric:
            self.metric = "%s.%s" % (func.__module__, func.__name__)

        # Coroutines
        if iscoroutinefunction(func):
            return _get_wrapped_co(self, func)

        # Others
        @wraps(func)
        def wrapped(*args, **kwargs):
            start = monotonic()
            try:
                return func(*args, **kwargs)
            finally:
                self._send(start)

        return wrapped

    def __enter__(self):  # type(...) -> TimedContextManagerDecorator
        if not self.metric:
            raise TypeError("Cannot used timed without a metric!")
        self._start = monotonic()
        return self

    def __exit__(self, type, value, traceback):  # type(...) -> None
        # Report the elapsed time of the context manager.
        self._send(self._start)

    def _send(
        self,
        start,  # type: float
    ):  # type(...) -> None
        elapsed = monotonic() - start
        use_ms = self.use_ms if self.use_ms is not None else self.statsd.use_ms
        elapsed = int(round(1000 * elapsed)) if use_ms else elapsed
        self.timing_func(self.metric, elapsed, self.tags, self.sample_rate)  # type: ignore
        self.elapsed = elapsed

    def start(self):  # type(...) -> None
        self.__enter__()

    def stop(self):  # type(...) -> None
        self.__exit__(None, None, None)


class DistributedContextManagerDecorator(TimedContextManagerDecorator):
    """
    A context manager and a decorator which will report the elapsed time in
    the context OR in a function call using the custom distribution metric.
    """

    def __init__(
        self,
        statsd,  # type: DogStatsd
        metric=None,  # type: Optional[Text]
        tags=None,  # type: Optional[List[str]]
        sample_rate=1,  # type: Optional[float]
        use_ms=None,  # type: Optional[bool]
    ):  # type(...) -> None
        super(DistributedContextManagerDecorator, self).__init__(statsd, metric, tags, sample_rate, use_ms)
        self.timing_func = statsd.distribution
