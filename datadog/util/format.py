# datadog
from datadog.util.compat import json


def pretty_json(obj):
    return json.dumps(obj, sort_keys=True, indent=2)
