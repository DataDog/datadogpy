# coding: utf8

# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import unittest
import os
import sys
import tempfile

from datadog.dogshell.wrap import OutputReader, build_event_body, parse_options
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
