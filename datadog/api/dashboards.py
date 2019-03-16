from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, DeletableAPIResource, ListableAPIResource


class Dashboard(GetableAPIResource, CreateableAPIResource,
                UpdatableAPIResource, DeletableAPIResource,
                ListableAPIResource):
    """
    A wrapper around Dashboard HTTP API.
    """
    _resource_name = 'dashboard'
