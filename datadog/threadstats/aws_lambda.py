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

from datadog.threadstats import ThreadStats
from threading import Lock, Thread
from datadog import api
import os
import warnings

"""
DEPRECATED use datadog-lambda package instead https://git.io/fjy8o
Usage:

from datadog import datadog_lambda_wrapper, lambda_metric

@datadog_lambda_wrapper
def my_lambda_handle(event, context):
    lambda_metric("some_metric", 10)
"""


class _LambdaDecorator(object):
    """ DEPRECATED Decorator to automatically init & flush metrics, created for Lambda functions"""

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
                api._api_key = os.environ.get('DATADOG_API_KEY', os.environ.get('DD_API_KEY'))
                api._api_host = os.environ.get('DATADOG_HOST', 'https://api.datadoghq.com')

                # Async initialization of the TLS connection with our endpoints
                # This avoids adding execution time at the end of the lambda run
                t = Thread(target=_init_api_client)
                t.start()
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
        warnings.warn("datadog_lambda_wrapper() is relocated to https://git.io/fjy8o", DeprecationWarning)
        _LambdaDecorator._enter()
        try:
            return self.func(*args, **kw)
        finally:
            _LambdaDecorator._close()


_lambda_stats = ThreadStats()
_lambda_stats.start(flush_in_greenlet=False, flush_in_thread=False)
datadog_lambda_wrapper = _LambdaDecorator


def lambda_metric(*args, **kw):
    """ Alias to expose only distributions for lambda functions"""
    _lambda_stats.distribution(*args, **kw)


def _init_api_client():
    """ No-op GET to initialize the requests connection with DD's endpoints

    The goal here is to make the final flush faster:
    we keep alive the Requests session, this means that we can re-use the connection
    The consequence is that the HTTP Handshake, which can take hundreds of ms,
    is now made at the beginning of a lambda instead of at the end.

    By making the initial request async, we spare a lot of execution time in the lambdas.
    """
    try:
        api.api_client.APIClient.submit('GET', 'validate')
    except Exception:
        pass
