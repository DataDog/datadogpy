try:
    from collections.abc import Iterable
except ImportError:
    from collections import Iterable
from numbers import Number
import time


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
