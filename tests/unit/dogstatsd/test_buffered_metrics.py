import unittest
from datadog.dogstatsd.buffered_metrics import HistogramMetric, DistributionMetric, TimingMetric
from datadog.dogstatsd.metric_types import MetricType

class TestBufferedMetric(unittest.TestCase):

    def test_new_histogram_metric(self):
        s = HistogramMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        self.assertEqual(s.data, [1.0])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)

    def test_histogram_metric_aggregate(self):
        s = HistogramMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        s.aggregate(123.45)
        self.assertEqual(s.data, [1.0, 123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.specified_rate, 1.0)
        self.assertEqual(s.metric_type, MetricType.HISTOGRAM)

    def test_flush_histogram_metric_aggregate(self):
        s = HistogramMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        m = s.flush()
        self.assertEqual(m['metric_type'], MetricType.HISTOGRAM)
        self.assertEqual(m['values'], [1.0])
        self.assertEqual(m['name'], "test")
        self.assertEqual(m['tags'], "tag1,tag2")

        s.aggregate(21)
        s.aggregate(123.45)
        m = s.flush()
        self.assertEqual(m['metric_type'], MetricType.HISTOGRAM)
        self.assertEqual(m['values'], [1.0, 21.0, 123.45])
        self.assertEqual(m['name'], "test")
        self.assertEqual(m['rate'], 1.0)
        self.assertEqual(m['tags'], "tag1,tag2")

    def test_new_distribution_metric(self):
        s = DistributionMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        self.assertEqual(s.data, [1.0])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.DISTRIBUTION)

    def test_distribution_metric_aggregate(self):
        s = DistributionMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        s.aggregate(123.45)
        self.assertEqual(s.data, [1.0, 123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.DISTRIBUTION)

    def test_flush_distribution_metric_aggregate(self):
        s = DistributionMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        m = s.flush()
        self.assertEqual(m['metric_type'], MetricType.DISTRIBUTION)
        self.assertEqual(m['values'], [1.0])
        self.assertEqual(m['name'], "test")
        self.assertEqual(m['tags'], "tag1,tag2")

        s.aggregate(21)
        s.aggregate(123.45)
        m = s.flush()
        self.assertEqual(m['metric_type'], MetricType.DISTRIBUTION)
        self.assertEqual(m['values'], [1.0, 21.0, 123.45])
        self.assertEqual(m['name'], "test")
        self.assertEqual(m['tags'], "tag1,tag2")

    def test_new_timing_metric(self):
        s = TimingMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        self.assertEqual(s.data, [1.0])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.TIMING)

    def test_timing_metric_aggregate(self):
        s = TimingMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        s.aggregate(123.45)
        self.assertEqual(s.data, [1.0, 123.45])
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, "tag1,tag2")
        self.assertEqual(s.metric_type, MetricType.TIMING)

    def test_flush_timing_metric_aggregate(self):
        s = TimingMetric(name="test", value=1.0, tags="tag1,tag2", max_metric_samples=0, rate=1.0)
        m = s.flush()
        self.assertEqual(m['metric_type'], MetricType.TIMING)
        self.assertEqual(m['values'], [1.0])
        self.assertEqual(m['name'], "test")
        self.assertEqual(m['tags'], "tag1,tag2")

        s.aggregate(21)
        s.aggregate(123.45)
        m = s.flush()
        self.assertEqual(m['metric_type'], MetricType.TIMING)
        self.assertEqual(m['values'], [1.0, 21.0, 123.45])
        self.assertEqual(m['name'], "test")
        self.assertEqual(m['tags'], "tag1,tag2")

if __name__ == '__main__':
    unittest.main()