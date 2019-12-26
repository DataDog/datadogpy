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

from datadog.api.resources import ActionAPIResource, CreateableAPIResource, CustomUpdatableAPIResource,\
    DeletableAPIResource, GetableAPIResource, ListableAPIResource

from datadog.api.api_client import APIClient


class Roles(ActionAPIResource, CreateableAPIResource, CustomUpdatableAPIResource, GetableAPIResource,
            ListableAPIResource, DeletableAPIResource):
    """
    A wrapper around Tag HTTP API.
    """
    _resource_name = 'roles'
    _api_version = 'v2'

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
        path = '{resource_name}/{resource_id}/permissions'.format(
            resource_name=cls._resource_name,
            resource_id=id
        )
        api_version = getattr(cls, '_api_version', None)

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
        path = '{resource_name}/{resource_id}/permissions'.format(
            resource_name=cls._resource_name,
            resource_id=id
        )
        api_version = getattr(cls, '_api_version', None)

        return APIClient.submit("DELETE", path, api_version, body, **params)
