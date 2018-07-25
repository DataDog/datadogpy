from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, ListableAPIResource, DeletableAPIResource


class Timeboard(GetableAPIResource, CreateableAPIResource,
                UpdatableAPIResource, ListableAPIResource,
                DeletableAPIResource):
    """
    A wrapper around Timeboard HTTP API.
    """
    _resource_name = 'dash'
