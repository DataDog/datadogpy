# coding: utf8

# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import unittest
import mock
import os
import tempfile

from datadog.dogshell.wrap import OutputReader, build_event_body, parse_options, execute, Timeout, poll_proc
from datadog.util.compat import is_p3k


HERE = os.path.dirname(os.path.abspath(__file__))


class TestDogwrap(unittest.TestCase):
    def test_output_reader(self):
        with open(os.path.join(HERE, "fixtures", "proc_out.txt"), 'rb') as cmd_out:
            content = cmd_out.read()

        with tempfile.TemporaryFile() as fwd_out:
            reader = OutputReader(open(os.path.join(HERE, "fixtures", "proc_out.txt"), 'rb'), fwd_out)
            reader.start()
            reader.join()
            self.assertIsInstance(reader.content, bytes)
            self.assertEqual(reader.content, content)
            fwd_out.seek(0, 0)
            self.assertEqual(reader.content, fwd_out.read())

    def test_build_event_body(self):
        # Only cmd is already unicode, the rest is decoded in the function
        cmd = u"yö dudes"
        returncode = 0
        stdout = b"s\xc3\xb9p\xaa"
        stderr = b"d\xc3\xa0wg\xaa"
        notifications = b"@m\xc3\xa9\xaa"
        expected_body = u"%%%\n" \
            u"**>>>> CMD <<<<**\n```\nyö dudes \n```\n" \
            u"**>>>> EXIT CODE <<<<**\n\n 0\n\n\n" \
            u"**>>>> STDOUT <<<<**\n```\nsùp\ufffd \n```\n" \
            u"**>>>> STDERR <<<<**\n```\ndàwg\ufffd \n```\n" \
            u"**>>>> NOTIFICATIONS <<<<**\n\n @mé\ufffd\n" \
            u"%%%\n"

        event_body = build_event_body(cmd, returncode, stdout, stderr, notifications)
        self.assertEqual(expected_body, event_body)

        # notifications can be unicode already in py3, make sure we don't try decoding
        notifications = notifications.decode("utf-8", "replace")
        event_body = build_event_body(cmd, returncode, stdout, stderr, notifications)
        self.assertEqual(expected_body, event_body)

    def test_parse_options(self):
        options, cmd = parse_options([])
        self.assertEqual(cmd, '')

        # The output of parse_args is already unicode in python 3, so don't encode the input
        if is_p3k():
            arg = u'helløøééé'
        else:
            arg = u'helløøééé'.encode('utf-8')

        options, cmd = parse_options(['-n', 'name', '-k', 'key', '-m', 'all', '-p', 'low', '-t', '123',
                                      '--sigterm_timeout', '456', '--sigkill_timeout', '789',
                                      '--proc_poll_interval', '1.5', '--notify_success', 'success',
                                      '--notify_error', 'error', '-b', '--tags', 'k1:v1,k2:v2',
                                      'echo', arg])
        self.assertEqual(cmd, u'echo helløøééé')
        self.assertEqual(options.name, 'name')
        self.assertEqual(options.api_key, 'key')
        self.assertEqual(options.submit_mode, 'all')
        self.assertEqual(options.priority, 'low')
        self.assertEqual(options.timeout, 123)
        self.assertEqual(options.sigterm_timeout, 456)
        self.assertEqual(options.sigkill_timeout, 789)
        self.assertEqual(options.proc_poll_interval, 1.5)
        self.assertEqual(options.notify_success, 'success')
        self.assertEqual(options.notify_error, 'error')
        self.assertTrue(options.buffer_outs)
        self.assertEqual(options.tags, 'k1:v1,k2:v2')

        with self.assertRaises(SystemExit):
            parse_options(['-m', 'invalid'])

        with self.assertRaises(SystemExit):
            parse_options(['-p', 'invalid'])

        with self.assertRaises(SystemExit):
            parse_options(['-t', 'invalid'])

        with self.assertRaises(SystemExit):
            parse_options(['--sigterm_timeout', 'invalid'])

        with self.assertRaises(SystemExit):
            parse_options(['--sigkill_timeout', 'invalid'])

        with self.assertRaises(SystemExit):
            parse_options(['--proc_poll_interval', 'invalid'])

        with mock.patch.dict(os.environ, values={"DD_API_KEY": "the_key"}, clear=True):
            options, _ = parse_options([])
            self.assertEqual(options.api_key, "the_key")

    def test_poll_proc(self):
        mock_proc = mock.Mock()
        mock_proc.poll.side_effect = [None, 0]

        return_value = poll_proc(mock_proc, 0.1, 1)
        self.assertEqual(return_value, 0)
        self.assertEqual(mock_proc.poll.call_count, 2)

    def test_poll_timeout(self):
        mock_proc = mock.Mock()
        mock_proc.poll.side_effect = [None, None, None]

        with self.assertRaises(Timeout):
            poll_proc(mock_proc, 0.1, 0.2)

    @mock.patch('datadog.dogshell.wrap.poll_proc')
    @mock.patch('subprocess.Popen')
    def test_execute(self, mock_popen, mock_poll):
        mock_proc = mock.Mock()
        mock_proc.stdout.readline.side_effect = [b'out1\n', b'']
        mock_proc.stderr.readline.side_effect = [b'err1\n', b'']
        mock_popen.return_value = mock_proc
        mock_poll.return_value = 0

        return_code, stdout, stderr, duration = execute('foo', 10, 20, 30, 1, False)
        self.assertEqual(return_code, 0)
        self.assertEqual(stdout, b'out1\n')
        self.assertEqual(stderr, b'err1\n')

        mock_popen.assert_called_once()
        mock_poll.assert_called_once_with(mock_proc, 1, 10)
        mock_proc.terminate.assert_not_called()
        mock_proc.kill.assert_not_called()

    @mock.patch('datadog.dogshell.wrap.poll_proc')
    @mock.patch('subprocess.Popen')
    def test_execute_exit_code(self, mock_popen, mock_poll):
        mock_proc = mock.Mock()
        mock_proc.stdout.readline.side_effect = [b'out1\n', b'out2\n', b'']
        mock_proc.stderr.readline.side_effect = [b'err1\n', b'']
        mock_popen.return_value = mock_proc
        mock_poll.return_value = 14

        return_code, stdout, stderr, duration = execute('foo', 10, 20, 30, 1, False)
        self.assertEqual(return_code, 14)
        self.assertEqual(stdout, b'out1\nout2\n')
        self.assertEqual(stderr, b'err1\n')

        mock_popen.assert_called_once()
        mock_poll.assert_called_once_with(mock_proc, 1, 10)
        mock_proc.terminate.assert_not_called()
        mock_proc.kill.assert_not_called()

    @mock.patch('datadog.dogshell.wrap.poll_proc')
    @mock.patch('subprocess.Popen')
    def test_execute_cmd_timeout(self, mock_popen, mock_poll):
        mock_proc = mock.Mock()
        mock_proc.stdout.readline.side_effect = [b'out1\n', b'out2\n', b'']
        mock_proc.stderr.readline.side_effect = [b'err1\n', b'']
        mock_popen.return_value = mock_proc
        mock_poll.side_effect = [Timeout, 1]

        return_code, stdout, stderr, duration = execute('foo', 10, 20, 30, 1, False)
        self.assertEqual(return_code, Timeout)
        self.assertEqual(stdout, b'out1\nout2\n')
        self.assertEqual(stderr, b'err1\n')

        mock_popen.assert_called_once()
        mock_poll.assert_has_calls([
            mock.call(mock_proc, 1, 10),
            mock.call(mock_proc, 1, 20)
        ])
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_not_called()

    @mock.patch('datadog.dogshell.wrap.poll_proc')
    @mock.patch('subprocess.Popen')
    def test_execute_sigterm_timeout(self, mock_popen, mock_poll):
        mock_proc = mock.Mock()
        mock_proc.stdout.readline.side_effect = [b'out1\n', b'out2\n', b'']
        mock_proc.stderr.readline.side_effect = [b'err1\n', b'']
        mock_popen.return_value = mock_proc
        mock_poll.side_effect = [Timeout, Timeout, 2]

        return_code, stdout, stderr, duration = execute('foo', 10, 20, 30, 1, False)
        self.assertEqual(return_code, Timeout)
        self.assertEqual(stdout, b'out1\nout2\n')
        self.assertEqual(stderr, b'err1\n')

        mock_popen.assert_called_once()
        mock_poll.assert_has_calls([
            mock.call(mock_proc, 1, 10),
            mock.call(mock_proc, 1, 20),
            mock.call(mock_proc, 1, 30)
        ])
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @mock.patch('datadog.dogshell.wrap.poll_proc')
    @mock.patch('subprocess.Popen')
    def test_execute_sigkill_timeout(self, mock_popen, mock_poll):
        mock_proc = mock.Mock()
        mock_proc.stdout.readline.side_effect = [b'out1\n', b'out2\n', b'']
        mock_proc.stderr.readline.side_effect = [b'err1\n', b'']
        mock_popen.return_value = mock_proc
        mock_poll.side_effect = [Timeout, Timeout, Timeout]

        return_code, stdout, stderr, duration = execute('foo', 10, 20, 30, 1, False)
        self.assertEqual(return_code, Timeout)
        self.assertEqual(stdout, b'out1\nout2\n')
        self.assertEqual(stderr, b'err1\n')

        mock_popen.assert_called_once()
        mock_poll.assert_has_calls([
            mock.call(mock_proc, 1, 10),
            mock.call(mock_proc, 1, 20),
            mock.call(mock_proc, 1, 30)
        ])
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @mock.patch('datadog.dogshell.wrap.poll_proc')
    @mock.patch('subprocess.Popen')
    def test_execute_oserror(self, mock_popen, mock_poll):
        mock_proc = mock.Mock()
        mock_proc.stdout.readline.side_effect = [b'out1\n', b'out2\n', b'']
        mock_proc.stderr.readline.side_effect = [b'err1\n', b'']
        mock_popen.return_value = mock_proc
        mock_poll.side_effect = [Timeout, Timeout]
        mock_proc.kill.side_effect = OSError(3, 'No process')
        return_code, stdout, stderr, duration = execute('foo', 10, 20, 30, 1, False)
        self.assertEqual(return_code, Timeout)
        self.assertEqual(stdout, b'out1\nout2\n')
        self.assertEqual(stderr, b'err1\n')

        mock_popen.assert_called_once()
        mock_poll.assert_has_calls([
            mock.call(mock_proc, 1, 10),
            mock.call(mock_proc, 1, 20)
        ])
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @mock.patch('subprocess.Popen')
    def test_execute_popen_fail(self, mock_popen):
        mock_popen.side_effect = ValueError('Bad things')

        with self.assertRaises(ValueError):
            execute('sleep 1', 10, 1, 1, 1, False)
