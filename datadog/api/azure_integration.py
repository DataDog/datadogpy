# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    DeletableAPIResource,
    UpdatableAPIResource,
    AddableAPISubResource,
)


class AzureIntegration(
    GetableAPIResource, CreateableAPIResource, DeletableAPIResource, UpdatableAPIResource, AddableAPISubResource
):
    """
    A wrapper around Azure integration API.
    """

    _resource_name = "integration"
    _resource_id = "azure"

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
        cls._sub_resource_name = "host_filters"
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
