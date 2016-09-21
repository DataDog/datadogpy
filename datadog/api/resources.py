"""
Datadog API resources.
"""
# datadog
from datadog.api.api_client import APIClient


class CreateableAPIResource(object):
    """
    Creatable API Resource
    """
    @classmethod
    def create(cls, attach_host_name=False, method='POST', id=None, params=None, **body):
        """
        Create a new API resource object

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param id: create a new resource object as a child of the given object
        :type id: id

        :param params: new resource object source
        :type params: dictionary

        :param body: new resource object attributes
        :type body: dictionary

        :returns: JSON response from HTTP API request
        """
        if params is None:
            params = {}
        if method == 'GET':
            return APIClient.submit('GET', cls._class_url, **body)
        if id is None:
            return APIClient.submit('POST', cls._class_url, body,
                                    attach_host_name=attach_host_name, **params)
        else:
            return APIClient.submit('POST', cls._class_url + "/" + str(id), body,
                                    attach_host_name=attach_host_name, **params)


class SendableAPIResource(object):
    """
    Fork of CreateableAPIResource class with different method names
    """
    @classmethod
    def send(cls, attach_host_name=False, id=None, **body):
        """
        Create an API resource object

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param id: create a new resource object as a child of the given object
        :type id: id

        :param body: new resource object attributes
        :type body: dictionary

        :returns: JSON response from HTTP API request
        """
        if id is None:
            return APIClient.submit('POST', cls._class_url, body,
                                    attach_host_name=attach_host_name)
        else:
            return APIClient.submit('POST', cls._class_url + "/" + str(id), body,
                                    attach_host_name=attach_host_name)


class UpdatableAPIResource(object):
    """
    Updatable API Resource
    """
    @classmethod
    def update(cls, id, params=None, **body):
        """
        Update an API resource object

        :param params: updated resource object source
        :type params: dictionary

        :param body: updated resource object attributes
        :type body: dictionary

        :returns: JSON response from HTTP API request
        """
        if params is None:
            params = {}
        return APIClient.submit('PUT', cls._class_url + "/" + str(id), body, **params)


class DeletableAPIResource(object):
    """
    Deletable API Resource
    """
    @classmethod
    def delete(cls, id, **params):
        """
        Delete an API resource object

        :param id: resource object to delete
        :type id: id

        :returns: JSON response from HTTP API request
        """
        return APIClient.submit('DELETE', cls._class_url + "/" + str(id), **params)


class GetableAPIResource(object):
    """
    Getable API Resource
    """
    @classmethod
    def get(cls, id, **params):
        """
        Get information about an API resource object

        :param id: resource object id to retrieve
        :type id: id

        :param params: parameters to filter API resource stream
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        return APIClient.submit('GET', cls._class_url + "/" + str(id), **params)


class ListableAPIResource(object):
    """
    Listable API Resource
    """
    @classmethod
    def get_all(cls, **params):
        """
        List API resource objects

        :param params: parameters to filter API resource stream
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        return APIClient.submit('GET', cls._class_url, **params)


class SearchableAPIResource(object):
    """
    Fork of ListableAPIResource class with different method names
    """
    @classmethod
    def _search(cls, **params):
        """
        Query an API resource stream

        :param params: parameters to filter API resource stream
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        return APIClient.submit('GET', cls._class_url, **params)


class ActionAPIResource(object):
    """
    Actionable API Resource
    """
    @classmethod
    def _trigger_class_action(cls, method, name, id=None, **params):
        """
        Trigger an action

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param name: action name
        :type name: string

        :param id: trigger the action for the specified resource object
        :type id: id

        :param params: action parameters
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        if id is None:
            return APIClient.submit(method, cls._class_url + "/" + name, params)
        else:
            return APIClient.submit(method, cls._class_url + "/" + str(id) + "/" + name, params)

    @classmethod
    def _trigger_action(cls, method, name, id=None, **params):
        """
        Trigger an action

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param name: action name
        :type name: string

        :param id: trigger the action for the specified resource object
        :type id: id

        :param params: action parameters
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        if id is None:
            return APIClient.submit(method, name, params)
        else:
            return APIClient.submit(method, name + "/" + str(id), params)
