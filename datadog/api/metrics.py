import time

from datadog.api.base import SendableAPIResource


class Metric(SendableAPIResource):

    """
    A wrapper around Metric HTTP API.
    """
    _class_url = '/series'
    _json_name = 'series'

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
        try:
            if metrics:
                for metric in metrics:
                    if isinstance(metric, dict):
                        metric['points'] = cls._process_points(metric['points'])
                metrics_dict = {"series": metrics[0]}
            else:
                single_metric['points'] = cls._process_points(single_metric['points'])
                metrics = [single_metric]
                metrics_dict = {"series": metrics}

        except KeyError:
            raise KeyError("'points' parameter is required")

        return super(Metric, cls).send(attach_host_name=True, **metrics_dict)
