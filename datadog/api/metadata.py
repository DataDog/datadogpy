# stdlib
import time
from numbers import Number

# datadog
from datadog.api.exceptions import ApiError
from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, ActionAPIResource


class Metadata(GetableAPIResource, CreateableAPIResource, UpdatableAPIResource, ActionAPIResource):
    """
    A wrapper around Metric Metadata HTTP API
    """
    _class_url = '/metrics'
    _json_name = 'metrics'

    @classmethod
    def get(cls, metric_name):
        """
        Get metadata information on an existing Datadog metric

        param metric_name: metric name (ex. system.cpu.idle)

        :returns: JSON response from HTTP request
        """
        if not metric_name:
            raise KeyError("'metric_name' parameter is required")

        return super(Metadata, cls).get(metric_name)

    @classmethod
    def update(cls, metric_name, **params):
        """
        Query metrics from Datadog

        :param type: type of metric (ex. "gauge", "rate", etc.)
                            see http://docs.datadoghq.com/metrictypes/
        :type type: string

        :param description: description of the metric
        :type description: string

        :param short_name: short name of the metric
        :type short_name: string

        :param unit: unit type associated with the metric (ex. "byte", "operation")
                     see http://docs.datadoghq.com/units/ for full list
        :type unit: string

        :param per_unit: per unit type (ex. "second" as in "queries per second")
                         see http://docs.datadoghq.com/units/ for full list
        :type per_unit: string

        :param statsd_interval: statsd flush interval for metric in seconds (if applicable)
        :type statsd_interval: integer

        :return: JSON response from HTTP request

        >>> api.Metadata.update(metric_name='api.requests.served', metric_type="counter")
        """
        if not metric_name:
            raise KeyError("'metric_name' parameter is required")

        return super(Metadata, cls)._trigger_class_action('PUT', 'metrics', metric_name, **params)
