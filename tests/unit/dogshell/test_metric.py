# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Tests for the `metric post` dogshell command.
"""

import argparse
import unittest

import mock

from datadog import api
from datadog.dogshell.metric import MetricClient


def parse_args(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode")
    MetricClient.setup_parser(subparsers)
    args = parser.parse_args(argv)
    args.timeout = 10
    return args


class TestMetricPost(unittest.TestCase):
    def setUp(self):
        for patcher in (
            mock.patch.object(api, "_timeout", api._timeout),
            mock.patch("datadog.api.Metric.send", return_value={"status": "ok"}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def post(self, *options):
        args = parse_args(["metric", "post", "my.metric", "1"] + list(options))
        with mock.patch("datadog.dogshell.metric.report_warnings") as report_warnings:
            args.func(args)
        sent_type = api.Metric.send.call_args[1]["metric_type"]
        warnings = report_warnings.call_args[0][0]["warnings"]
        return sent_type, warnings

    def test_supported_types_are_sent_unchanged(self):
        for metric_type in ("gauge", "count", "rate", ""):
            self.assertEqual(self.post("--type", metric_type), (metric_type, []))
        self.assertEqual(self.post(), (None, []))

    def test_counter_is_sent_as_count(self):
        sent_type, warnings = self.post("--type", "counter")
        self.assertEqual(sent_type, "count")
        self.assertEqual(len(warnings), 1)
        self.assertIn("--type count", warnings[0])

    def test_unknown_type_is_rejected(self):
        with mock.patch("sys.stderr"):
            with self.assertRaises(SystemExit) as cm:
                parse_args(["metric", "post", "my.metric", "1", "--type", "foo"])
        self.assertEqual(cm.exception.code, 2)
