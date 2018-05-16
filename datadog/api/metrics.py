# stdlib
import time
from numbers import Number

# datadog
from datadog.api.exceptions import ApiError
from datadog.api.resources import SearchableAPIResource, SendableAPIResource, ListableAPIResource


class Metric(SearchableAPIResource, SendableAPIResource, ListableAPIResource):
    """
    A wrapper around Metric HTTP API
    """
    _resource_name = None

    _METRIC_QUERY_ENDPOINT = 'query'
    _METRIC_SUBMIT_ENDPOINT = 'series'
    _METRIC_LIST_ENDPOINT = 'metrics'

    @classmethod
    def _process_points(cls, points):
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
                timestamp = now if isinstance(point, Number) else point[0]
                value = float(point) if isinstance(point, Number) else float(point[1])

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

    @classmethod
    def list(cls, from_epoch):
        """
        Get a list of active metrics since a given time (Unix Epoc)

        :param from_epoch: Start time in Unix Epoc (seconds)

        :returns: Dictionary containing a list of active metrics
        """

        cls._resource_name = cls._METRIC_LIST_ENDPOINT

        try:
            seconds = int(from_epoch)
            params = {'from': seconds}
        except ValueError:
            raise ApiError("Parameter 'from_epoch' must be an integer")

        return super(Metric, cls).get_all(**params)

    @classmethod
    def send(cls, metrics=None, **single_metric):
        """
        Submit a metric or a list of metrics to the metric API

        :param metric: the name of the time series
        :type metric: string

        :param points: a (timestamp, value) pair or list of (timestamp, value) pairs
        :type points: list

        :param host: host name that produced the metric
        :type host: string

        :param tags:  list of tags associated with the metric.
        :type tags: string list

        :param type: type of the metric
        :type type: 'gauge' or 'count' or 'rate' string

        :returns: Dictionary representing the API's JSON response
        """
        def rename_metric_type(metric):
            """
            FIXME DROPME in 1.0:

            API documentation was illegitimately promoting usage of `metric_type` parameter
            instead of `type`.
            To be consistent and avoid 'backward incompatibilities', properly rename this parameter.
            """
            if 'metric_type' in metric:
                metric['type'] = metric.pop('metric_type')

        # Set the right endpoint
        cls._resource_name = cls._METRIC_SUBMIT_ENDPOINT

        # Format the payload
        try:
            if metrics:
                for metric in metrics:
                    if isinstance(metric, dict):
                        rename_metric_type(metric)
                        metric['points'] = cls._process_points(metric['points'])
                metrics_dict = {"series": metrics}
            else:
                rename_metric_type(single_metric)
                single_metric['points'] = cls._process_points(single_metric['points'])
                metrics = [single_metric]
                metrics_dict = {"series": metrics}

        except KeyError:
            raise KeyError("'points' parameter is required")

        return super(Metric, cls).send(attach_host_name=True, **metrics_dict)

    @classmethod
    def query(cls, **params):
        """
        Query metrics from Datadog

        :param start: query start timestamp
        :type start: POSIX timestamp

        :param end: query end timestamp
        :type end: POSIX timestamp

        :param query: metric query
        :type query: string query

        :returns: Dictionary representing the API's JSON response

        *start* and *end* should be less than 24 hours apart.
        It is *not* meant to retrieve metric data in bulk.

        >>> api.Metric.query(start=int(time.time()) - 3600, end=int(time.time()),
                             query='avg:system.cpu.idle{*}')
        """
        # Set the right endpoint
        cls._resource_name = cls._METRIC_QUERY_ENDPOINT

        # `from` is a reserved keyword in Python, therefore
        # `api.Metric.query(from=...)` is not permited
        # -> map `start` to `from` and `end` to `to`
        try:
            params['from'] = params.pop('start')
            params['to'] = params.pop('end')
        except KeyError as e:
            raise ApiError("The parameter '{0}' is required".format(e.args[0]))

        return super(Metric, cls)._search(**params)
