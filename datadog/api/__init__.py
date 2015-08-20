# flake8: noqa

# API settings
_api_key = None
_application_key = None
_api_version = 'v1'
_api_host = None
_host_name = None
_cacert = True

# HTTP(S) settings
_proxies = None
_timeout = 3
_max_timeouts = 3
_max_retries = 3
_backoff_period = 300
_mute = True

# Resources
from datadog.api.comments import Comment
from datadog.api.downtimes import Downtime
from datadog.api.timeboards import Timeboard
from datadog.api.events import Event
from datadog.api.infrastructure import Infrastructure
from datadog.api.metrics import Metric
from datadog.api.monitors import Monitor
from datadog.api.screenboards import Screenboard
from datadog.api.graphs import Graph, Embed
from datadog.api.hosts import Host
from datadog.api.service_checks import ServiceCheck
from datadog.api.tags import Tag
from datadog.api.users import User
