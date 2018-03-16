from datadog.api.resources import GetableAPIResource, CreateableAPIResource,\
    UpdatableAPIResource, ListableAPIResource, DeletableAPIResource


class Downtime(GetableAPIResource, CreateableAPIResource, UpdatableAPIResource,
               ListableAPIResource, DeletableAPIResource):
    """
    A wrapper around Monitor Downtiming HTTP API.
    """
    _resource_name = 'downtime'
