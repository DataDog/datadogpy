# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

import warnings
from functools import wraps
from typing import Any, Callable


def deprecated(message):
    # type: (str) -> Callable[[Callable[..., Any]], Callable[..., Any]]
    def deprecated_decorator(func):
        # type: (Callable[..., Any]) -> Callable[..., Any]
        @wraps(func)
        def deprecated_func(*args, **kwargs):
            # type: (*Any, **Any) -> Any
            warnings.warn(
                "'{0}' is a deprecated function. {1}".format(func.__name__, message),
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter('default', DeprecationWarning)

            return func(*args, **kwargs)

        return deprecated_func

    return deprecated_decorator
