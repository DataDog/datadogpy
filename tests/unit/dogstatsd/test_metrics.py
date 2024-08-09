import unittest

from datadog.dogstatsd.metrics import CountMetric, GaugeMetric, SetMetric

class TestMetrics(unittest.TestCase):
    def test_new_count_metric(self):
        c = CountMetric("test", 21, ["tag1", "tag2"], 1, 1713804588)
        self.assertEqual(c.value, 21)
        self.assertEqual(c.name, "test")
        self.assertEqual(c.tags, ["tag1", "tag2"])
        self.assertEqual(c.rate, 1.0)
        self.assertEqual(c.timestamp, 1713804588)
        # Testing for default timestamp may be unecessary
        c_default_timestamp = CountMetric("test", 21, ["tag1", "tag2"], 1)
        self.assertEqual(c_default_timestamp.value, 21)
        self.assertEqual(c_default_timestamp.name, "test")
        self.assertEqual(c_default_timestamp.tags, ["tag1", "tag2"])
        self.assertEqual(c_default_timestamp.rate, 1.0)
        self.assertEqual(c_default_timestamp.timestamp, 0)

    def test_count_metric_aggregate(self):
        c = CountMetric("test", 10, ["tag1", "tag2"], 1, 1713804588)
        c.aggregate(20)
        self.assertEqual(c.value, 30)
        self.assertEqual(c.name, "test")
        self.assertEqual(c.tags, ["tag1", "tag2"])
        self.assertEqual(c.rate, 1.0)
        self.assertEqual(c.timestamp, 1713804588)

    def test_new_gauge_metric(self):
        g = GaugeMetric("test", 10, ["tag1", "tag2"], 1, 1713804588)
        self.assertEqual(g.value, 10)
        self.assertEqual(g.name, "test")
        self.assertEqual(g.tags, ["tag1", "tag2"])
        self.assertEqual(g.rate, 1)
        self.assertEqual(g.timestamp, 1713804588)

        g_default_timestamp = GaugeMetric("test", 10, ["tag1", "tag2"], 1)
        self.assertEqual(g_default_timestamp.value, 10)
        self.assertEqual(g_default_timestamp.name, "test")
        self.assertEqual(g_default_timestamp.tags, ["tag1", "tag2"])
        self.assertEqual(g_default_timestamp.rate, 1)
        self.assertEqual(g_default_timestamp.timestamp, 0)

    def test_gauge_metric_aggregate(self):
        g = GaugeMetric("test", 10, ["tag1", "tag2"], 1, 1713804588)
        g.aggregate(20)
        self.assertEqual(g.value, 20)
        self.assertEqual(g.name, "test")
        self.assertEqual(g.tags, ["tag1", "tag2"])
        self.assertEqual(g.rate, 1.0)
        self.assertEqual(g.timestamp, 1713804588)

    def test_new_set_metric(self):
        s = SetMetric("test", "value1", ["tag1", "tag2"], 1)
        self.assertEqual(s.data, {"value1"})
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, ["tag1", "tag2"])
        self.assertEqual(s.rate, 1)
        self.assertEqual(s.timestamp, 0)

    def test_set_metric_aggregate(self):
        s = SetMetric("test", "value1", ["tag1", "tag2"], 1)
        s.aggregate("value2")
        s.aggregate("value2")
        self.assertEqual(s.data, {"value1", "value2"})
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, ["tag1", "tag2"])
        self.assertEqual(s.rate, 1)
        self.assertEqual(s.timestamp, 0)

if __name__ == '__main__':
    unittest.main()
