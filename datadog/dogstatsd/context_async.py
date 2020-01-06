# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Decorator `timed` for coroutine methods.

Warning: requires Python 3.5 or higher.
"""
# stdlib
from functools import wraps
from time import time


def _get_wrapped_co(self, func):
    """
    `timed` wrapper for coroutine methods.
    """
    @wraps(func)
    async def wrapped_co(*args, **kwargs):
        start = time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            self._send(start)
    return wrapped_co
