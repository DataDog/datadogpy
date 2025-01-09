# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
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
from typing import Any, List, Optional

# datadog
from datadog import api
from datadog.dogstatsd import DogStatsd, statsd  # noqa
from datadog.threadstats import ThreadStats, datadog_lambda_wrapper, lambda_metric  # noqa
from datadog.util.compat import iteritems, NullHandler, text
from datadog.util.hostname import get_hostname
from datadog.version import __version__  # noqa

# Loggers
logging.getLogger("datadog.api").addHandler(NullHandler())
logging.getLogger("datadog.dogstatsd").addHandler(NullHandler())
logging.getLogger("datadog.threadstats").addHandler(NullHandler())


def initialize(
    api_key=None,  # type: Optional[str]
    app_key=None,  # type: Optional[str]
    host_name=None,  # type: Optional[str]
    api_host=None,  # type: Optional[str]
    statsd_host=None,  # type: Optional[str]
    statsd_port=None,  # type: Optional[int]
    statsd_disable_aggregation=True,  # type: bool
    statsd_disable_buffering=True,  # type: bool
    statsd_aggregation_flush_interval=0.3,  # type: float
    statsd_use_default_route=False,  # type: bool
    statsd_socket_path=None,  # type: Optional[str]
    statsd_namespace=None,  # type: Optional[str]
    statsd_max_samples_per_context=0,  # type: Optional[int]
    statsd_constant_tags=None,  # type: Optional[List[str]]
    return_raw_response=False,  # type: bool
    hostname_from_config=True,  # type: bool
    cardinality=None,  # type: Optional[str]
    **kwargs  # type: Any
):
    # type: (...) -> None
    """
    Initialize and configure Datadog.api and Datadog.statsd modules

    :param api_key: Datadog API key
    :type api_key: string

    :param app_key: Datadog application key
    :type app_key: string

    :param host_name: Set a specific hostname
    :type host_name: string

    :param proxies: Proxy to use to connect to Datadog API;
                    for example, 'proxies': {'http': "http:<user>:<pass>@<ip>:<port>/"}
    :type proxies: dictionary mapping protocol to the URL of the proxy.

    :param api_host: Datadog API endpoint
    :type api_host: url

    :param statsd_host: Host of DogStatsd server or statsd daemon
    :type statsd_host: address

    :param statsd_port: Port of DogStatsd server or statsd daemon
    :type statsd_port: port

    :param statsd_disable_buffering: Enable/disable statsd client buffering support
                                     (default: True).
    :type statsd_disable_buffering: boolean

    :param statsd_disable_aggregation: Enable/disable statsd client aggregation support
                                     (default: True).
    :type statsd_disable_aggregation: boolean

    :param statsd_max_samples_per_context: Set the max samples per context for Histogram,
    Distribution and Timing metrics. Use with the statsd_disable_aggregation set to False.
    :type statsd_max_samples_per_context: int

    :param statsd_aggregation_flush_interval: If aggregation is enabled, set the flush interval for
                    aggregation/buffering (This feature is experimental)
                                     (default: 0.3 seconds)
    :type statsd_aggregation_flush_interval: float

    :param statsd_use_default_route: Dynamically set the statsd host to the default route
                                     (Useful when running the client in a container)
    :type statsd_use_default_route: boolean

    :param statsd_socket_path: path to the DogStatsd UNIX socket. Supersedes statsd_host
                               and stats_port if provided.

    :param statsd_constant_tags: A list of tags to be applied to all metrics ("tag", "tag:value")
    :type statsd_constant_tags: list of string

    :param cacert: Path to local certificate file used to verify SSL \
        certificates. Can also be set to True (default) to use the systems \
        certificate store, or False to skip SSL verification
    :type cacert: path or boolean

    :param mute: Mute any ApiError or ClientError before they escape \
        from datadog.api.HTTPClient (default: True).
    :type mute: boolean

    :param return_raw_response: Whether or not to return the raw response object in addition \
        to the decoded response content (default: False)
    :type return_raw_response: boolean

    :param hostname_from_config: Set the hostname from the Datadog agent config (agent 5). Will be deprecated
    :type hostname_from_config: boolean

    :param cardinality: Set the global cardinality for all metrics. \
        Possible values are "none", "low", "orchestrator" and "high".
        Can also be set via the DATADOG_CARDINALITY or DD_CARDINALITY environment variables.
    :type cardinality: string

    """
    # API configuration
    api._api_key = api_key or api._api_key or os.environ.get("DATADOG_API_KEY", os.environ.get("DD_API_KEY"))
    api._application_key = (
        app_key or api._application_key or os.environ.get("DATADOG_APP_KEY", os.environ.get("DD_APP_KEY"))
    )
    api._hostname_from_config = hostname_from_config
    api._host_name = host_name or api._host_name or get_hostname(hostname_from_config)
    api._api_host = api_host or api._api_host or os.environ.get("DATADOG_HOST", "https://api.datadoghq.com")

    # Statsd configuration
    # ...overrides the default `statsd` instance attributes
    if statsd_socket_path:
        statsd.socket_path = statsd_socket_path
        statsd.host = None
        statsd.port = None
    else:
        if statsd_host or statsd_use_default_route:
            statsd.host = statsd.resolve_host(statsd_host, statsd_use_default_route)
        if statsd_port:
            statsd.port = int(statsd_port)
    statsd.close_socket()
    if statsd_namespace:
        statsd.namespace = text(statsd_namespace)
    if statsd_constant_tags:
        statsd.constant_tags += statsd_constant_tags

    if statsd_disable_aggregation:
        statsd.disable_aggregation()
    else:
        statsd.enable_aggregation(statsd_aggregation_flush_interval, statsd_max_samples_per_context)
    statsd.disable_buffering = statsd_disable_buffering
    api._return_raw_response = return_raw_response

    # Set the global cardinality for all metrics
    statsd.cardinality = cardinality or os.environ.get("DATADOG_CARDINALITY", os.environ.get("DD_CARDINALITY"))

    # HTTP client and API options
    for key, value in iteritems(kwargs):
        attribute = "_{}".format(key)
        setattr(api, attribute, value)
