import unittest

from datadog.dogstatsd.metrics import CountMetric, GaugeMetric, SetMetric

class TestMetrics(unittest.TestCase):
    # TODO: potentially test flush_unsafe and locks
    def test_new_count_metric(self):
        c = CountMetric("test", 21, ["tag1", "tag2"], 1)
        self.assertEqual(c.value, 21)
        self.assertEqual(c.name, "test")
        self.assertEqual(c.tags, ["tag1", "tag2"])
        self.assertEqual(c.rate, 1.0)

    def test_count_metric_aggregate(self):
        c = CountMetric("test", 10, ["tag1", "tag2"], 1)
        c.aggregate(20)
        self.assertEqual(c.value, 30)
        self.assertEqual(c.name, "test")
        self.assertEqual(c.tags, ["tag1", "tag2"])
        self.assertEqual(c.rate, 1.0)

    # def test_flush_unsafe_count_metric(self):
    #     c = CountMetric("test", 10, ["tag1", "tag2"], 1)
    #     m = c.flush_unsafe()
    #     self.assertEqual(m['metric_type'], 'count')
    #     self.assertEqual(m['ivalue'], 10)
    #     self.assertEqual(m['name'], "test")
    #     self.assertEqual(m['tags'], ["tag1", "tag2"])
    #     self.assertEqual(m['rate'], 1)

    #     c.aggregate(20)
    #     m = c.flush_unsafe()
    #     self.assertEqual(m['metric_type'], 'count')
    #     self.assertEqual(m['ivalue'], 30)
    #     self.assertEqual(m['name'], "test")
    #     self.assertEqual(m['tags'], ["tag1", "tag2"])
    #     self.assertEqual(m['rate'], 1.0)

    def test_new_gauge_metric(self):
        g = GaugeMetric("test", 10, ["tag1", "tag2"], 1)
        self.assertEqual(g.value, 10)
        self.assertEqual(g.name, "test")
        self.assertEqual(g.tags, ["tag1", "tag2"])
        self.assertEqual(g.rate, 1)

    def test_gauge_metric_aggregate(self):
        g = GaugeMetric("test", 10, ["tag1", "tag2"], 1)
        g.aggregate(20)
        self.assertEqual(g.value, 20)
        self.assertEqual(g.name, "test")
        self.assertEqual(g.tags, ["tag1", "tag2"])
        self.assertEqual(g.rate, 1.0)

    # def test_flush_unsafe_gauge_metric(self):
    #     g = GaugeMetric("test", 10, ["tag1", "tag2"], 1)
    #     m = g.flush_unsafe()
    #     self.assertEqual(m['metric_type'], 'gauge')
    #     self.assertEqual(m['fvalue'], 10)
    #     self.assertEqual(m['name'], "test")
    #     self.assertEqual(m['tags'], ["tag1", "tag2"])
    #     self.assertEqual(m['rate'], 1)

    #     g.aggregate(20)
    #     m = g.flush_unsafe()
    #     self.assertEqual(m['metric_type'], 'gauge')
    #     self.assertEqual(m['fvalue'], 20)
    #     self.assertEqual(m['name'], "test")
    #     self.assertEqual(m['tags'], ["tag1", "tag2"])
    #     self.assertEqual(m['rate'], 1)

    def test_new_set_metric(self):
        s = SetMetric("test", "value1", ["tag1", "tag2"], 1)
        self.assertEqual(s.data, {"value1"})
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, ["tag1", "tag2"])
        self.assertEqual(s.rate, 1)

    def test_set_metric_aggregate(self):
        s = SetMetric("test", "value1", ["tag1", "tag2"], 1)
        s.aggregate("value2")
        s.aggregate("value2")
        self.assertEqual(s.data, {"value1", "value2"})
        self.assertEqual(s.name, "test")
        self.assertEqual(s.tags, ["tag1", "tag2"])
        self.assertEqual(s.rate, 1)

    # def test_flush_unsafe_set_metric(self):
    #     s = SetMetric("test", "value1", ["tag1", "tag2"], 1)
    #     m = s.flush_unsafe()

    #     self.assertEqual(len(m), 1)
    #     self.assertEqual(m[0]['metric_type'], 'set')
    #     self.assertEqual(m[0]['svalue'], "value1")
    #     self.assertEqual(m[0]['name'], "test")
    #     self.assertEqual(m[0]['tags'], ["tag1", "tag2"])
    #     self.assertEqual(m[0]['rate'], 1)

    #     s.aggregate("value1")
    #     s.aggregate("value2")
    #     m = s.flush_unsafe()

    #     m = sorted(m, key=lambda x: x['svalue'])

    #     self.assertEqual(len(m), 2)
    #     self.assertEqual(m[0]['metric_type'], 'set')
    #     self.assertEqual(m[0]['svalue'], "value1")
    #     self.assertEqual(m[0]['name'], "test")
    #     self.assertEqual(m[0]['tags'], ["tag1", "tag2"])
    #     self.assertEqual(m[0]['rate'], 1)
    #     self.assertEqual(m[1]['metric_type'], 'set')
    #     self.assertEqual(m[1]['svalue'], "value2")
    #     self.assertEqual(m[1]['name'], "test")
    #     self.assertEqual(m[1]['tags'], ["tag1", "tag2"])
    #     self.assertEqual(m[1]['rate'], 1)

if __name__ == '__main__':
    unittest.main()
