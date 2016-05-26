from datadog.api.resources import CreateableAPIResource, UpdatableAPIResource,\
    DeletableAPIResource, GetableAPIResource, ListableAPIResource


class Tag(CreateableAPIResource, UpdatableAPIResource, GetableAPIResource,
          ListableAPIResource, DeletableAPIResource):
    """
    A wrapper around Tag HTTP API.
    """
    _class_name = 'tags'
    _class_url = '/tags/hosts'
    _plural_class_name = 'tags'

    @classmethod
    def create(cls, host, **body):
        """
        Add tags to a host

        :param tags: list of tags to apply to the host
        :type tags: string list

        :param source: source of the tags
        :type source: string

        :return: JSON response from HTTP request
        """
        params = {}
        if 'source' in body:
            params['source'] = body['source']
        return super(Tag, cls).create(id=host, params=params, **body)

    @classmethod
    def update(cls, host, **body):
        """
        Update all tags for a given host

        :param tags: list of tags to apply to the host
        :type tags: string list

        :param source: source of the tags
        :type source: string

        :return: JSON response from HTTP request
        """
        params = {}
        if 'source' in body:
            params['source'] = body['source']
        return super(Tag, cls).update(id=host, params=params, **body)
