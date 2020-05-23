# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from numbers import Number
import sys
import time

if sys.version_info[0] >= 3:
    from collections.abc import Iterable
else:
    from collections import Iterable


def format_points(points):
    """
    Format `points` parameter.

    Input:
        a value or (timestamp, value) pair or a list of value or (timestamp, value) pairs

    Returns:
        list of (timestamp, float value) pairs

    """
    now = time.time()
    if not isinstance(points, list):
        points = [points]

    formatted_points = []
    for point in points:
        if isinstance(point, Number):
            timestamp = now
            value = float(point)
        # Distributions contain a list of points
        else:
            timestamp = point[0]
            if isinstance(point[1], Iterable):
                value = [float(p) for p in point[1]]
            else:
                value = float(point[1])

        formatted_points.append((timestamp, value))

    return formatted_points
