# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    ActionAPIResource,
    CreateableAPIResource,
    CustomUpdatableAPIResource,
    DeletableAPIResource,
    GetableAPIResource,
    ListableAPIResource,
)

from datadog.api.api_client import APIClient


class Roles(
    ActionAPIResource,
    CreateableAPIResource,
    CustomUpdatableAPIResource,
    GetableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
):
    """
    A wrapper around Tag HTTP API.
    """

    _resource_name = "roles"
    _api_version = "v2"

    @classmethod
    def update(cls, id, **body):
        """
        Update a role's attributes

        :param id: uuid of the role
        :param body: dict with type of the input, role `id`, and modified attributes
        :returns: Dictionary representing the API's JSON response
        """
        params = {}
        return super(Roles, cls).update("PATCH", id, params=params, **body)

    @classmethod
    def assign_permission(cls, id, **body):
        """
        Assign permission to a role

        :param id: uuid of the role to assign permission to
        :param body: dict with "type": "permissions" and uuid of permission to assign
        :returns: Dictionary representing the API's JSON response
        """
        params = {}
        path = "{resource_name}/{resource_id}/permissions".format(resource_name=cls._resource_name, resource_id=id)
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("POST", path, api_version, body, **params)

    @classmethod
    def unassign_permission(cls, id, **body):
        """
        Unassign permission from a role

        :param id: uuid of the role to unassign permission from
        :param body: dict with "type": "permissions" and uuid of permission to unassign
        :returns: Dictionary representing the API's JSON response
        """
        params = {}
        path = "{resource_name}/{resource_id}/permissions".format(resource_name=cls._resource_name, resource_id=id)
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("DELETE", path, api_version, body, **params)
