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
from datadog.api.comments import Comment
from datadog.api.dashboard_lists import DashboardList
from datadog.api.distributions import Distribution
from datadog.api.downtimes import Downtime
from datadog.api.timeboards import Timeboard
from datadog.api.dashboards import Dashboard
from datadog.api.events import Event
from datadog.api.infrastructure import Infrastructure
from datadog.api.metadata import Metadata
from datadog.api.metrics import Metric
from datadog.api.monitors import Monitor
from datadog.api.screenboards import Screenboard
from datadog.api.graphs import Graph, Embed
from datadog.api.hosts import Host, Hosts
from datadog.api.service_checks import ServiceCheck
from datadog.api.tags import Tag
from datadog.api.users import User
from datadog.api.aws_integration import AwsIntegration
from datadog.api.aws_log_integration import AwsLogsIntegration
from datadog.api.azure_integration import AzureIntegration
from datadog.api.gcp_integration import GcpIntegration
from datadog.api.roles import Roles
from datadog.api.permissions import Permissions
from datadog.api.service_level_objectives import ServiceLevelObjective
from datadog.api.synthetics import Synthetics
from datadog.api.logs import Logs
from datadog.api.security_monitoring_rules import SecurityMonitoringRule
from datadog.api.security_monitoring_signals import SecurityMonitoringSignal
