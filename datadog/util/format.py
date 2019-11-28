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
    final_tag_list = []
    for tag in tag_list:
        # remove commas and whitespaces from the tag
        final_tag_list.append(tag.replace(",", "_").replace(" ", ""))
    return final_tag_list
