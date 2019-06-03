# coding: utf8

import unittest
import os
import tempfile

from datadog.dogshell.wrap import OutputReader, build_event_body

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
