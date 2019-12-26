# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# flake8: noqa

# API settings
_api_key = None
_application_key = None
_api_version = 'v1'
_api_host = None
_host_name = None
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
