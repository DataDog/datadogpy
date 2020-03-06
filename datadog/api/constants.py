# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc


class CheckStatus(object):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3
    ALL = (OK, WARNING, CRITICAL, UNKNOWN)


class MonitorType(object):
    # From https://docs.datadoghq.com/api/?lang=bash#create-a-monitor
    QUERY_ALERT = "query alert"
    COMPOSITE = "composite"
    SERVICE_CHECK = "service check"
    PROCESS_ALERT = "process alert"
    LOG_ALERT = "log alert"
    METRIC_ALERT = "metric alert"
    RUM_ALERT = "rum alert"
    EVENT_ALERT = "event alert"
    SYNTHETICS_ALERT = "synthetics alert"
    TRACE_ANALYTICS = "trace-analytics alert"
