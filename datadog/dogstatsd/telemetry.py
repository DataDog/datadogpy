# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

# stdlib
import time
from threading import Lock


class Telemetry(object):
    def __init__(self, telemetry_min_flush_interval, tags):
        self.lock = Lock()
        self._tags = tags
        self._flush_interval = telemetry_min_flush_interval
        self.reset()

    def reset(self):
        self.metrics_count = 0
        self.events_count = 0
        self.service_checks_count = 0
        self.bytes_sent = 0
        self.bytes_dropped = 0
        self.packets_sent = 0
        self.packets_dropped = 0
        self._last_flush_time = time.time()

    def flush(self):
        serialized_tags = ",".join(self._tags)
        return "\n".join((
            "datadog.dogstatsd.client.metrics:%s|c|#%s" % (self.metrics_count, serialized_tags),
            "datadog.dogstatsd.client.events:%s|c|#%s" % (self.events_count, serialized_tags),
            "datadog.dogstatsd.client.service_checks:%s|c|#%s" % (self.service_checks_count, serialized_tags),
            "datadog.dogstatsd.client.bytes_sent:%s|c|#%s" % (self.bytes_sent, serialized_tags),
            "datadog.dogstatsd.client.bytes_dropped:%s|c|#%s" % (self.bytes_dropped, serialized_tags),
            "datadog.dogstatsd.client.packets_sent:%s|c|#%s" % (self.packets_sent, serialized_tags),
            "datadog.dogstatsd.client.packets_dropped:%s|c|#%s" % (self.packets_dropped, serialized_tags),
        ))

    def is_flush_time(self):
        return self._last_flush_time + self._flush_interval < time.time()
