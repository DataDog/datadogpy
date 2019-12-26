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

from argparse import ArgumentTypeError
from freezegun import freeze_time
import datetime
import unittest

from datadog.util.cli import (
    comma_list,
    comma_set,
    comma_list_or_empty,
    list_of_ints,
    list_of_ints_and_strs,
    set_of_ints,
    DateParsingError,
    _midnight,
    parse_date_as_epoch_timestamp,
    parse_date,
)
from datadog.util.compat import is_pypy
from datadog.util.format import force_to_epoch_seconds


class TestCLI(unittest.TestCase):
    def test_comma_list(self):
        invalid_cases = [None, ""]
        for invalid_case in invalid_cases:
            with self.assertRaises(ArgumentTypeError):
                comma_list(invalid_case)

        valid_cases = (
            (["foo"], "foo", None),
            (["foo", "bar"], "foo,bar", None),
            ([1], "1", int),
            ([1, 2], "1,2", int),
        )
        for expected, list_str, item_func in valid_cases:
            actual = comma_list(list_str, item_func)
            self.assertListEqual(expected, actual)

    def test_comma_set(self):
        invalid_cases = [None, ""]
        for invalid_case in invalid_cases:
            with self.assertRaises(ArgumentTypeError):
                comma_set(invalid_case)

        valid_cases = (
            ({"foo"}, "foo", None),
            ({"foo", "bar"}, "foo,bar", None),
            ({1}, "1", int),
            ({1}, "1,1,1", int),
            ({1, 2}, "1,2,1", int),
        )
        for expected, list_str, item_func in valid_cases:
            actual = comma_set(list_str, item_func)
            self.assertSetEqual(expected, actual)

    def test_comma_list_or_empty(self):
        valid_cases = (
            ([], None, None),
            ([], "", None),
            (["foo"], "foo", None),
            (["foo", "bar"], "foo,bar", None),
        )
        for expected, list_str, item_func in valid_cases:
            actual = comma_list_or_empty(list_str)
            self.assertListEqual(expected, actual)

    def test_list_of_ints(self):
        invalid_cases = [None, "", "foo", '["foo"]']
        for invalid_case in invalid_cases:
            with self.assertRaises(ArgumentTypeError):
                list_of_ints(invalid_case)

        valid_cases = (([1], "1"), ([1, 2], "1,2"), ([1], "[1]"), ([1, 2], "[1,2]"))
        for expected, list_str in valid_cases:
            actual = list_of_ints(list_str)
            self.assertListEqual(expected, actual)

    def test_list_of_ints_and_strs(self):
        invalid_cases = [None, ""]
        for invalid_case in invalid_cases:
            with self.assertRaises(ArgumentTypeError):
                list_of_ints_and_strs(invalid_case)

        valid_cases = (
            (["foo"], "foo"),
            (["foo", "bar"], "foo,bar"),
            ([1], "1"),
            ([1, 2], "1,2"),
            (["foo", 2], "foo,2"),
        )
        for expected, list_str in valid_cases:
            actual = list_of_ints_and_strs(list_str)
            self.assertListEqual(expected, actual)

    def test_set_of_ints(self):
        invalid_cases = [None, "", "foo", '["foo"]']
        for invalid_case in invalid_cases:
            with self.assertRaises(ArgumentTypeError):
                set_of_ints(invalid_case)

        valid_cases = (
            ({1}, "1"),
            ({1, 2}, "1,2"),
            ({1}, "[1]"),
            ({1}, "[1,1,1]"),
            ({1, 2}, "[1,2,1]"),
        )
        for expected, list_str in valid_cases:
            actual = set_of_ints(list_str)
            self.assertSetEqual(expected, actual)

    @freeze_time("2019-10-23 04:44:32", tz_offset=0)
    def test_midnight(self):
        d = _midnight()
        self.assertEqual(2019, d.year)
        self.assertEqual(10, d.month)
        self.assertEqual(23, d.day)
        self.assertEqual(0, d.hour)
        self.assertEqual(0, d.minute)
        self.assertEqual(0, d.second)
        self.assertEqual(0, d.microsecond)

    @freeze_time("2019-10-23 04:44:32", tz_offset=0)
    def test_parse_date(self):
        test_date = datetime.datetime(2019, 10, 23, 4, 44, 32, 0)
        cases = [
            (test_date, test_date),  # already an instance, return
            ("today", datetime.datetime(2019, 10, 23, 0, 0, 0)),
            ("yesterday", datetime.datetime(2019, 10, 22, 0, 0, 0)),
            ("tomorrow", datetime.datetime(2019, 10, 24, 0, 0, 0)),
            ("2 days ago", datetime.datetime(2019, 10, 21, 4, 44, 32)),
            ("2d ago", datetime.datetime(2019, 10, 21, 4, 44, 32)),
            ("2 days ahead", datetime.datetime(2019, 10, 25, 4, 44, 32)),
            ("2d ahead", datetime.datetime(2019, 10, 25, 4, 44, 32)),
            ("now", datetime.datetime(2019, 10, 23, 4, 44, 32)),
            ("2019-10-23 04:44:32.000000", test_date),
            ("2019-10-23T04:44:32.000000", test_date),
            ("2019-10-23 04:44:32", test_date),
            ("2019-10-23T04:44:32", test_date),
            ("2019-10-23 04:44", datetime.datetime(2019, 10, 23, 4, 44, 0, 0)),
            ("2019-10-23-04", datetime.datetime(2019, 10, 23, 4, 0, 0, 0)),
            ("2019-10-23", datetime.datetime(2019, 10, 23, 0, 0, 0, 0)),
            ("2019-10", datetime.datetime(2019, 10, 1, 0, 0, 0, 0)),
            ("2019", datetime.datetime(2019, 1, 1, 0, 0, 0, 0)),
            ("2019-10", datetime.datetime(2019, 10, 1, 0, 0, 0, 0)),
            ("1571805872", test_date),  # seconds
        ]
        if not is_pypy():
            cases.append(
                ("1571805872000", test_date)
            )  # millis, pypy does not work (known)

        for i, (date_str, expected) in enumerate(cases):
            actual = parse_date(date_str)
            self.assertEqual(
                expected,
                actual,
                "case {}: failed, date_str={} expected={} actual={}".format(
                    i, date_str, expected, actual
                ),
            )

        # test invalid case
        with self.assertRaises(DateParsingError):
            parse_date("foo")

    @freeze_time("2019-10-23 04:44:32", tz_offset=0)
    def test_parse_date_as_epoch_timestamp(self):
        # this applies the same rules but always returns epoch seconds
        test_date = datetime.datetime(2019, 10, 23, 4, 44, 32, 0)
        cases = [
            (test_date, test_date),  # already an instance, return
            ("today", datetime.datetime(2019, 10, 23, 0, 0, 0)),
            ("yesterday", datetime.datetime(2019, 10, 22, 0, 0, 0)),
            ("tomorrow", datetime.datetime(2019, 10, 24, 0, 0, 0)),
            ("2 days ago", datetime.datetime(2019, 10, 21, 4, 44, 32)),
            ("2d ago", datetime.datetime(2019, 10, 21, 4, 44, 32)),
            ("2 days ahead", datetime.datetime(2019, 10, 25, 4, 44, 32)),
            ("2d ahead", datetime.datetime(2019, 10, 25, 4, 44, 32)),
            ("now", datetime.datetime(2019, 10, 23, 4, 44, 32)),
            ("2019-10-23 04:44:32.000000", test_date),
            ("2019-10-23T04:44:32.000000", test_date),
            ("2019-10-23 04:44:32", test_date),
            ("2019-10-23T04:44:32", test_date),
            ("2019-10-23 04:44", datetime.datetime(2019, 10, 23, 4, 44, 0, 0)),
            ("2019-10-23-04", datetime.datetime(2019, 10, 23, 4, 0, 0, 0)),
            ("2019-10-23", datetime.datetime(2019, 10, 23, 0, 0, 0, 0)),
            ("2019-10", datetime.datetime(2019, 10, 1, 0, 0, 0, 0)),
            ("2019", datetime.datetime(2019, 1, 1, 0, 0, 0, 0)),
            ("2019-10", datetime.datetime(2019, 10, 1, 0, 0, 0, 0)),
            ("1571805872", test_date),  # seconds
        ]
        if not is_pypy():
            cases.append(
                ("1571805872000", test_date)
            )  # millis, pypy does not work (known)

        for i, (date_str, expected) in enumerate(cases):
            actual_timestamp = parse_date_as_epoch_timestamp(date_str)
            expected_timestamp = force_to_epoch_seconds(expected)
            self.assertEqual(
                expected_timestamp,
                actual_timestamp,
                "case {}: failed, date_str={} expected={} actual={}".format(
                    i, date_str, expected_timestamp, actual_timestamp
                ),
            )

        # test invalid case
        with self.assertRaises(DateParsingError):
            parse_date_as_epoch_timestamp("foo")
