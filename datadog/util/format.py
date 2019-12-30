# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/). Copyright 2020 Datadog, Inc.

# stdlib
import calendar
import datetime
import json


def pretty_json(obj):
    return json.dumps(obj, sort_keys=True, indent=2)


def construct_url(host, api_version, path):
    return "{}/api/{}/{}".format(host.strip("/"), api_version.strip("/"), path.strip("/"))


def construct_path(api_version, path):
    return "{}/{}".format(api_version.strip("/"), path.strip("/"))


def force_to_epoch_seconds(epoch_sec_or_dt):
    if isinstance(epoch_sec_or_dt, datetime.datetime):
        return calendar.timegm(epoch_sec_or_dt.timetuple())
    return epoch_sec_or_dt


def normalize_tags(tag_list):
    return [tag.replace(',', '_') for tag in tag_list]
