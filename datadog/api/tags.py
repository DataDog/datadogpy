# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    CreateableAPIResource,
    UpdatableAPIResource,
    DeletableAPIResource,
    GetableAPIResource,
    ListableAPIResource,
)


class Tag(CreateableAPIResource, UpdatableAPIResource, GetableAPIResource, ListableAPIResource, DeletableAPIResource):
    """
    A wrapper around Tag HTTP API.
    """

    _resource_name = "tags/hosts"

    @classmethod
    def create(cls, host, **body):
        """
        Add tags to a host

        :param tags: list of tags to apply to the host
        :type tags: string list

        :param source: source of the tags
        :type source: string

        :returns: Dictionary representing the API's JSON response
        """
        params = {}
        if "source" in body:
            params["source"] = body["source"]
        return super(Tag, cls).create(id=host, params=params, **body)

    @classmethod
    def update(cls, host, **body):
        """
        Update all tags for a given host

        :param tags: list of tags to apply to the host
        :type tags: string list

        :param source: source of the tags
        :type source: string

        :returns: Dictionary representing the API's JSON response
        """
        params = {}
        if "source" in body:
            params["source"] = body["source"]
        return super(Tag, cls).update(id=host, params=params, **body)
