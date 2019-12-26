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

import re
import time
import threading

from datadog import ThreadStats


class MemoryReporter(object):
    """ A reporting class that reports to memory for testing. """

    def __init__(self):
        self.metrics = []
        self.events = []

    def flush_metrics(self, metrics):
        self.metrics += metrics

    def flush_events(self, events):
        self.events += events


class ThreadStatsTest(ThreadStats):
    def send_metrics_and_event(self, id):
        # Counter
        self.increment("counter", timestamp=12345)
        time.sleep(0.001)  # sleep makes the os continue another thread

        # Gauge
        self.gauge("gauge_" + str(id), 42)
        time.sleep(0.001)  # sleep makes the os continue another thread

        # Histogram
        self.histogram("histogram", id, timestamp=12345)
        time.sleep(0.001)  # sleep makes the os continue another thread

        # Event
        self.event("title", "content")


class TestThreadStatsThreadSafety(object):

    def test_threadstats_thread_safety(self):
        stats = ThreadStatsTest()
        stats.start(roll_up_interval=10, flush_in_thread=False)
        reporter = stats.reporter = MemoryReporter()

        for i in range(10000):
            threading.Thread(target=stats.send_metrics_and_event, args=[i]).start()
        # Wait all threads to finish
        time.sleep(10)

        # Flush and check
        stats.flush()
        metrics = reporter.metrics
        events = reporter.events

        # Overview
        assert len(metrics) == 10009

        # Sort metrics
        counter_metrics = []
        gauge_metrics = []
        histogram_metrics = []

        for m in metrics:
            if re.match("gauge_.*", m['metric']):
                gauge_metrics.append(m)
            elif re.match("histogram.*", m['metric']):
                histogram_metrics.append(m)
            else:
                counter_metrics.append(m)

        # Counter
        assert len(counter_metrics) == 1
        counter = counter_metrics[0]
        assert counter['points'][0][1] == 10000

        # Gauge
        assert len(gauge_metrics) == 10000

        # Histogram
        assert len(histogram_metrics) == 8
        count_histogram = filter(lambda x: x['metric'] == "histogram.count", histogram_metrics)[0]
        assert count_histogram['points'][0][1] == 10000
        sum_histogram = filter(lambda x: x['metric'] == "histogram.avg", histogram_metrics)[0]
        assert sum_histogram['points'][0][1] == 4999.5

        # Events
        assert 10000 == len(events)
