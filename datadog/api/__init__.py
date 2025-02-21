# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# flake8: noqa

from typing import Optional

# API settings
_api_key = None  # type: Optional[str]
_application_key = None  # type: Optional[str]
_api_version = "v1"
_api_host = None  # type: Optional[str]
_host_name = None  # type: Optional[str]
_hostname_from_config = True
_cacert = True

# HTTP(S) settings
_proxies = None
_timeout = 60
_max_timeouts = 3
_max_retries = 3
_backoff_period = 300
_mute = True
_return_raw_response = False

# Resources
from datadog.api.comments import Comment as Comment
from datadog.api.dashboard_lists import DashboardList as DashboardList
from datadog.api.distributions import Distribution as Distribution
from datadog.api.downtimes import Downtime as Downtime
from datadog.api.timeboards import Timeboard as Timeboard
from datadog.api.dashboards import Dashboard as Dashboard
from datadog.api.events import Event as Event
from datadog.api.infrastructure import Infrastructure as Infrastructure
from datadog.api.metadata import Metadata as Metadata
from datadog.api.metrics import Metric as Metric
from datadog.api.monitors import Monitor as Monitor
from datadog.api.screenboards import Screenboard as Screenboard
from datadog.api.graphs import Graph as Graph, Embed as Embed
from datadog.api.hosts import Host as Host, Hosts as Hosts
from datadog.api.service_checks import ServiceCheck as ServiceCheck
from datadog.api.tags import Tag as Tag
from datadog.api.users import User as User
from datadog.api.aws_integration import AwsIntegration as AwsIntegration
from datadog.api.aws_log_integration import AwsLogsIntegration as AwsLogsIntegration
from datadog.api.azure_integration import AzureIntegration as AzureIntegration
from datadog.api.gcp_integration import GcpIntegration as GcpIntegration
from datadog.api.roles import Roles as Roles
from datadog.api.permissions import Permissions as Permissions
from datadog.api.service_level_objectives import (
    ServiceLevelObjective as ServiceLevelObjective,
)
from datadog.api.synthetics import Synthetics as Synthetics
from datadog.api.logs import Logs as Logs
