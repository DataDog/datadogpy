import unittest
from datadog.dogstatsd.max_sample_metric import HistogramMetric, DistributionMetric, TimingMetric
from datadog.dogstatsd.metric_types import MetricType

class TestMaxSampleMetric(unittest.TestCase):

    def test_new_histogram_metric(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)

    def test_histogram_metric_sample(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", rate=1.0, max_metric_samples=0)
        s.sample(123.45)
        self.assertEqual(s.data, [123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)

    def test_flush_histogram_metric_sample(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", rate=1.0, max_metric_samples=0)

        s.sample(21)
        m = s.flush()[0]
        self.assertEqual(m.metric_type, MetricType.HISTOGRAM)
        self.assertEqual(m.value, 21.0)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.rate, 1.0)
        self.assertEqual(m.tags, "tag1,tag2")

    def test_new_distribution_metric(self):
        s = DistributionMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.DISTRIBUTION)

    def test_distribution_metric_sample(self):
        s = DistributionMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        s.sample(123.45)
        self.assertEqual(s.data, [123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.DISTRIBUTION)

    def test_flush_distribution_metric_sample(self):
        s = DistributionMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        s.sample(123.45)
        m = s.flush()[0]
        self.assertEqual(m.metric_type, MetricType.DISTRIBUTION)
        self.assertEqual(m.value, 123.45)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.tags, "tag1,tag2")

    def test_new_timing_metric(self):
        s = TimingMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.TIMING)

    def test_timing_metric_sample(self):
        s = TimingMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        s.sample(123.45)
        self.assertEqual(s.data, [123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.TIMING)

    def test_flush_timing_metric_sample(self):
        s = TimingMetric(name="test", tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        s.sample(123.45)
        m = s.flush()[0]
        self.assertEqual(m.metric_type, MetricType.TIMING)
        self.assertEqual(m.value, 123.45)
        self.assertEqual(m.name, "test")
        self.assertEqual(m.tags, "tag1,tag2")

    def test_maybe_keep_sample(self):
        s = HistogramMetric(name="test", tags="tag1,tag2", rate=1.0, max_metric_samples=2)
        s.maybe_keep_sample(123)
        s.maybe_keep_sample(456)
        s.maybe_keep_sample(789)
        self.assertEqual(len(s.data), 2)
        self.assertFalse(123 in s.data and 456 in s.data)
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)

if __name__ == '__main__':
    unittest.main()