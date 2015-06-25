import time

from datadog.api.base import SearchableAPIResource, SendableAPIResource
from datadog.api.exceptions import ApiError


class Metric(SearchableAPIResource, SendableAPIResource):
    """
    A wrapper around Metric HTTP API
    """
    _class_url = None
    _json_name = 'series'

    _METRIC_QUERY_ENDPOINT = '/query'
    _METRIC_SUBMIT_ENDPOINT = '/series'

    @classmethod
    def _process_points(cls, points):
        now = time.time()
        if isinstance(points, (float, int)):
            points = [(now, points)]
        elif isinstance(points, tuple):
            points = [points]
        return points

    @classmethod
    def send(cls, *metrics, **single_metric):
        """
        Submit a metric or a list of metrics to the metric API

        :param metric: the name of the time series
        :type metric: string

        :param points: list of points to submit
        :type points: list

        :param host: host name that produced the metric
        :type host: string

        :param tags:  list of tags associated with the metric.
        :type tags: string list

        :param metric_type: type of the metric
        :type metric_type: 'gauge' or 'counter' string

        :returns: JSON response from HTTP request
        """
        # Set the right endpoint
        cls._class_url = cls._METRIC_SUBMIT_ENDPOINT

        try:
            if metrics:
                for metric in metrics:
                    if isinstance(metric, dict):
                        metric['points'] = cls._process_points(metric['points'])
                metrics_dict = {"series": metrics}
            else:
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

        :return: JSON response from HTTP request

        *start* and *end* should be less than 24 hours apart.
        It is *not* meant to retrieve metric data in bulk.

        >>> api.Metric.query(start=int(time.time()) - 3600, end=int(time.time()),
                             query='avg:system.cpu.idle{*}')
        """
        # Set the right endpoint
        cls._class_url = cls._METRIC_QUERY_ENDPOINT

        # `from` is a reserved keyword in Python, therefore
        # `api.Metric.query(from=...)` is not permited
        # -> map `start` to `from` and `end` to `to`
        try:
            params['from'] = params.pop('start')
            params['to'] = params.pop('end')
        except KeyError as e:
            raise ApiError("The parameter '{0}' is required".format(e.args[0]))

        return super(Metric, cls)._search(**params)
