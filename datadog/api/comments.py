from datadog.api.resources import CreateableAPIResource, UpdatableAPIResource


class Comment(CreateableAPIResource, UpdatableAPIResource):
    """
    A wrapper around Comment HTTP API.
    """
    _resource_name = 'comments'
