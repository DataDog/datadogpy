from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, ListableAPIResource, DeletableAPIResource


class Timeboard(GetableAPIResource, CreateableAPIResource,
                UpdatableAPIResource, ListableAPIResource,
                DeletableAPIResource):
    """
    A wrapper around Timeboard HTTP API.
    """
    _class_name = 'dash'
    _class_url = '/dash'
    _plural_class_name = 'dashes'
    _json_name = 'dash'
