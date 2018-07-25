from datadog.api.resources import CreateableAPIResource, UpdatableAPIResource, \
    DeletableAPIResource


class Comment(CreateableAPIResource, UpdatableAPIResource, DeletableAPIResource):
    """
    A wrapper around Comment HTTP API.
    """
    _resource_name = 'comments'
