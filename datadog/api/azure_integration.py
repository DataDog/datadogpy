from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    SearchableAPIResource, DeletableAPIResource, \
    UpdatableAPIResource, ListableAPISubResource, AddableAPISubResource


class Azure(GetableAPIResource, CreateableAPIResource, SearchableAPIResource,
            DeletableAPIResource, ListableAPISubResource, UpdatableAPIResource,
            AddableAPISubResource):
    """
    A wrapper around Event HTTP API.
    """
    _resource_name = 'integration'
    _resource_id = 'azure'

    @classmethod
    def list(cls, id=_resource_id, **params):
        """
        List all Datadog-Azure integrations available in your Datadog organization.

        >>> api.Azure.list()
        """
        return super(Azure, cls).get(id=id, **params)

    @classmethod
    def create(cls, id=_resource_id, **params):
        """
        Add a new Azure integration config.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"
        >>> client_secret = "<AZURE_CLIENT_SECRET>"
        >>> host_filters = ["<KEY>:<VALUE>"]

        >>> api.Azure.create(tenant_name=tenant_name, client_id=client_id, \
        client_secret=client_secret,host_filters=host_filters)
        """
        return super(Azure, cls).create(id=id, **params)

    @classmethod
    def delete(cls, id=_resource_id, **body):
        """
        Delete a given Datadog-AWS integration.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"

        >>> api.Azure.delete(tenant_name=tenant_name, client_id=client_id)
        """
        return super(Azure, cls).delete(id=id, body=body)

    @classmethod
    def update_host_filters(cls, id=_resource_id, **params):
        """
        Update the defined list of host filters for a given Datadog-Azure integration.
        
        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"
        >>> host_filters = "<KEY>:<VALUE>"

        >>> api.Azure.update_host_filters(tenant_name=tenant_name, client_id=client_id, \
            host_filters=host_filters)
        """
        cls._sub_resource_name = 'host_filters'
        return super(Azure, cls).add_items(id=id, **params)

    @classmethod
    def update(cls, id=_resource_id, **body):
        """
        Update an Azure account configuration.

        >>> tenant_name = "<AZURE_TENANT_NAME>"
        >>> client_id = "<AZURE_CLIENT_ID>"
        >>> new_tenant_name = "<NEW_AZURE_TENANT_NAME>"
        >>> new_client_id = "<NEW_AZURE_CLIENT_ID>"
        >>> client_secret = "<AZURE_CLIENT_SECRET>"
        >>> host_filters = "<KEY>:<VALUE>"

        >>> api.Azure.update(tenant_name=tenant_name, client_id=client_id, \
        new_tenant_name=new_tenant_name, new_client_id=new_client_id,\
        client_secret=client_secret, host_filters=host_filters)
        """
        params = {}
        params['new_tenant_name'] = body.get('new_tenant_name')
        params['new_client_id'] = body.get('new_client_id')
        return super(Azure, cls).update(id=id, params=params, **body)
