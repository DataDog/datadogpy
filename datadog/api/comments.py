from datadog.api.resources import CreateableAPIResource, UpdatableAPIResource, \
    DeletableAPIResource


class Comment(CreateableAPIResource, UpdatableAPIResource, DeletableAPIResource):
    """
    A wrapper around Comment HTTP API.
    """
    _class_name = 'comment'
    _class_url = '/comments'
    _json_name = 'comment'
