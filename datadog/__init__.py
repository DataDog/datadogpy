"""
Datadog.py is a collection of Datadog Python tools.
It contains:
* datadog.api: a Python client for Datadog REST API.
* datadog.stats: a tool to collect application metrics without hindering
performance.
* datadog.dogshell: a wrapper around datadog.api
"""
from pkg_resources import get_distribution, DistributionNotFound
import os.path

from datadog import api
from datadog.stats import stats
from datadog.util.hostname import get_hostname


try:
    _dist = get_distribution("datadogpy")
    # Normalize case for Windows systems
    dist_loc = os.path.normcase(_dist.location)
    here = os.path.normcase(__file__)
    if not here.startswith(os.path.join(dist_loc, __name__)):
        # not installed, but there is another version that *is*e
        raise DistributionNotFound
except DistributionNotFound:
    __version__ = 'Please install datadogpy with setup.py'
else:
    __version__ = _dist.version


def initialize(api_key=None, app_key=None, host_name=None, api_host="https://app.datadoghq.com",
               proxies=None, **stats_params):
    """
    Configure api and stats instances

    :param api_key: Datadog API key
    :type api_key: string

    :param app_key: Datadog application key
    :type app_key: string

    :param proxies: Proxy to use to connect to Datadog API
    :type proxies: dictionary mapping protocol to the URL of the proxy.

    :param api_host: Datadog API endpoint
    :type api_host: url

    :param stats_params: DogStatsApi ``configure`` parameters
    :type stats_params: DogStatsApi parameters dictionary

    """
    # Configure api
    api._api_key = api_key
    api._application_key = app_key
    api._host_name = host_name if host_name is not None else get_hostname()
    api._api_host = api_host
    api._proxies = proxies

    # Configure stats
    stats.configure(**stats_params)
