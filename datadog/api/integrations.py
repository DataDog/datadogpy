from datadog.api.api_client import APIClient
from datadog.api.resources import CreateableAPIResource


class Aws(CreateableAPIResource):
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
        path = '{resource_name}'.format(
            resource_name=cls._resource_name
        )
        return APIClient.submit('GET', path, **params)

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
        path = '{resource_name}'.format(
            resource_name=cls._resource_name
        )
        return APIClient.submit('DELETE', path, **params)


class Slack(CreateableAPIResource):
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

        path = '{resource_name}'.format(
            resource_name=cls._resource_name
        )
        return APIClient.submit('GET', path, **params)

    @classmethod
    def delete(cls, **params):
        """
        Delete Slack Integration.

        :returns:
        """

        path = '{resource_name}'.format(
            resource_name=cls._resource_name
        )
        return APIClient.submit('DELETE', path, **params)

    @classmethod
    def update(cls, params=None, **body):
        """
        Update Slack Integration

        :returns:
        """
        if params is None:
            params = {}

        path = '{resource_name}'.format(
            resource_name=cls._resource_name
        )
        return APIClient.submit('PUT', path, body, **params)
