import unittest
from datadog.dogstatsd.metric_types import MetricType
from datadog.dogstatsd.aggregator import Aggregator


class TestAggregator(unittest.TestCase):
    def setUp(self):
        self.aggregator = Aggregator()

    def test_aggregator_sample(self):
        tags = ["tag1", "tag2"]

        self.aggregator.gauge("gaugeTest", 21, tags, 1)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.GAUGE]), 1)
        self.assertIn("gaugeTest:tag1,tag2", self.aggregator.metrics_map[MetricType.GAUGE])

        self.aggregator.count("countTest", 21, tags, 1)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.COUNT]), 1)
        self.assertIn("countTest:tag1,tag2", self.aggregator.metrics_map[MetricType.COUNT])

        self.aggregator.set("setTest", "value1", tags, 1)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.SET]), 1)
        self.assertIn("setTest:tag1,tag2", self.aggregator.metrics_map[MetricType.SET])

        self.aggregator.gauge("gaugeTest", 123, tags, 1)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.GAUGE]), 1)
        self.assertIn("gaugeTest:tag1,tag2", self.aggregator.metrics_map[MetricType.GAUGE])

        self.aggregator.count("countTest", 10, tags, 1)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.COUNT]), 1)
        self.assertIn("countTest:tag1,tag2", self.aggregator.metrics_map[MetricType.COUNT])

        self.aggregator.set("setTest", "value1", tags, 1)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.SET]), 1)
        self.assertIn("setTest:tag1,tag2", self.aggregator.metrics_map[MetricType.SET])

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

        metrics = self.aggregator.flush_aggregated_metrics()
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.GAUGE]), 0)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.COUNT]), 0)
        self.assertEqual(len(self.aggregator.metrics_map[MetricType.SET]), 0)

        self.assertEqual(len(metrics), 7)
        metrics.sort(key=lambda m: (m.metric_type, m.name, m.value))
        expected_metrics = [
            {"metric_type": MetricType.COUNT, "name": "countTest1", "tags": tags, "rate": 1, "value": 31, "timestamp": 0},
            {"metric_type": MetricType.COUNT, "name": "countTest2", "tags": tags, "rate": 1, "value": 1, "timestamp": 0},
            {"metric_type": MetricType.GAUGE, "name": "gaugeTest1", "tags": tags, "rate": 1, "value": 10, "timestamp": 0},
            {"metric_type": MetricType.GAUGE, "name": "gaugeTest2", "tags": tags, "rate": 1, "value": 15, "timestamp": 0},
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
