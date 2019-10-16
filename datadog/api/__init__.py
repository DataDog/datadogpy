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
from datadog.api.service_level_objectives import ServiceLevelObjective