# -*- coding: utf-8 -*-
import threading
import unittest
from mock import patch
from datadog.dogstatsd.max_sample_metric import HistogramMetric, DistributionMetric, TimingMetric
from datadog.dogstatsd.max_sample_metric_context import MaxSampleMetricContexts
from datadog.dogstatsd.metric_types import MetricType

class TestMaxSampleMetric(unittest.TestCase):

    def test_new_histogram_metric(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0, cardinality=None)
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)
        self.assertEqual(s.cardinality, None)

    def test_histogram_metric_sample(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", rate=1.0, max_metric_samples=0, cardinality="high")
        s.sample(123.45)
        self.assertEqual(s.data, [123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)
        self.assertEqual(s.cardinality, "high")

    def test_flush_histogram_metric_sample(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", rate=1.0, max_metric_samples=0, cardinality="low")

        s.sample(21)
        m = s.flush()[0]
        self.assertEqual(m.metric_type, MetricType.HISTOGRAM)
        self.assertEqual(m.value, 21.0)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.rate, 1.0)
        self.assertEqual(m.tags, "tag1,tag2")
        self.assertEqual(m.cardinality, "low")

    def test_new_distribution_metric(self):
        s = DistributionMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0, cardinality="none")
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.DISTRIBUTION)
        self.assertEqual(s.cardinality, "none")

    def test_distribution_metric_sample(self):
        s = DistributionMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0, cardinality="orchestrator")
        s.sample(123.45)
        self.assertEqual(s.data, [123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.DISTRIBUTION)
        self.assertEqual(s.cardinality, "orchestrator")

    def test_flush_distribution_metric_sample(self):
        s = DistributionMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0, cardinality="none")
        s.sample(123.45)
        m = s.flush()[0]
        self.assertEqual(m.metric_type, MetricType.DISTRIBUTION)
        self.assertEqual(m.value, 123.45)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.tags, "tag1,tag2")
        self.assertEqual(m.cardinality, "none")

    def test_new_timing_metric(self):
        s = TimingMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0, cardinality=None)
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.TIMING)
        self.assertEqual(s.cardinality, None)

    def test_timing_metric_sample(self):
        s = TimingMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0, cardinality="high")
        s.sample(123.45)
        self.assertEqual(s.data, [123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.TIMING)
        self.assertEqual(s.cardinality, "high")

    def test_flush_timing_metric_sample(self):
        s = TimingMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0, cardinality="low")
        s.sample(123.45)
        m = s.flush()[0]
        self.assertEqual(m.metric_type, MetricType.TIMING)
        self.assertEqual(m.value, 123.45)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.tags, "tag1,tag2")
        self.assertEqual(m.cardinality, "low")

    def test_maybe_keep_sample_work_unsafe(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", rate=1.0, max_metric_samples=2, cardinality=None)
        s.maybe_keep_sample_work_unsafe(123)
        s.maybe_keep_sample_work_unsafe(456)
        s.maybe_keep_sample_work_unsafe(789)

        self.assertEqual(len(s.data), 2)
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)
        self.assertEqual(s.cardinality, None)

    def test_flush_rate_reflects_skipped_samples(self):
        s = HistogramMetric(name="test", tags=[], max_metric_samples=0, rate=1.0, cardinality=None)
        s.maybe_keep_sample_work_unsafe(1)
        s.maybe_keep_sample_work_unsafe(2)
        s.maybe_keep_sample_work_unsafe(3)
        s.skip_sample()
        s.skip_sample()

        metrics = s.flush()
        self.assertEqual(len(metrics), 3)
        for m in metrics:
            self.assertAlmostEqual(m.rate, 3 / 5)

    def test_flush_rate_reflects_bounded_reservoir_sampling(self):
        s = HistogramMetric(name="test", tags=[], max_metric_samples=2, rate=1.0, cardinality=None)
        s.maybe_keep_sample_work_unsafe(1)
        s.maybe_keep_sample_work_unsafe(2)
        s.maybe_keep_sample_work_unsafe(3)

        metrics = s.flush()
        self.assertEqual(len(metrics), 2)
        for m in metrics:
            self.assertAlmostEqual(m.rate, 2 / 3)

    def test_flush_rate_computed_inside_lock(self):
        """rate must be computed inside the lock so it is consistent with the returned samples.

        An intercepted lock injects a skip_sample() call right before the lock is
        actually acquired, simulating a concurrent thread that increments
        total_metric_samples at the worst possible moment.  With the old code the
        rate was calculated *before* lock acquisition (stored=10, total=10 → 1.0),
        and the injected skip would push total to 11 while the stale 1.0 was kept.
        With the fix, rate is calculated *inside* the lock, after the injection, so
        it correctly reflects 10/11.
        """
        s = HistogramMetric(name="test", tags=[], max_metric_samples=0, rate=1.0, cardinality=None)
        for i in range(10):
            s.maybe_keep_sample_work_unsafe(i)
        # stored=10, total=10

        real_lock = threading.Lock()

        class _InterceptedLock:
            def __enter__(self_inner):
                s.skip_sample()  # total becomes 11 right before the lock is acquired
                real_lock.acquire()
                return self_inner

            def __exit__(self_inner, *args):
                real_lock.release()

        s.lock = _InterceptedLock()
        metrics = s.flush()

        # The injected skip_sample made total=11 while stored stayed at 10.
        # rate must reflect the state *after* the injection: 10/11.
        self.assertEqual(len(metrics), 10)
        for m in metrics:
            self.assertAlmostEqual(m.rate, 10 / 11)

class TestMaxSampleMetricContexts(unittest.TestCase):

    @patch('datadog.dogstatsd.max_sample_metric_context.random.random', return_value=0.0)
    def test_sample_passes_rate_to_metric_constructor(self, _mock_random):
        """Ensure the rate parameter is forwarded when creating a new metric context."""
        contexts = MaxSampleMetricContexts(HistogramMetric)
        contexts.sample(
            name="test.metric",
            value=42,
            tags=["tag:value"],
            rate=0.5,
            context_key="test.metric:tag:value",
            max_samples_per_context=10,
            cardinality=None,
        )
        metric = contexts.values["test.metric:tag:value"]
        self.assertAlmostEqual(metric.specified_rate, 0.5)
        self.assertEqual(metric.max_metric_samples, 10)

    @patch('datadog.dogstatsd.max_sample_metric_context.random.random', return_value=0.0)
    def test_sample_passes_rate_to_distribution_metric(self, _mock_random):
        """Ensure the rate parameter is forwarded for distribution metrics."""
        contexts = MaxSampleMetricContexts(DistributionMetric)
        contexts.sample(
            name="test.dist",
            value=100,
            tags=["env:prod"],
            rate=0.3,
            context_key="test.dist:env:prod",
            max_samples_per_context=5,
            cardinality="low",
        )
        metric = contexts.values["test.dist:env:prod"]
        self.assertAlmostEqual(metric.specified_rate, 0.3)
        self.assertEqual(metric.max_metric_samples, 5)
        self.assertEqual(metric.cardinality, "low")


if __name__ == '__main__':
    unittest.main()
