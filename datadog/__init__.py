"""
Datadogpy is a collection of Datadog Python tools.
It contains:
* datadog.api: a Python client for Datadog REST API.
* datadog.dogstatsd: a DogStatsd Python client.
* datadog.threadstats: an alternative tool to DogStatsd client for collecting application metrics
without hindering performance.
* datadog.dogshell: a command-line tool, wrapping datadog.api, to interact with Datadog REST API.
"""
# stdlib
import logging
import os
import os.path

# datadog
from datadog import api
from datadog.dogstatsd import DogStatsd, statsd  # noqa
from datadog.threadstats import ThreadStats  # noqa
from datadog.util.compat import iteritems
from datadog.util.config import get_version
from datadog.util.hostname import get_hostname


__version__ = get_version()

# Loggers
logging.getLogger('datadog.api').addHandler(logging.NullHandler())
logging.getLogger('datadog.dogstatsd').addHandler(logging.NullHandler())
logging.getLogger('datadog.threadstats').addHandler(logging.NullHandler())


def initialize(api_key=None, app_key=None, host_name=None, api_host=None,
               statsd_host=None, statsd_port=None, statsd_use_default_route=False, **kwargs):
    """
    Initialize and configure Datadog.api and Datadog.statsd modules

    :param api_key: Datadog API key
    :type api_key: string

    :param app_key: Datadog application key
    :type app_key: string

    :param proxies: Proxy to use to connect to Datadog API
    :type proxies: dictionary mapping protocol to the URL of the proxy.

    :param api_host: Datadog API endpoint
    :type api_host: url

    :param statsd_host: Host of DogStatsd server or statsd daemon
    :type statsd_host: address

    :param statsd_port: Port of DogStatsd server or statsd daemon
    :type statsd_port: port

    :param statsd_use_default_route: Dynamically set the statsd host to the default route
    (Useful when running the client in a container)
    :type statsd_use_default_route: boolean

    :param cacert: Path to local certificate file used to verify SSL \
        certificates. Can also be set to True (default) to use the systems \
        certificate store, or False to skip SSL verification
    :type cacert: path or boolean

    :param mute: Mute any ApiError or ClientError before they escape \
        from datadog.api.HTTPClient (default: True).
    :type mute: boolean
    """
    # API configuration
    api._api_key = api_key if api_key is not None else os.environ.get('DATADOG_API_KEY')
    api._application_key = app_key if app_key is not None else os.environ.get('DATADOG_APP_KEY')
    api._host_name = host_name if host_name is not None else get_hostname()
    api._api_host = api_host if api_host is not None else \
        os.environ.get('DATADOG_HOST', 'https://app.datadoghq.com')

    # Statsd configuration -overrides default statsd instance attributes-
    if statsd_host:
        statsd.host = statsd_host

    if statsd_port:
        statsd.port = int(statsd_port)

    if statsd_use_default_route:
        statsd.use_default_route = statsd_use_default_route

    # HTTP client and API options
    for key, value in iteritems(kwargs):
        attribute = "_{0}".format(key)
        setattr(api, attribute, value)
