class MetricType(object):
    Gauge = "gauge"
    Counter = "counter"
    Histogram = "histogram"
    Rate = "rate"


class MonitorType(object):
    SERVICE_CHECK = 'service check'
    METRIC_ALERT = 'metric alert'
    QUERY_ALERT = 'query alert'
    ALL = (SERVICE_CHECK, METRIC_ALERT, QUERY_ALERT)
