import unittest
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.aggregator import Aggregator


class TestAggregator(unittest.TestCase):
    def setUp(self):
        self.aggregator = Aggregator()

    def test_aggregator_sample(self):
        tags = ["tag1", "tag2"]
        for _ in range(2):
            self.aggregator.gauge("gaugeTest", 21, tags, 1)
            self.assertEqual(len(self.aggregator.metrics_map[MetricType.GAUGE]), 1)
            self.assertIn("gaugeTest:tag1,tag2", self.aggregator.metrics_map[MetricType.GAUGE])

            self.aggregator.count("countTest", 21, tags, 1)
            self.assertEqual(len(self.aggregator.metrics_map[MetricType.COUNT]), 1)
            self.assertIn("countTest:tag1,tag2", self.aggregator.metrics_map[MetricType.COUNT])

            self.aggregator.set("setTest", "value1", tags, 1)
            self.assertEqual(len(self.aggregator.metrics_map[MetricType.SET]), 1)
            self.assertIn("setTest:tag1,tag2", self.aggregator.metrics_map[MetricType.SET])

            self.aggregator.histogram("histogramTest", 21, tags, 1)
            self.assertEqual(len(self.aggregator.max_sample_metric_map[MetricType.HISTOGRAM].values), 1)
            self.assertIn("histogramTest:tag1,tag2", self.aggregator.max_sample_metric_map[MetricType.HISTOGRAM].values)

            self.aggregator.distribution("distributionTest", 21, tags, 1)
            self.assertEqual(len(self.aggregator.max_sample_metric_map[MetricType.DISTRIBUTION].values), 1)
            self.assertIn("distributionTest:tag1,tag2", self.aggregator.max_sample_metric_map[MetricType.DISTRIBUTION].values)

            self.aggregator.timing("timingTest", 21, tags, 1)
            self.assertEqual(len(self.aggregator.max_sample_metric_map[MetricType.TIMING].values), 1)
            self.assertIn("timingTest:tag1,tag2", self.aggregator.max_sample_metric_map[MetricType.TIMING].values)

    def test_aggregator_flush(self):
        tags = ["tag1", "tag2"]

        self.aggregator.gauge("gaugeTest1", 21, tags, 1)
        self.aggregator.gauge("gaugeTest1", 10, tags, 1)
        self.aggregator.gauge("gaugeTest2", 15, tags, 1)

        self.aggregator.count("countTest1", 21, tags, 1)
        self.aggregator.count("countTest1", 10, tags, 1)
        self.aggregator.count("countTest2", 1, tags, 1)

        self.aggregator.set("setTest1", "value1", tags, 1)
        self.aggregator.set("setTest1", "value1", tags, 1)
        self.aggregator.set("setTest1", "value2", tags, 1)
        self.aggregator.set("setTest2", "value1", tags, 1)

        self.aggregator.histogram("histogramTest1", 21, tags, 1)
        self.aggregator.histogram("histogramTest1", 22, tags, 1)
        self.aggregator.histogram("histogramTest2", 23, tags, 1)

        self.aggregator.distribution("distributionTest1", 21, tags, 1)
        self.aggregator.distribution("distributionTest1", 22, tags, 1)
        self.aggregator.distribution("distributionTest2", 23, tags, 1)

        self.aggregator.timing("timingTest1", 21, tags, 1)
        self.aggregator.timing("timingTest1", 22, tags, 1)
        self.aggregator.timing("timingTest2", 23, tags, 1)

        metrics = self.aggregator.flush_aggregated_metrics()
        metrics.extend(self.aggregator.flush_aggregated_sampled_metrics())
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.GAUGE]), 0)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.COUNT]), 0)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.SET]), 0)
        self.assertEqual(len(self.aggregator.max_sample_metric_map[MetricType.HISTOGRAM].values), 0)
        self.assertEqual(len(self.aggregator.max_sample_metric_map[MetricType.DISTRIBUTION].values), 0)
        self.assertEqual(len(self.aggregator.max_sample_metric_map[MetricType.TIMING].values), 0)
        self.assertEqual(len(metrics), 16)
        metrics.sort(key=lambda m: (m.metric_type, m.name, m.value))

        expected_metrics = [
            {"metric_type": MetricType.COUNT, "name": "countTest1", "tags": tags, "rate": 1, "value": 31, "timestamp": 0},
            {"metric_type": MetricType.COUNT, "name": "countTest2", "tags": tags, "rate": 1, "value": 1, "timestamp": 0},
            {"metric_type": MetricType.DISTRIBUTION, "name": "distributionTest1", "tags": tags, "rate": 1, "value": 21},
            {"metric_type": MetricType.DISTRIBUTION, "name": "distributionTest1", "tags": tags, "rate": 1, "value": 22},
            {"metric_type": MetricType.DISTRIBUTION, "name": "distributionTest2", "tags": tags, "rate": 1, "value": 23},
            {"metric_type": MetricType.GAUGE, "name": "gaugeTest1", "tags": tags, "rate": 1, "value": 10, "timestamp": 0},
            {"metric_type": MetricType.GAUGE, "name": "gaugeTest2", "tags": tags, "rate": 1, "value": 15, "timestamp": 0},
            {"metric_type": MetricType.HISTOGRAM, "name": "histogramTest1", "tags": tags, "rate": 1, "value": 21},
            {"metric_type": MetricType.HISTOGRAM, "name": "histogramTest1", "tags": tags, "rate": 1, "value": 22},
            {"metric_type": MetricType.HISTOGRAM, "name": "histogramTest2", "tags": tags, "rate": 1, "value": 23},
            {"metric_type": MetricType.TIMING, "name": "timingTest1", "tags": tags, "rate": 1, "value": 21},
            {"metric_type": MetricType.TIMING, "name": "timingTest1", "tags": tags, "rate": 1, "value": 22},
            {"metric_type": MetricType.TIMING, "name": "timingTest2", "tags": tags, "rate": 1, "value": 23},
            {"metric_type": MetricType.SET, "name": "setTest1", "tags": tags, "rate": 1, "value": "value1", "timestamp": 0},
            {"metric_type": MetricType.SET, "name": "setTest1", "tags": tags, "rate": 1, "value": "value2", "timestamp": 0},
            {"metric_type": MetricType.SET, "name": "setTest2", "tags": tags, "rate": 1, "value": "value1", "timestamp": 0},
        ]

        for metric, expected in zip(metrics, expected_metrics):
            self.assertEqual(metric.name, expected["name"])
            self.assertEqual(metric.tags, expected["tags"])
            self.assertEqual(metric.rate, expected["rate"])
            self.assertEqual(metric.value, expected["value"])
            
if __name__ == '__main__':
    unittest.main()
