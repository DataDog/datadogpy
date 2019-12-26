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

from datetime import datetime, timedelta
from argparse import ArgumentTypeError
import json
import re
from datadog.util.format import force_to_epoch_seconds
import time


def comma_list(list_str, item_func=None):
    if not list_str:
        raise ArgumentTypeError("Invalid comma list")
    item_func = item_func or (lambda i: i)
    return [item_func(i.strip()) for i in list_str.split(",") if i.strip()]


def comma_set(list_str, item_func=None):
    return set(comma_list(list_str, item_func=item_func))


def comma_list_or_empty(list_str):
    if not list_str:
        return []
    else:
        return comma_list(list_str)


def list_of_ints(int_csv):
    if not int_csv:
        raise ArgumentTypeError("Invalid list of ints")
    try:
        # Try as a [1, 2, 3] list
        j = json.loads(int_csv)
        if isinstance(j, (list, set)):
            j = [int(i) for i in j]
            return j
    except Exception:
        pass

    try:
        return [int(i.strip()) for i in int_csv.strip().split(",")]
    except Exception:
        raise ArgumentTypeError("Invalid list of ints: {0}".format(int_csv))


def list_of_ints_and_strs(csv):
    def int_or_str(item):
        try:
            return int(item)
        except ValueError:
            return item

    return comma_list(csv, int_or_str)


def set_of_ints(int_csv):
    return set(list_of_ints(int_csv))


class DateParsingError(Exception):
    """Thrown if parse_date exhausts all possible parsings of a string"""


_date_fieldre = re.compile(r"(\d+)\s?(\w+) (ago|ahead)")


def _midnight():
    """ Truncate a date to midnight. Default to UTC midnight today."""
    return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def parse_date_as_epoch_timestamp(date_str):
    return parse_date(date_str, to_epoch_ts=True)


def _parse_date_noop_formatter(d):
    """ NOOP - only here for pylint """
    return d


def parse_date(date_str, to_epoch_ts=False):
    formatter = _parse_date_noop_formatter
    if to_epoch_ts:
        formatter = force_to_epoch_seconds

    if isinstance(date_str, datetime):
        return formatter(date_str)
    elif isinstance(date_str, time.struct_time):
        return formatter(datetime.fromtimestamp(time.mktime(date_str)))

    # Parse relative dates.
    if date_str == "today":
        return formatter(_midnight())
    elif date_str == "yesterday":
        return formatter(_midnight() - timedelta(days=1))
    elif date_str == "tomorrow":
        return formatter(_midnight() + timedelta(days=1))
    elif date_str.endswith(("ago", "ahead")):
        m = _date_fieldre.match(date_str)
        if m:
            fields = m.groups()
        else:
            fields = date_str.split(" ")[1:]
        num = int(fields[0])
        short_unit = fields[1]
        time_direction = {"ago": -1, "ahead": 1}[fields[2]]
        assert short_unit, short_unit
        units = ["weeks", "days", "hours", "minutes", "seconds"]
        # translate 'h' -> 'hours'
        short_units = dict([(u[:1], u) for u in units])
        unit = short_units.get(short_unit, short_unit)
        # translate 'hour' -> 'hours'
        if unit[-1] != "s":
            unit += "s"  # tolerate 1 hour
        assert unit in units, "'%s' not in %s" % (unit, units)
        return formatter(datetime.utcnow() + time_direction * timedelta(**{unit: num}))
    elif date_str == "now":
        return formatter(datetime.utcnow())

    def _from_epoch_timestamp(seconds):
        print("_from_epoch_timestamp({})".format(seconds))
        return datetime.utcfromtimestamp(float(seconds))

    def _from_epoch_ms_timestamp(millis):
        print("_from_epoch_ms_timestamp({})".format(millis))
        in_sec = float(millis) / 1000.0
        print("_from_epoch_ms_timestamp({}) -> {}".format(millis, in_sec))
        return _from_epoch_timestamp(in_sec)

    # Or parse date formats (most specific to least specific)
    parse_funcs = [
        lambda d: datetime.strptime(d, "%Y-%m-%d %H:%M:%S.%f"),
        lambda d: datetime.strptime(d, "%Y-%m-%d %H:%M:%S"),
        lambda d: datetime.strptime(d, "%Y-%m-%dT%H:%M:%S.%f"),
        lambda d: datetime.strptime(d, "%Y-%m-%dT%H:%M:%S"),
        lambda d: datetime.strptime(d, "%Y-%m-%d %H:%M"),
        lambda d: datetime.strptime(d, "%Y-%m-%d-%H"),
        lambda d: datetime.strptime(d, "%Y-%m-%d"),
        lambda d: datetime.strptime(d, "%Y-%m"),
        lambda d: datetime.strptime(d, "%Y"),
        _from_epoch_timestamp,  # an epoch in seconds
        _from_epoch_ms_timestamp,  # an epoch in milliseconds
    ]

    for parse_func in parse_funcs:
        try:
            return formatter(parse_func(date_str))
        except Exception:
            pass
    raise DateParsingError(u"Could not parse {0} as date".format(date_str))
