from datadog.api.resources import ActionAPIResource, CreateableAPIResource, CustomUpdatableAPIResource, \
    DeletableAPIResource, GetableAPIResource, ListableAPIResource


class Permissions(ActionAPIResource, CreateableAPIResource, CustomUpdatableAPIResource, GetableAPIResource,
                  ListableAPIResource, DeletableAPIResource):
    """
    A wrapper around Tag HTTP API.
    """
    _resource_name = 'permissions'
    _api_version = 'v2'
