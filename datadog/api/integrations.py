from datadog.api.resources import (
    CreateableAPIResource,
    DeletableAPIResource,
    GetableAPIResource,
    UpdatableAPIResource
)


class Aws(CreateableAPIResource, GetableAPIResource, DeletableAPIResource):
    """
    A wrapper around Integration AWS HTTP API.
    """
    _resource_name = 'integration/aws'

    @classmethod
    def get(cls, **params):
        """
        Get AWS Integration details.

        :returns: Dictionary representing the API's JSON response
        """

        return super(Aws, cls).get(id="", **params)

    @classmethod
    def delete(cls, **params):
        """
        Delete AWS Integration.

        :param account_id: aws account id
        :type account_id: id

        :param role_name: string indicating AWS role
        :type role_name: string

        :returns: Dictionary representing the API's JSON response
        """

        return super(Aws, cls).get(id="", **params)


class Slack(CreateableAPIResource, GetableAPIResource, DeletableAPIResource, UpdatableAPIResource):
    """
    A wrapper around Integration AWS HTTP API.
    """
    _resource_name = 'integration/slack'

    @classmethod
    def get(cls, **params):
        """
        Get Slack Integration details.

        :returns: Dictionary representing the API's JSON response
        """

        return super(Slack, cls).get(id="", **params)

    @classmethod
    def delete(cls, **params):
        """
        Delete Slack Integration.

        :returns:
        """

        return super(Slack, cls).get(id="", **params)

    @classmethod
    def update(cls, params=None, **body):
        """
        Update Slack Integration

        :returns:
        """

        return super(Slack, cls).update(id="", params=params, **body)
