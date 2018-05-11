"""
Tests for the ThreadStats class, using HTTP mode
"""

# stdlib
import logging
import os
import random
import time
import unittest

# 3p
from mock import patch
import nose.tools as nt

# datadog
from datadog import ThreadStats
from tests.util.contextmanagers import preserve_environment_variable


# Silence the logger.
logger = logging.getLogger('dd.datadogpy')
logger.setLevel(logging.ERROR)


class MemoryReporter(object):
    """
    A reporting class that reports to memory for testing.
    """

    def __init__(self):
        self.metrics = []
        self.events = []

    def flush_metrics(self, metrics):
        self.metrics += metrics

    def flush_events(self, events):
        self.events += events


class TestUnitThreadStats(unittest.TestCase):
    """
    Unit tests for ThreadStats.
    """
    def setUp(self):
        """
        Set a mocked reporter.
        """
        self.reporter = MemoryReporter()

    def sort_metrics(self, metrics):
        """
        Sort metrics by timestamp of first point and then name.
        """
        def sort(metric):
            tags = metric['tags'] or []
            host = metric['host'] or ''
            return (metric['points'][0][0], metric['metric'], tags, host,
                    metric['points'][0][1])
        return sorted(metrics, key=sort)

    def assertMetric(self, name=None, value=None, tags=None, count=None):
        """
        Helper, to make assertions on metrics.
        """
        matching_metrics = []

        for metric in self.reporter.metrics:
            if name and name != metric['metric']:
                continue
            if value and value != metric['points'][0][1]:
                continue
            if tags and tags != metric['tags']:
                continue
            matching_metrics.append(metric)

        if count:
            self.assertEquals(
                len(matching_metrics), count,
                u"Candidate size assertion failure: expected {expected}, found {count}. "
                u"Metric name={name}, value={value}, tags={tags}.".format(
                    expected=count, count=len(matching_metrics),
                    name=name, value=value, tags=tags
                )
            )
        else:
            self.assertTrue(
                len(matching_metrics) > 0,
                u"Candidate size assertion failure: no matching metric found. "
                u"Metric name={name}, value={value}, tags={tags}.".format(
                    name=name, value=value, tags=tags
                )
            )

    def test_timed_decorator(self):
        dog = ThreadStats()
        dog.start(roll_up_interval=1, flush_in_thread=False)
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
        dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        event1_tag = "Event 2 tag"
        dog.event(event1_title, event1_text, priority=event1_priority,
                  date_happened=event1_date_happened, tags=[event1_tag])

        # Flush and test
        dog.flush()
        event, = reporter.events
        nt.assert_equal(event['title'], event1_title)
        nt.assert_equal(event['text'], event1_text)
        nt.assert_equal(event['priority'], event1_priority)
        nt.assert_equal(event['date_happened'], event1_date_happened)
        nt.assert_equal(event['tags'], [event1_tag])

    def test_event_constant_tags(self):
        constant_tag = 'type:constant'
        dog = ThreadStats(constant_tags=[constant_tag])
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        nt.assert_equal(event1['tags'], [constant_tag])
        nt.assert_equal(event2['title'], event2_title)
        nt.assert_equal(event2['text'], event2_text)
        nt.assert_equal(event2['text'], event2_text)
        nt.assert_equal(event2['tags'], [constant_tag])

        # Test more parameters
        reporter.events = []
        event1_priority = "low"
        event1_date_happened = 1375296969
        event1_tag = "Event 2 tag"
        dog.event(event1_title, event1_text, priority=event1_priority,
                  date_happened=event1_date_happened, tags=[event1_tag])

        # Flush and test
        dog.flush()
        event, = reporter.events
        nt.assert_equal(event['title'], event1_title)
        nt.assert_equal(event['text'], event1_text)
        nt.assert_equal(event['priority'], event1_priority)
        nt.assert_equal(event['date_happened'], event1_date_happened)
        nt.assert_equal(event['tags'], [event1_tag, constant_tag])

    def test_histogram(self):
        dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        nt.assert_equal(h1cnt1['points'][0][1], 0.4)
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
        nt.assert_equal(h1cnt2['points'][0][1], 0.3)
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
        nt.assert_equal(h2cnt1['points'][0][1], 0.1)

        # Flush again ensure they're gone.
        dog.reporter.metrics = []
        dog.flush(140.0)
        nt.assert_equal(len(dog.reporter.metrics), 8)
        dog.reporter.metrics = []
        dog.flush(200.0)
        nt.assert_equal(len(dog.reporter.metrics), 0)

    def test_histogram_percentiles(self):
        dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        nt.assert_equal(first['points'][0][1], 0.3)
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
        nt.assert_equal(first['points'][0][1], 0.8)
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
        dog = ThreadStats()
        dog.start(roll_up_interval=1, flush_in_thread=False)
        reporter = dog.reporter = MemoryReporter()
        dog.gauge('my.gauge', 1, 100.0)
        dog.flush(1000)
        metric = reporter.metrics[0]
        assert not metric['device']
        assert not metric['host']

    def test_custom_host_and_device(self):
        dog = ThreadStats()
        dog.start(roll_up_interval=1, flush_in_thread=False, device='dev')
        reporter = dog.reporter = MemoryReporter()
        dog.gauge('my.gauge', 1, 100.0, host='host')
        dog.flush(1000)
        metric = reporter.metrics[0]
        nt.assert_equal(metric['device'], 'dev')
        nt.assert_equal(metric['host'], 'host')

    def test_tags(self):
        dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        nt.assert_equal(c1['points'][0][1], 0.1)
        nt.assert_equal(c2['tags'], ['env:production', 'db'])
        nt.assert_equal(c2['points'][0][1], 0.1)
        nt.assert_equal(c3['tags'], ['env:staging'])
        nt.assert_equal(c3['points'][0][1], 0.1)

        (nt.assert_equal(c['metric'], 'gauge') for c in [g1, g2, g3])
        nt.assert_equal(g1['tags'], None)
        nt.assert_equal(g1['points'][0][1], 10)
        nt.assert_equal(g2['tags'], ['env:production', 'db'])
        nt.assert_equal(g2['points'][0][1], 15)
        nt.assert_equal(g3['tags'], ['env:staging'])
        nt.assert_equal(g3['points'][0][1], 20)

    def test_constant_tags(self):
        """
        Constant tags are attached to all metrics.
        """
        dog = ThreadStats(constant_tags=["type:constant"])
        dog.start(roll_up_interval=1, flush_in_thread=False)
        dog.reporter = self.reporter

        # Post the same metric with different tags.
        dog.gauge("gauge", 10, timestamp=100.0)
        dog.gauge("gauge", 15, timestamp=100.0, tags=["env:production", 'db'])
        dog.gauge("gauge", 20, timestamp=100.0, tags=["env:staging"])

        dog.increment("counter", timestamp=100.0)
        dog.increment("counter", timestamp=100.0, tags=["env:production", 'db'])
        dog.increment("counter", timestamp=100.0, tags=["env:staging"])

        dog.flush(200.0)

        # Assertions on all metrics
        self.assertMetric(count=6)

        # Assertions on gauges
        self.assertMetric(name='gauge', value=10, tags=["type:constant"], count=1)
        self.assertMetric(name="gauge", value=15, 
                          tags=["env:production", "db", "type:constant"], count=1)  # noqa
        self.assertMetric(name="gauge", value=20, tags=["env:staging", "type:constant"], count=1)

        # Assertions on counters
        self.assertMetric(name="counter", value=1, tags=["type:constant"], count=1)
        self.assertMetric(name="counter", value=1, 
                          tags=["env:production", "db", "type:constant"], count=1)  # noqa
        self.assertMetric(name="counter", value=1, tags=["env:staging", "type:constant"], count=1)

        # Ensure histograms work as well.
        @dog.timed('timed', tags=['version:1'])
        def do_nothing():
            """
            A function that does nothing, but being timed.
            """
            pass

        with patch("datadog.threadstats.base.time", return_value=300):
            do_nothing()

        dog.histogram('timed', 20, timestamp=300.0, tags=['db', 'version:2'])

        self.reporter.metrics = []
        dog.flush(400.0)

        # Histograms, and related metric types, produce 8 different metrics
        self.assertMetric(tags=["version:1", "type:constant"], count=8)
        self.assertMetric(tags=["db", "version:2", "type:constant"], count=8)

    def test_metric_namespace(self):
        """
        Namespace prefixes all metric names.
        """
        # Set up ThreadStats with a namespace
        dog = ThreadStats(namespace="foo")
        dog.start(roll_up_interval=1, flush_in_thread=False)
        dog.reporter = self.reporter

        # Send a few metrics
        dog.gauge("gauge", 20, timestamp=100.0)
        dog.increment("counter", timestamp=100.0)
        dog.flush(200.0)

        # Metric names are prefixed with the namespace
        self.assertMetric(count=2)
        self.assertMetric(name="foo.gauge", count=1)
        self.assertMetric(name="foo.counter", count=1)

    def test_host(self):
        dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        nt.assert_equal(c1['points'][0][1], 0.2)
        nt.assert_equal(c2['host'], 'test')
        nt.assert_equal(c2['tags'], None)
        nt.assert_equal(c2['points'][0][1], 0.1)
        nt.assert_equal(c3['host'], 'test')
        nt.assert_equal(c3['tags'], ['tag'])
        nt.assert_equal(c3['points'][0][1], 0.2)

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
        dog = ThreadStats()
        dog.start(disabled=True, flush_interval=1, roll_up_interval=1)
        reporter = dog.reporter = MemoryReporter()
        dog.gauge('testing', 1, timestamp=1000)
        dog.gauge('testing', 2, timestamp=1000)
        dog.flush(2000.0)
        assert not reporter.metrics

    def test_stop(self):
        dog = ThreadStats()
        dog.start(flush_interval=1, roll_up_interval=1)
        dog.reporter = MemoryReporter()
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

    def test_tags_from_environment(self):
        test_tags = ['country:china', 'age:45', 'blue']
        with preserve_environment_variable('DATADOG_TAGS'):
            os.environ['DATADOG_TAGS'] = ','.join(test_tags)
            dog = ThreadStats()
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        nt.assert_equal(event1['tags'], test_tags)
        nt.assert_equal(event2['title'], event2_title)
        nt.assert_equal(event2['text'], event2_text)
        nt.assert_equal(event2['text'], event2_text)
        nt.assert_equal(event2['tags'], test_tags)

        # Test more parameters
        reporter.events = []
        event1_priority = "low"
        event1_date_happened = 1375296969
        event1_tag = "Event 2 tag"
        dog.event(event1_title, event1_text, priority=event1_priority,
                  date_happened=event1_date_happened, tags=[event1_tag])

        # Flush and test
        dog.flush()
        event, = reporter.events
        nt.assert_equal(event['title'], event1_title)
        nt.assert_equal(event['text'], event1_text)
        nt.assert_equal(event['priority'], event1_priority)
        nt.assert_equal(event['date_happened'], event1_date_happened)
        nt.assert_equal(event['tags'], [event1_tag] + test_tags)
        dog.start(flush_interval=1, roll_up_interval=1)

    def test_tags_from_environment_and_constant(self):
        test_tags = ['country:china', 'age:45', 'blue']
        constant_tags = ['country:canada', 'red']
        with preserve_environment_variable('DATADOG_TAGS'):
            os.environ['DATADOG_TAGS'] = ','.join(test_tags)
            dog = ThreadStats(constant_tags=constant_tags)
        dog.start(roll_up_interval=10, flush_in_thread=False)
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
        nt.assert_equal(event1['tags'], constant_tags + test_tags)
        nt.assert_equal(event2['title'], event2_title)
        nt.assert_equal(event2['text'], event2_text)
        nt.assert_equal(event2['text'], event2_text)
        nt.assert_equal(event2['tags'], constant_tags + test_tags)

        # Test more parameters
        reporter.events = []
        event1_priority = "low"
        event1_date_happened = 1375296969
        event1_tag = "Event 2 tag"
        dog.event(event1_title, event1_text, priority=event1_priority,
                  date_happened=event1_date_happened, tags=[event1_tag])

        # Flush and test
        dog.flush()
        event, = reporter.events
        nt.assert_equal(event['title'], event1_title)
        nt.assert_equal(event['text'], event1_text)
        nt.assert_equal(event['priority'], event1_priority)
        nt.assert_equal(event['date_happened'], event1_date_happened)
        nt.assert_equal(event['tags'], [event1_tag] + constant_tags + test_tags)
        dog.start(flush_interval=1, roll_up_interval=1)

    def test_metric_type(self):
        """
        Checks the submitted metric's metric type.
        """
        # Set up ThreadStats with a namespace
        dog = ThreadStats(namespace="foo")
        dog.start(roll_up_interval=1, flush_in_thread=False)
        reporter = dog.reporter = self.reporter

        # Send a few metrics
        dog.gauge("gauge", 20, timestamp=100.0)
        dog.increment("counter", timestamp=100.0)
        dog.histogram('histogram.1', 20, 100.0)
        dog.flush(200.0)
		
        (first, second, p75, p85, p95, p99, avg, cnt, 
        max_, min_) = self.sort_metrics(reporter.metrics)
		
		# Assert Metric type
        nt.assert_equal(first['type'], 'rate')
        nt.assert_equal(second['type'], 'gauge')
        nt.assert_equal(p75['type'], 'gauge')
        nt.assert_equal(p85['type'], 'gauge')
        nt.assert_equal(p95['type'], 'gauge')
        nt.assert_equal(p99['type'], 'gauge')
        nt.assert_equal(avg['type'], 'gauge')
        nt.assert_equal(cnt['type'], 'rate')
        nt.assert_equal(max_['type'], 'gauge')
        nt.assert_equal(min_['type'], 'gauge')