from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, DeletableAPIResource


class Dashboard(GetableAPIResource, CreateableAPIResource,
                UpdatableAPIResource, DeletableAPIResource):
    """
    A wrapper around Dashboard HTTP API.
    """
    _resource_name = 'dashboard'
