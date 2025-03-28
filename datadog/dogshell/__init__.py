# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import os
import warnings
import sys

# 3p
import argparse

# datadog
from datadog import initialize, __version__
from datadog.dogshell.comment import CommentClient
from datadog.dogshell.common import DogshellConfig
from datadog.dogshell.dashboard_list import DashboardListClient
from datadog.dogshell.downtime import DowntimeClient
from datadog.dogshell.event import EventClient
from datadog.dogshell.host import HostClient
from datadog.dogshell.hosts import HostsClient
from datadog.dogshell.metric import MetricClient
from datadog.dogshell.monitor import MonitorClient
from datadog.dogshell.screenboard import ScreenboardClient
from datadog.dogshell.search import SearchClient
from datadog.dogshell.service_check import ServiceCheckClient
from datadog.dogshell.service_level_objective import ServiceLevelObjectiveClient
from datadog.dogshell.tag import TagClient
from datadog.dogshell.timeboard import TimeboardClient
from datadog.dogshell.dashboard import DashboardClient
from datadog.dogshell.security_monitoring import SecurityMonitoringClient


def main():
    if sys.argv[0].endswith("dog"):
        warnings.warn("dog is pending deprecation. Please use dogshell instead.", PendingDeprecationWarning)

    parser = argparse.ArgumentParser(
        description="Interact with the Datadog API", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--config", help="location of your dogrc file (default ~/.dogrc)", default=os.path.expanduser("~/.dogrc")
    )
    parser.add_argument(
        "--api-key",
        help="your API key, from "
        "https://app.datadoghq.com/account/settings#api. "
        "You can also set the environment variables DATADOG_API_KEY or DD_API_KEY",
        dest="api_key",
        default=os.environ.get("DATADOG_API_KEY", os.environ.get("DD_API_KEY")),
    )
    parser.add_argument(
        "--application-key",
        help="your Application key, from "
        "https://app.datadoghq.com/account/settings#api. "
        "You can also set the environment variables DATADOG_APP_KEY or DD_APP_KEY",
        dest="app_key",
        default=os.environ.get("DATADOG_APP_KEY", os.environ.get("DD_APP_KEY")),
    )
    parser.add_argument(
        "--pretty",
        help="pretty-print output (suitable for human consumption, " "less useful for scripting)",
        dest="format",
        action="store_const",
        const="pretty",
    )
    parser.add_argument(
        "--raw", help="raw JSON as returned by the HTTP service", dest="format", action="store_const", const="raw"
    )
    parser.add_argument(
        "--timeout", help="time to wait in seconds before timing" " out an API call (default 10)", default=10, type=int
    )
    parser.add_argument(
        "-v", "--version", help="Dog API version", action="version", version="%(prog)s {0}".format(__version__)
    )

    parser.add_argument(
        "--api_host",
        help="Datadog site to send data, us (datadoghq.com), eu (datadoghq.eu), us3 (us3.datadoghq.com), \
              us5 (us5.datadoghq.com), ap1 (ap1.datadoghq.com), gov (ddog-gov.com), or custom url. default: us",
        dest="api_host",
    )

    config = DogshellConfig()

    # Set up subparsers for each service
    subparsers = parser.add_subparsers(title="Modes", dest="mode")
    subparsers.required = True

    CommentClient.setup_parser(subparsers)
    SearchClient.setup_parser(subparsers)
    MetricClient.setup_parser(subparsers)
    TagClient.setup_parser(subparsers)
    EventClient.setup_parser(subparsers)
    MonitorClient.setup_parser(subparsers)
    TimeboardClient.setup_parser(subparsers)
    DashboardClient.setup_parser(subparsers)
    ScreenboardClient.setup_parser(subparsers)
    DashboardListClient.setup_parser(subparsers)
    HostClient.setup_parser(subparsers)
    HostsClient.setup_parser(subparsers)
    DowntimeClient.setup_parser(subparsers)
    ServiceCheckClient.setup_parser(subparsers)
    ServiceLevelObjectiveClient.setup_parser(subparsers)
    SecurityMonitoringClient.setup_parser(subparsers)

    args = parser.parse_args()

    config.load(args.config, args.api_key, args.app_key, args.api_host)

    # Initialize datadog.api package
    initialize(**config)

    args.func(args)


if __name__ == "__main__":
    main()
