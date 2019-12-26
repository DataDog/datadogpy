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

from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    DeletableAPIResource, UpdatableAPIResource, AddableAPISubResource


class AzureIntegration(GetableAPIResource, CreateableAPIResource, DeletableAPIResource,
                       UpdatableAPIResource, AddableAPISubResource):
    """
    A wrapper around Azure integration API.
    """
    _resource_name = 'integration'
    _resource_id = 'azure'

    @classmethod
    def list(cls, **params):
        """
        List all Datadog-Azure integrations available in your Datadog organization.

        >>> api.AzureIntegration.list()
        """
        return super(AzureIntegration, cls).get(id=cls._resource_id, **params)

    @classmethod
    def create(cls, **params):
        """
        Add a new Azure integration config.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"
        >>> client_secret = "<AZURE_CLIENT_SECRET>"
        >>> host_filters = ["<KEY>:<VALUE>"]

        >>> api.AzureIntegration.create(tenant_name=tenant_name, client_id=client_id, \
        client_secret=client_secret,host_filters=host_filters)
        """
        return super(AzureIntegration, cls).create(id=cls._resource_id, **params)

    @classmethod
    def delete(cls, **body):
        """
        Delete a given Datadog-Azure integration.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"

        >>> api.AzureIntegration.delete(tenant_name=tenant_name, client_id=client_id)
        """
        return super(AzureIntegration, cls).delete(id=cls._resource_id, body=body)

    @classmethod
    def update_host_filters(cls, **params):
        """
        Update the defined list of host filters for a given Datadog-Azure integration. \

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"
        >>> host_filters = "<KEY>:<VALUE>"

        >>> api.AzureIntegration.update_host_filters(tenant_name=tenant_name, client_id=client_id, \
            host_filters=host_filters)
        """
        cls._sub_resource_name = 'host_filters'
        return super(AzureIntegration, cls).add_items(id=cls._resource_id, **params)

    @classmethod
    def update(cls, **body):
        """
        Update an Azure account configuration.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"
        >>> new_tenant_name = "<NEW_AZURE_TENANT_NAME>"
        >>> new_client_id = "<NEW_AZURE_CLIENT_ID>"
        >>> client_secret = "<AZURE_CLIENT_SECRET>"
        >>> host_filters = "<KEY>:<VALUE>"

        >>> api.AzureIntegration.update(tenant_name=tenant_name, client_id=client_id, \
        new_tenant_name=new_tenant_name, new_client_id=new_client_id,\
        client_secret=client_secret, host_filters=host_filters)
        """
        params = {}
        return super(AzureIntegration, cls).update(id=cls._resource_id, params=params, **body)
