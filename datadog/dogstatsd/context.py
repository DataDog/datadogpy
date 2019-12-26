# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from functools import wraps
from time import time

# datadog
from datadog.util.compat import (
    is_higher_py35,
    iscoroutinefunction,
)


if is_higher_py35():
    from datadog.dogstatsd.context_async import _get_wrapped_co
else:
    def _get_wrapped_co(self, func):
        raise NotImplementedError(
            u"Decorator `timed` compatibility with coroutine functions"
            u" requires Python 3.5 or higher."
        )


class TimedContextManagerDecorator(object):
    """
    A context manager and a decorator which will report the elapsed time in
    the context OR in a function call.
    """
    def __init__(self, statsd, metric=None, tags=None, sample_rate=1, use_ms=None):
        self.statsd = statsd
        self.metric = metric
        self.tags = tags
        self.sample_rate = sample_rate
        self.use_ms = use_ms
        self.elapsed = None

    def __call__(self, func):
        """
        Decorator which returns the elapsed time of the function call.

        Default to the function name if metric was not provided.
        """
        if not self.metric:
            self.metric = '%s.%s' % (func.__module__, func.__name__)

        # Coroutines
        if iscoroutinefunction(func):
            return _get_wrapped_co(self, func)

        # Others
        @wraps(func)
        def wrapped(*args, **kwargs):
            start = time()
            try:
                return func(*args, **kwargs)
            finally:
                self._send(start)
        return wrapped

    def __enter__(self):
        if not self.metric:
            raise TypeError("Cannot used timed without a metric!")
        self._start = time()
        return self

    def __exit__(self, type, value, traceback):
        # Report the elapsed time of the context manager.
        self._send(self._start)

    def _send(self, start):
        elapsed = time() - start
        use_ms = self.use_ms if self.use_ms is not None else self.statsd.use_ms
        elapsed = int(round(1000 * elapsed)) if use_ms else elapsed
        self.statsd.timing(self.metric, elapsed, self.tags, self.sample_rate)
        self.elapsed = elapsed

    def start(self):
        self.__enter__()

    def stop(self):
        self.__exit__(None, None, None)
