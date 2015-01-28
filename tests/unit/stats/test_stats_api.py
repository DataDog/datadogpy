"""
Tests for the DogStatsAPI class, using HTTP mode
"""

import logging
import random
import time
import threading

import nose.tools as nt
from nose.plugins.skip import SkipTest

from datadog.stats.dog_stats_api import DogStatsApi


# Silence the logger.
logger = logging.getLogger('dd.datadogpy')
logger.setLevel(logging.ERROR)


#
# Test fixtures.
#

class MemoryReporter(object):
    """ A reporting class that reports to memory for testing. """

    def __init__(self):
        self.metrics = []
        self.events = []

    def flush_metrics(self, metrics):
        self.metrics += metrics

    def flush_events(self, events):
        self.events += events


#
# Unit tests.
#
class TestUnitDogStatsAPI(object):
    """ Unit tests for the dog stats api. """

    def sort_metrics(self, metrics):
        """ Sort metrics by timestamp of first point and then name """
        def sort(metric):
            tags = metric['tags'] or []
            host = metric['host'] or ''
            return (metric['points'][0][0], metric['metric'], tags, host)
        return sorted(metrics, key=sort)

    def test_timed_decorator(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=1, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        @dog.timed('timed.test')
        def func(a, b, c=1, d=1):
            """docstring"""
            return (a, b, c, d)

        nt.assert_equal(func.__name__, 'func')
        nt.assert_equal(func.__doc__, 'docstring')

        result = func(1, 2, d=3)
        # Assert it handles args and kwargs correctly.
        nt.assert_equal(result, (1, 2, 1, 3))
        time.sleep(1)  # Argh. I hate this.
        dog.flush()
        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 8)
        (_, _, _, _, avg, count, max_, min_) = metrics
        nt.assert_equal(avg['metric'], 'timed.test.avg')
        nt.assert_equal(count['metric'], 'timed.test.count')
        nt.assert_equal(max_['metric'], 'timed.test.max')
        nt.assert_equal(min_['metric'], 'timed.test.min')

    def test_event(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=10, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        # Add two events
        event1_title = "Event 1 title"
        event2_title = "Event 1 title"
        event1_text = "Event 1 text"
        event2_text = "Event 2 text"
        dog.event(event1_title, event1_text)
        dog.event(event2_title, event2_text)

        # Flush and test
        dog.flush()
        event1, event2 = reporter.events
        nt.assert_equal(event1['title'], event1_title)
        nt.assert_equal(event1['text'], event1_text)
        nt.assert_equal(event2['title'], event2_title)
        nt.assert_equal(event2['text'], event2_text)

        # Test more parameters
        reporter.events = []
        event1_priority = "low"
        event1_date_happened = 1375296969
        dog.event(event1_title, event1_text, priority=event1_priority,
                  date_happened=event1_date_happened)

        # Flush and test
        dog.flush()
        event, = reporter.events
        nt.assert_equal(event['title'], event1_title)
        nt.assert_equal(event['text'], event1_text)
        nt.assert_equal(event['priority'], event1_priority)
        nt.assert_equal(event['date_happened'], event1_date_happened)

    def test_histogram(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=10, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        # Add some histogram metrics.
        dog.histogram('histogram.1', 20, 100.0)
        dog.histogram('histogram.1', 30, 105.0)
        dog.histogram('histogram.1', 40, 106.0)
        dog.histogram('histogram.1', 50, 106.0)

        dog.histogram('histogram.1', 30, 110.0)
        dog.histogram('histogram.1', 50, 115.0)
        dog.histogram('histogram.1', 40, 116.0)

        dog.histogram('histogram.2', 40, 100.0)

        dog.histogram('histogram.3', 50, 134.0)

        # Flush and ensure they roll up properly.
        dog.flush(120.0)
        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 24)

        # Test histograms elsewhere.
        (h1751, h1851, h1951, h1991, h1avg1, h1cnt1, h1max1, h1min1,
         _, _, _, _, h2avg1, h2cnt1, h2max1, h2min1,
         h1752, _, _, h1992, h1avg2, h1cnt2, h1max2, h1min2) = metrics

        nt.assert_equal(h1avg1['metric'], 'histogram.1.avg')
        nt.assert_equal(h1avg1['points'][0][0], 100.0)
        nt.assert_equal(h1avg1['points'][0][1], 35)
        nt.assert_equal(h1cnt1['metric'], 'histogram.1.count')
        nt.assert_equal(h1cnt1['points'][0][0], 100.0)
        nt.assert_equal(h1cnt1['points'][0][1], 4)
        nt.assert_equal(h1min1['metric'], 'histogram.1.min')
        nt.assert_equal(h1min1['points'][0][1], 20)
        nt.assert_equal(h1max1['metric'], 'histogram.1.max')
        nt.assert_equal(h1max1['points'][0][1], 50)
        nt.assert_equal(h1751['metric'], 'histogram.1.75percentile')
        nt.assert_equal(h1751['points'][0][1], 40)
        nt.assert_equal(h1991['metric'], 'histogram.1.99percentile')
        nt.assert_equal(h1991['points'][0][1], 50)

        nt.assert_equal(h1avg2['metric'], 'histogram.1.avg')
        nt.assert_equal(h1avg2['points'][0][0], 110.0)
        nt.assert_equal(h1avg2['points'][0][1], 40)
        nt.assert_equal(h1cnt2['metric'], 'histogram.1.count')
        nt.assert_equal(h1cnt2['points'][0][0], 110.0)
        nt.assert_equal(h1cnt2['points'][0][1], 3)
        nt.assert_equal(h1752['metric'], 'histogram.1.75percentile')
        nt.assert_equal(h1752['points'][0][0], 110.0)
        nt.assert_equal(h1752['points'][0][1], 40.0)
        nt.assert_equal(h1992['metric'], 'histogram.1.99percentile')
        nt.assert_equal(h1992['points'][0][0], 110.0)
        nt.assert_equal(h1992['points'][0][1], 50.0)

        nt.assert_equal(h2avg1['metric'], 'histogram.2.avg')
        nt.assert_equal(h2avg1['points'][0][0], 100.0)
        nt.assert_equal(h2avg1['points'][0][1], 40)
        nt.assert_equal(h2cnt1['metric'], 'histogram.2.count')
        nt.assert_equal(h2cnt1['points'][0][0], 100.0)
        nt.assert_equal(h2cnt1['points'][0][1], 1)

        # Flush again ensure they're gone.
        dog.reporter.metrics = []
        dog.flush(140.0)
        nt.assert_equal(len(dog.reporter.metrics), 8)
        dog.reporter.metrics = []
        dog.flush(200.0)
        nt.assert_equal(len(dog.reporter.metrics), 0)

    def test_histogram_percentiles(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=10, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()
        # Sample all numbers between 1-100 many times. This
        # means our percentiles should be relatively close to themselves.
        percentiles = list(range(100))
        random.shuffle(percentiles)  # in place
        for i in percentiles:
            for j in range(20):
                dog.histogram('percentiles', i, 1000.0)
        dog.flush(2000.0)
        metrics = reporter.metrics

        def assert_almost_equal(i, j, e=1):
            # Floating point math?
            assert abs(i - j) <= e, "%s %s %s" % (i, j, e)
        nt.assert_equal(len(metrics), 8)
        p75, p85, p95, p99, _, _, _, _ = self.sort_metrics(metrics)
        nt.assert_equal(p75['metric'], 'percentiles.75percentile')
        nt.assert_equal(p75['points'][0][0], 1000.0)
        assert_almost_equal(p75['points'][0][1], 75, 8)
        assert_almost_equal(p85['points'][0][1], 85, 8)
        assert_almost_equal(p95['points'][0][1], 95, 8)
        assert_almost_equal(p99['points'][0][1], 99, 8)

    def test_gauge(self):
        # Create some fake metrics.
        dog = DogStatsApi()
        dog.configure(roll_up_interval=10, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        dog.gauge('test.gauge.1', 20, 100.0)
        dog.gauge('test.gauge.1', 22, 105.0)
        dog.gauge('test.gauge.2', 30, 115.0)
        dog.gauge('test.gauge.3', 30, 125.0)
        dog.flush(120.0)

        # Assert they've been properly flushed.
        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 2)

        (first, second) = metrics
        nt.assert_equal(first['metric'], 'test.gauge.1')
        nt.assert_equal(first['points'][0][0], 100.0)
        nt.assert_equal(first['points'][0][1], 22)
        nt.assert_equal(second['metric'], 'test.gauge.2')

        # Flush again and make sure we're progressing.
        reporter.metrics = []
        dog.flush(130.0)
        nt.assert_equal(len(reporter.metrics), 1)

        # Finally, make sure we've flushed all metrics.
        reporter.metrics = []
        dog.flush(150.0)
        nt.assert_equal(len(reporter.metrics), 0)

    def test_counter(self):
        # Create some fake metrics.
        dog = DogStatsApi()
        dog.configure(roll_up_interval=10, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        dog.increment('test.counter.1', timestamp=1000.0)
        dog.increment('test.counter.1', value=2, timestamp=1005.0)
        dog.increment('test.counter.2', timestamp=1015.0)
        dog.increment('test.counter.3', timestamp=1025.0)
        dog.flush(1021.0)

        # Assert they've been properly flushed.
        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 2)
        (first, second) = metrics
        nt.assert_equal(first['metric'], 'test.counter.1')
        nt.assert_equal(first['points'][0][0], 1000.0)
        nt.assert_equal(first['points'][0][1], 3)
        nt.assert_equal(second['metric'], 'test.counter.2')

        # Test decrement
        dog.increment('test.counter.1', value=10, timestamp=1000.0)
        dog.decrement('test.counter.1', value=2, timestamp=1005.0)
        reporter.metrics = []
        dog.flush(1021.0)

        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 1)
        first, = metrics
        nt.assert_equal(first['metric'], 'test.counter.1')
        nt.assert_equal(first['points'][0][0], 1000.0)
        nt.assert_equal(first['points'][0][1], 8)
        nt.assert_equal(second['metric'], 'test.counter.2')

        # Flush again and make sure we're progressing.
        reporter.metrics = []
        dog.flush(1030.0)
        nt.assert_equal(len(reporter.metrics), 1)

        # Finally, make sure we've flushed all metrics.
        reporter.metrics = []
        dog.flush(1050.0)
        nt.assert_equal(len(reporter.metrics), 0)

    def test_default_host_and_device(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=1, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()
        dog.gauge('my.gauge', 1, 100.0)
        dog.flush(1000)
        metric = reporter.metrics[0]
        assert not metric['device']
        assert not metric['host']

    def test_custom_host_and_device(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=1, flush_in_thread=False, device='dev', statsd=False)
        reporter = dog.reporter = MemoryReporter()
        dog.gauge('my.gauge', 1, 100.0, host='host')
        dog.flush(1000)
        metric = reporter.metrics[0]
        nt.assert_equal(metric['device'], 'dev')
        nt.assert_equal(metric['host'], 'host')

    def test_tags(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=10, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        # Post the same metric with different tags.
        dog.gauge('gauge', 10, timestamp=100.0)
        dog.gauge('gauge', 15, timestamp=100.0, tags=['env:production', 'db'])
        dog.gauge('gauge', 20, timestamp=100.0, tags=['env:staging'])

        dog.increment('counter', timestamp=100.0)
        dog.increment('counter', timestamp=100.0, tags=['env:production', 'db'])
        dog.increment('counter', timestamp=100.0, tags=['env:staging'])

        dog.flush(200.0)

        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 6)

        [c1, c2, c3, g1, g2, g3] = metrics
        (nt.assert_equal(c['metric'], 'counter') for c in [c1, c2, c3])
        nt.assert_equal(c1['tags'], None)
        nt.assert_equal(c1['points'][0][1], 1)
        nt.assert_equal(c2['tags'], ['env:production', 'db'])
        nt.assert_equal(c2['points'][0][1], 1)
        nt.assert_equal(c3['tags'], ['env:staging'])
        nt.assert_equal(c3['points'][0][1], 1)

        (nt.assert_equal(c['metric'], 'gauge') for c in [g1, g2, g3])
        nt.assert_equal(g1['tags'], None)
        nt.assert_equal(g1['points'][0][1], 10)
        nt.assert_equal(g2['tags'], ['env:production', 'db'])
        nt.assert_equal(g2['points'][0][1], 15)
        nt.assert_equal(g3['tags'], ['env:staging'])
        nt.assert_equal(g3['points'][0][1], 20)

        # Ensure histograms work as well.
        @dog.timed('timed', tags=['version:1'])
        def test():
            pass
        test()
        dog.histogram('timed', 20, timestamp=300.0, tags=['db', 'version:2'])
        reporter.metrics = []
        dog.flush(400)
        for metric in reporter.metrics:
            assert metric['tags']  # this is enough

    def test_host(self):
        dog = DogStatsApi()
        dog.configure(roll_up_interval=10, flush_in_thread=False, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        # Post the same metric with different tags.
        dog.gauge('gauge', 12, timestamp=100.0, host='')  # unset the host
        dog.gauge('gauge', 10, timestamp=100.0)
        dog.gauge('gauge', 15, timestamp=100.0, host='test')
        dog.gauge('gauge', 15, timestamp=100.0, host='test')

        dog.increment('counter', timestamp=100.0)
        dog.increment('counter', timestamp=100.0)
        dog.increment('counter', timestamp=100.0, host='test')
        dog.increment('counter', timestamp=100.0, host='test', tags=['tag'])
        dog.increment('counter', timestamp=100.0, host='test', tags=['tag'])

        dog.flush(200.0)

        metrics = self.sort_metrics(reporter.metrics)
        nt.assert_equal(len(metrics), 6)

        [c1, c2, c3, g1, g2, g3] = metrics
        (nt.assert_equal(c['metric'], 'counter') for c in [c1, c2, c3])
        nt.assert_equal(c1['host'], None)
        nt.assert_equal(c1['tags'], None)
        nt.assert_equal(c1['points'][0][1], 2)
        nt.assert_equal(c2['host'], 'test')
        nt.assert_equal(c2['tags'], None)
        nt.assert_equal(c2['points'][0][1], 1)
        nt.assert_equal(c3['host'], 'test')
        nt.assert_equal(c3['tags'], ['tag'])
        nt.assert_equal(c3['points'][0][1], 2)

        (nt.assert_equal(g['metric'], 'gauge') for g in [g1, g2, g3])
        nt.assert_equal(g1['host'], None)
        nt.assert_equal(g1['points'][0][1], 10)
        nt.assert_equal(g2['host'], '')
        nt.assert_equal(g2['points'][0][1], 12)
        nt.assert_equal(g3['host'], 'test')
        nt.assert_equal(g3['points'][0][1], 15)

        # Ensure histograms work as well.
        @dog.timed('timed', host='test')
        def test():
            pass
        test()
        dog.histogram('timed', 20, timestamp=300.0, host='test')
        reporter.metrics = []
        dog.flush(400)
        for metric in reporter.metrics:
            assert metric['host'] == 'test'

    def test_disabled_mode(self):
        dog = DogStatsApi()
        reporter = dog.reporter = MemoryReporter()
        dog.configure(disabled=True, flush_interval=1, roll_up_interval=1, statsd=False)
        dog.gauge('testing', 1, timestamp=1000)
        dog.gauge('testing', 2, timestamp=1000)
        dog.flush(2000.0)
        assert not reporter.metrics

    def test_stop(self):
        dog = DogStatsApi()
        dog.configure(flush_interval=1, roll_up_interval=1, statsd=False)
        for i in range(10):
            dog.gauge('metric', i)
        time.sleep(2)
        flush_count = dog.flush_count
        assert flush_count
        dog.stop()
        for i in range(10):
            dog.gauge('metric', i)
        time.sleep(2)
        for i in range(10):
            dog.gauge('metric', i)
        time.sleep(2)
        assert dog.flush_count in [flush_count, flush_count + 1]

    def test_threadsafe_correctness(self):
        raise SkipTest("Passing on threadsafe for now")
        # A test to ensure we flush the expected values
        # when we have lots of threads writing to dog api
        dog = DogStatsApi()
        dog.configure(flush_interval=1, roll_up_interval=1, statsd=False)
        reporter = dog.reporter = MemoryReporter()

        class MetricProducer(threading.Thread):

            def id(self):
                return threading.current_thread().ident

            def run(self):
                print('running %s' % self.id())
                self.gauges = []
                self.count = 0
                end_time = time.time() + random.randint(0, 5)
                while time.time() < end_time:
                    m = 'gauge.%s.%s' % (time.time(), self.id())
                    self.gauges.append(m)
                    dog.gauge(m, 1)
                    # Also, increment a counter and ensure it works ok.
                    dog.increment('metric.count')
                    self.count += 1
                    time.sleep(0.01)

        # Start writing to dog api in a bunch of threads.
        num_threads = 10
        threads = [MetricProducer() for i in range(num_threads)]
        [t.start() for t in threads]
        # Also write a few metrics in the main thread.
        expected_gauges = ['gauge.%s' % i for i in range(100)]
        for g in expected_gauges:
            dog.gauge(g, 1)
        print('waiting for threads to finish')
        [t.join() for t in threads]

        # Wait for the flush/ roll up to complete.
        time.sleep(3)

        metrics = reporter.metrics
        metric_names = sorted((m['metric'] for m in metrics))

        #
        # Make sure we have the correct number of gauges.
        #
        for t in threads:
            expected_gauges += t.gauges
        expected_gauges.sort()
        gauges = [m for m in metric_names if 'gauge' in m]
        nt.assert_equal(gauges, expected_gauges)

        # assert the count is correct
        expected_count = sum((t.count for t in threads))
        actual_count = (sum((m['points'][0][1] for m in metrics if
                            m['metric'] == 'metric.count')))
        nt.assert_equal(actual_count, expected_count)
