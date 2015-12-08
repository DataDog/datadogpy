from datadog.api.resources import GetableAPIResource, CreateableAPIResource,\
    UpdatableAPIResource, ListableAPIResource, DeletableAPIResource


class Downtime(GetableAPIResource, CreateableAPIResource, UpdatableAPIResource,
               ListableAPIResource, DeletableAPIResource):
    """
    A wrapper around Monitor Downtiming HTTP API.
    """
    _class_url = '/downtime'
