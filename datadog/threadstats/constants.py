# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc


class MetricType(object):
    Gauge = "gauge"
    Counter = "counter"
    Histogram = "histogram"
    Rate = "rate"
    Distribution = "distribution"


class MonitorType(object):
    SERVICE_CHECK = "service check"
    METRIC_ALERT = "metric alert"
    QUERY_ALERT = "query alert"
    ALL = (SERVICE_CHECK, METRIC_ALERT, QUERY_ALERT)
