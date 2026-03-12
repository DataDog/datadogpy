# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from typing import Any, Dict, Optional

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
    _sub_resource_name = ""  # type: str

    @classmethod
    def list(cls, **params):
        # type: (**Any) -> Any
        """
        List all Datadog-Azure integrations available in your Datadog organization.

        >>> api.AzureIntegration.list()
        """
        return super(AzureIntegration, cls).get(id=cls._resource_id, **params)

    @classmethod
    def create(cls, attach_host_name=False, method="POST", id=None, params=None, **body):
        # type: (bool, str, Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
        """
        Add a new Azure integration config.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"
        >>> client_secret = "<AZURE_CLIENT_SECRET>"
        >>> host_filters = ["<KEY>:<VALUE>"]

        >>> api.AzureIntegration.create(tenant_name=tenant_name, client_id=client_id, \
        client_secret=client_secret,host_filters=host_filters)
        """
        return super(AzureIntegration, cls).create(id=cls._resource_id, **body)

    @classmethod
    def delete(cls, id=None, **body):
        # type: (Optional[Any], **Any) -> Any
        """
        Delete a given Datadog-Azure integration.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"

        >>> api.AzureIntegration.delete(tenant_name=tenant_name, client_id=client_id)
        """
        return super(AzureIntegration, cls).delete(id=cls._resource_id, body=body)

    @classmethod
    def update_host_filters(cls, **params):
        # type: (**Any) -> Any
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
    def update(cls, id=None, params=None, **body):
        # type: (Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
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
        actual_params = {}  # type: Dict[str, Any]
        return super(AzureIntegration, cls).update(id=cls._resource_id, params=actual_params, **body)
