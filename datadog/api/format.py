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
    points_lst = points if isinstance(points, list) else [points]

    def rec_parse(points_lst):
        """
        Recursively parse a list of values or a list of (timestamp, value) pairs to a list of
        (timestamp, `float` value) pairs.
        """
        try:
            if not points_lst:
                return []

            point = points_lst.pop()
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

            point = [(timestamp, value)]

            return point + rec_parse(points_lst)

        except TypeError as e:
            raise TypeError(
                u"{0}: "
                "`points` parameter must use real numerical values.".format(e)
            )

        except IndexError as e:
            raise IndexError(
                u"{0}: "
                u"`points` must be a list of values or "
                u"a list of (timestamp, value) pairs".format(e)
            )

    return rec_parse(points_lst)
