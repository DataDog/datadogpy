# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import CreateableAPIResource
from datadog.api.api_client import APIClient


class Logs(CreateableAPIResource):
    """
    A wrapper around Log HTTP API.
    """

    _resource_name = "logs-queries"

    @classmethod
    def list(cls, data):
        path = "{resource_name}/list".format(
            resource_name=cls._resource_name,
        )
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("POST", path, api_version, data)
