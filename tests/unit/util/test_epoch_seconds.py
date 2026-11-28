# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import datetime

import mock
import pytest
from dateutil.tz import tzoffset

from datadog import api
from datadog.api.resources import ActionAPIResource
from datadog.util.cli import parse_date_as_epoch_timestamp
from datadog.util.format import force_to_epoch_seconds


@pytest.mark.parametrize("offset", [-43200, -19800, 0, 19800, 50400])
def test_epoch_seconds_respects_timezone_offset(offset):
    value = datetime.datetime(2024, 1, 1, tzinfo=tzoffset(None, offset))
    assert force_to_epoch_seconds(value) == 1704067200 - offset


@pytest.mark.parametrize("microsecond", [0, 999999])
def test_same_instant_has_same_epoch_seconds(microsecond):
    utc = datetime.datetime(2024, 1, 1, microsecond=microsecond, tzinfo=tzoffset(None, 0))
    india = datetime.datetime(2024, 1, 1, 5, 30, microsecond=microsecond, tzinfo=tzoffset(None, 19800))
    assert force_to_epoch_seconds(india) == force_to_epoch_seconds(utc) == 1704067200


@pytest.mark.parametrize("value", [
    datetime.datetime(1970, 1, 1, 1, tzinfo=tzoffset(None, 3600)),
    datetime.datetime(1969, 12, 31, 23, tzinfo=tzoffset(None, -3600)),
])
def test_offset_datetime_at_epoch_boundary(value):
    assert force_to_epoch_seconds(value) == 0


@pytest.mark.parametrize("value", [
    datetime.datetime(2024, 1, 1),
    datetime.datetime(2024, 1, 1, microsecond=999999),
    datetime.datetime(2024, 1, 1, tzinfo=tzoffset(None, 0)),
])
def test_naive_and_utc_datetimes_retain_whole_second_behavior(value):
    assert force_to_epoch_seconds(value) == 1704067200


@pytest.mark.parametrize("value", [0, -1, 1704067200, 1704067200.25])
def test_numeric_timestamps_pass_through(value):
    assert force_to_epoch_seconds(value) is value


def test_cli_datetime_conversion_respects_timezone():
    value = datetime.datetime(2024, 1, 1, 5, 30, tzinfo=tzoffset(None, 19800))
    assert parse_date_as_epoch_timestamp(value) == 1704067200


def test_slo_history_uses_utc_epoch_seconds():
    start = datetime.datetime(2024, 1, 1, 5, 30, tzinfo=tzoffset(None, 19800))
    end = datetime.datetime(2024, 1, 1, 1, tzinfo=tzoffset(None, 0))
    with mock.patch.object(ActionAPIResource, "_trigger_class_action") as request:
        request.return_value = {"data": []}
        assert api.ServiceLevelObjective.history("slo-id", start, end) == {"data": []}
    request.assert_called_once_with(
        "GET", "history", id="slo-id",
        params={"id": "slo-id", "from_ts": 1704067200, "to_ts": 1704070800},
        body=None, suppress_response_errors_on_codes=[200],
    )
