# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Tests for dogwrap start signals (dogwrap.started metric and start event).
"""

import unittest

import mock

from datadog.dogshell.wrap import main


class TestDogwrapStartSignals(unittest.TestCase):
    @mock.patch("sys.exit")
    @mock.patch("datadog.dogshell.wrap.execute", return_value=(0, b"", b"", 1.0))
    @mock.patch("datadog.dogshell.wrap.api.Event.create")
    @mock.patch("datadog.dogshell.wrap.api.Metric.send")
    @mock.patch("datadog.dogshell.wrap.initialize")
    @mock.patch("datadog.dogshell.wrap.parse_options")
    def test_start_metric_fires_before_duration_metric(
        self,
        mock_parse,
        mock_init,
        mock_metric_send,
        mock_event_create,
        mock_execute,
        mock_exit,
    ):
        """Start metric fires before execute when --send_metric is set."""
        opts = mock.Mock()
        opts.name = "test-job"
        opts.api_key = "fake-key"
        opts.site = "datadoghq.com"
        opts.submit_mode = "all"
        opts.send_metric = True
        opts.tags = ""
        opts.timeout = 60
        opts.sigterm_timeout = 120
        opts.sigkill_timeout = 60
        opts.proc_poll_interval = 0.5
        opts.buffer_outs = False
        opts.priority = None
        opts.warning_codes = None
        opts.notify_success = ""
        opts.notify_error = ""
        opts.notify_warning = ""
        mock_parse.return_value = (opts, "echo hi")

        main()

        # Should have exactly 2 Metric.send calls: started then duration
        self.assertEqual(mock_metric_send.call_count, 2)
        first_call = mock_metric_send.call_args_list[0]
        second_call = mock_metric_send.call_args_list[1]
        self.assertEqual(first_call[1]["metric"], "dogwrap.started")
        self.assertEqual(second_call[1]["metric"], "dogwrap.duration")

    @mock.patch("sys.exit")
    @mock.patch("datadog.dogshell.wrap.execute", return_value=(0, b"", b"", 1.0))
    @mock.patch("datadog.dogshell.wrap.api.Event.create")
    @mock.patch("datadog.dogshell.wrap.api.Metric.send")
    @mock.patch("datadog.dogshell.wrap.initialize")
    @mock.patch("datadog.dogshell.wrap.parse_options")
    def test_no_start_metric_without_flag(
        self,
        mock_parse,
        mock_init,
        mock_metric_send,
        mock_event_create,
        mock_execute,
        mock_exit,
    ):
        """Start metric does NOT fire when --send_metric is not set."""
        opts = mock.Mock()
        opts.name = "test-job"
        opts.api_key = "fake-key"
        opts.site = "datadoghq.com"
        opts.submit_mode = "errors"
        opts.send_metric = False
        opts.tags = ""
        opts.timeout = 60
        opts.sigterm_timeout = 120
        opts.sigkill_timeout = 60
        opts.proc_poll_interval = 0.5
        opts.buffer_outs = False
        opts.priority = None
        opts.warning_codes = None
        opts.notify_success = ""
        opts.notify_error = ""
        opts.notify_warning = ""
        mock_parse.return_value = (opts, "echo hi")

        main()

        # Success + errors mode = no end event/metric either, so 0 calls total
        mock_metric_send.assert_not_called()

    @mock.patch("sys.exit")
    @mock.patch("datadog.dogshell.wrap.execute", return_value=(0, b"", b"", 1.0))
    @mock.patch("datadog.dogshell.wrap.api.Metric.send")
    @mock.patch("datadog.dogshell.wrap.api.Event.create")
    @mock.patch("datadog.dogshell.wrap.initialize")
    @mock.patch("datadog.dogshell.wrap.parse_options")
    def test_start_event_fires_with_submit_mode_all(
        self,
        mock_parse,
        mock_init,
        mock_event_create,
        mock_metric_send,
        mock_execute,
        mock_exit,
    ):
        """Start event fires when --submit_mode all."""
        opts = mock.Mock()
        opts.name = "test-job"
        opts.api_key = "fake-key"
        opts.site = "datadoghq.com"
        opts.submit_mode = "all"
        opts.send_metric = False
        opts.tags = ""
        opts.timeout = 60
        opts.sigterm_timeout = 120
        opts.sigkill_timeout = 60
        opts.proc_poll_interval = 0.5
        opts.buffer_outs = False
        opts.priority = None
        opts.warning_codes = None
        opts.notify_success = ""
        opts.notify_error = ""
        opts.notify_warning = ""
        mock_parse.return_value = (opts, "echo hi")

        main()

        # Should have exactly 2 Event.create calls: start event then end event
        self.assertEqual(mock_event_create.call_count, 2)
        first_call = mock_event_create.call_args_list[0]
        self.assertEqual(first_call[1]["alert_type"], "info")
        self.assertIn("started", first_call[1]["title"])

        # Second call is the end/success event
        second_call = mock_event_create.call_args_list[1]
        self.assertIn("succeeded", second_call[1]["title"])

    @mock.patch("sys.exit")
    @mock.patch("datadog.dogshell.wrap.execute", return_value=(0, b"", b"", 1.0))
    @mock.patch("datadog.dogshell.wrap.api.Metric.send")
    @mock.patch("datadog.dogshell.wrap.api.Event.create")
    @mock.patch("datadog.dogshell.wrap.initialize")
    @mock.patch("datadog.dogshell.wrap.parse_options")
    def test_no_start_event_with_submit_mode_errors(
        self,
        mock_parse,
        mock_init,
        mock_event_create,
        mock_metric_send,
        mock_execute,
        mock_exit,
    ):
        """Start event does NOT fire when --submit_mode errors."""
        opts = mock.Mock()
        opts.name = "test-job"
        opts.api_key = "fake-key"
        opts.site = "datadoghq.com"
        opts.submit_mode = "errors"
        opts.send_metric = False
        opts.tags = ""
        opts.timeout = 60
        opts.sigterm_timeout = 120
        opts.sigkill_timeout = 60
        opts.proc_poll_interval = 0.5
        opts.buffer_outs = False
        opts.priority = None
        opts.warning_codes = None
        opts.notify_success = ""
        opts.notify_error = ""
        opts.notify_warning = ""
        mock_parse.return_value = (opts, "echo hi")

        main()

        # Success + errors mode = no events at all
        mock_event_create.assert_not_called()

    @mock.patch("sys.exit")
    @mock.patch("datadog.dogshell.wrap.execute", return_value=(0, b"", b"", 1.0))
    @mock.patch("datadog.dogshell.wrap.api.Event.create")
    @mock.patch("datadog.dogshell.wrap.api.Metric.send")
    @mock.patch("datadog.dogshell.wrap.initialize")
    @mock.patch("datadog.dogshell.wrap.parse_options")
    def test_start_metric_tags_include_event_name(
        self,
        mock_parse,
        mock_init,
        mock_metric_send,
        mock_event_create,
        mock_execute,
        mock_exit,
    ):
        """Start metric tags include event_name tag and custom tags."""
        opts = mock.Mock()
        opts.name = "test-job"
        opts.api_key = "fake-key"
        opts.site = "datadoghq.com"
        opts.submit_mode = "errors"
        opts.send_metric = True
        opts.tags = "env:prod"
        opts.timeout = 60
        opts.sigterm_timeout = 120
        opts.sigkill_timeout = 60
        opts.proc_poll_interval = 0.5
        opts.buffer_outs = False
        opts.priority = None
        opts.warning_codes = None
        opts.notify_success = ""
        opts.notify_error = ""
        opts.notify_warning = ""
        mock_parse.return_value = (opts, "echo hi")

        main()

        # Find the dogwrap.started call
        started_call = None
        for call in mock_metric_send.call_args_list:
            if call[1].get("metric") == "dogwrap.started":
                started_call = call
                break

        self.assertIsNotNone(started_call, "dogwrap.started metric was not sent")
        sent_tags = started_call[1]["tags"]
        self.assertIn("env:prod", sent_tags)
        self.assertIn("event_name:test-job", sent_tags)

    @mock.patch("sys.exit")
    @mock.patch("datadog.dogshell.wrap.execute", return_value=(0, b"", b"", 1.0))
    @mock.patch("datadog.dogshell.wrap.api.Event.create")
    @mock.patch("datadog.dogshell.wrap.api.Metric.send")
    @mock.patch("datadog.dogshell.wrap.initialize")
    @mock.patch("datadog.dogshell.wrap.parse_options")
    def test_start_signal_failure_does_not_block_execute(
        self,
        mock_parse,
        mock_init,
        mock_metric_send,
        mock_event_create,
        mock_execute,
        mock_exit,
    ):
        """API failure on start signals must not prevent command execution."""
        opts = mock.Mock()
        opts.name = "test-job"
        opts.api_key = "fake-key"
        opts.site = "datadoghq.com"
        opts.submit_mode = "all"
        opts.send_metric = True
        opts.tags = ""
        opts.timeout = 60
        opts.sigterm_timeout = 120
        opts.sigkill_timeout = 60
        opts.proc_poll_interval = 0.5
        opts.buffer_outs = False
        opts.priority = None
        opts.warning_codes = None
        opts.notify_success = ""
        opts.notify_error = ""
        opts.notify_warning = ""
        mock_parse.return_value = (opts, "echo hi")

        # Simulate API failure on the start metric call
        mock_metric_send.side_effect = [Exception("API timeout"), mock.DEFAULT]

        main()

        # execute() must still have been called despite the API failure
        mock_execute.assert_called_once()

    @mock.patch("sys.exit")
    @mock.patch("datadog.dogshell.wrap.execute", return_value=(0, b"", b"", 1.0))
    @mock.patch("datadog.dogshell.wrap.api.Metric.send")
    @mock.patch("datadog.dogshell.wrap.api.Event.create")
    @mock.patch("datadog.dogshell.wrap.initialize")
    @mock.patch("datadog.dogshell.wrap.parse_options")
    def test_start_event_failure_does_not_block_execute(
        self,
        mock_parse,
        mock_init,
        mock_event_create,
        mock_metric_send,
        mock_execute,
        mock_exit,
    ):
        """API failure on start event must not prevent command execution."""
        opts = mock.Mock()
        opts.name = "test-job"
        opts.api_key = "fake-key"
        opts.site = "datadoghq.com"
        opts.submit_mode = "all"
        opts.send_metric = False
        opts.tags = ""
        opts.timeout = 60
        opts.sigterm_timeout = 120
        opts.sigkill_timeout = 60
        opts.proc_poll_interval = 0.5
        opts.buffer_outs = False
        opts.priority = None
        opts.warning_codes = None
        opts.notify_success = ""
        opts.notify_error = ""
        opts.notify_warning = ""
        mock_parse.return_value = (opts, "echo hi")

        # Simulate API failure on the start event call
        mock_event_create.side_effect = [Exception("Connection refused"), mock.DEFAULT]

        main()

        # execute() must still have been called despite the API failure
        mock_execute.assert_called_once()
