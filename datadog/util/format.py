# stdlib
import json


def pretty_json(obj):
    return json.dumps(obj, sort_keys=True, indent=2)


def construct_url(host, api_version, path):
    return "{}/api/{}/{}".format(host.strip("/"), api_version.strip("/"), path.strip("/"))
