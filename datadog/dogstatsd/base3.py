from functools import wraps
from time import time


def _get_wrapped_co(self, func):
    @wraps(func)
    async def wrapped_co(*args, **kwargs):
        start = time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            self._send(start)
    return wrapped_co
