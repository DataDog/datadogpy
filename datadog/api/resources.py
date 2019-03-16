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

        :returns: Dictionary representing the API's JSON response
        """
        if params is None:
            params = {}

        path = cls._resource_name

        if method == 'GET':
            return APIClient.submit('GET', path, **body)
        if id is None:
            return APIClient.submit('POST', path, body,
                                    attach_host_name=attach_host_name, **params)

        path = '{resource_name}/{resource_id}'.format(
            resource_name=cls._resource_name,
            resource_id=id
        )
        return APIClient.submit('POST', path, body, attach_host_name=attach_host_name, **params)


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

        :returns: Dictionary representing the API's JSON response
        """
        if id is None:
            return APIClient.submit('POST', cls._resource_name, body,
                                    attach_host_name=attach_host_name)

        path = '{resource_name}/{resource_id}'.format(
            resource_name=cls._resource_name,
            resource_id=id
        )
        return APIClient.submit('POST', path, body, attach_host_name=attach_host_name)


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

        :returns: Dictionary representing the API's JSON response
        """
        if params is None:
            params = {}

        path = '{resource_name}/{resource_id}'.format(
            resource_name=cls._resource_name,
            resource_id=id
        )
        return APIClient.submit('PUT', path, body, **params)


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

        :returns: Dictionary representing the API's JSON response
        """
        path = '{resource_name}/{resource_id}'.format(
            resource_name=cls._resource_name,
            resource_id=id
        )
        return APIClient.submit('DELETE', path, **params)


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

        :returns: Dictionary representing the API's JSON response
        """
        path = '{resource_name}/{resource_id}'.format(
            resource_name=cls._resource_name,
            resource_id=id
        )
        return APIClient.submit('GET', path, **params)


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

        :returns: Dictionary representing the API's JSON response
        """
        return APIClient.submit('GET', cls._resource_name, **params)


class ListableAPISubResource(object):
    """
    Listable API Sub-Resource
    """
    @classmethod
    def get_items(cls, id, **params):
        """
        List API sub-resource objects from a resource

        :param id: resource id to retrieve sub-resource objects from
        :type id: id

        :param params: parameters to filter API sub-resource stream
        :type params: dictionary

        :returns: Dictionary representing the API's JSON response
        """
        path = '{resource_name}/{resource_id}/{sub_resource_name}'.format(
            resource_name=cls._resource_name,
            resource_id=id,
            sub_resource_name=cls._sub_resource_name
        )
        return APIClient.submit('GET', path, **params)


class AddableAPISubResource(object):
    """
    Addable API Sub-Resource
    """
    @classmethod
    def add_items(cls, id, params=None, **body):
        """
        Add new API sub-resource objects to a resource

        :param id: resource id to add sub-resource objects to
        :type id: id

        :param params: request parameters
        :type params: dictionary

        :param body: new sub-resource objects attributes
        :type body: dictionary

        :returns: Dictionary representing the API's JSON response
        """
        if params is None:
            params = {}

        path = '{resource_name}/{resource_id}/{sub_resource_name}'.format(
            resource_name=cls._resource_name,
            resource_id=id,
            sub_resource_name=cls._sub_resource_name
        )
        return APIClient.submit('POST', path, body, **params)


class UpdatableAPISubResource(object):
    """
    Updatable API Sub-Resource
    """
    @classmethod
    def update_items(cls, id, params=None, **body):
        """
        Update API sub-resource objects of a resource

        :param id: resource id to update sub-resource objects from
        :type id: id

        :param params: request parameters
        :type params: dictionary

        :param body: updated sub-resource objects attributes
        :type body: dictionary

        :returns: Dictionary representing the API's JSON response
        """
        if params is None:
            params = {}

        path = '{resource_name}/{resource_id}/{sub_resource_name}'.format(
            resource_name=cls._resource_name,
            resource_id=id,
            sub_resource_name=cls._sub_resource_name
        )
        return APIClient.submit('PUT', path, body, **params)


class DeletableAPISubResource(object):
    """
    Deletable API Sub-Resource
    """
    @classmethod
    def delete_items(cls, id, params=None, **body):
        """
        Delete API sub-resource objects from a resource

        :param id: resource id to delete sub-resource objects from
        :type id: id

        :param params: request parameters
        :type params: dictionary

        :param body: deleted sub-resource objects attributes
        :type body: dictionary

        :returns: Dictionary representing the API's JSON response
        """
        if params is None:
            params = {}

        path = '{resource_name}/{resource_id}/{sub_resource_name}'.format(
            resource_name=cls._resource_name,
            resource_id=id,
            sub_resource_name=cls._sub_resource_name
        )
        return APIClient.submit('DELETE', path, body, **params)


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

        :returns: Dictionary representing the API's JSON response
        """
        return APIClient.submit('GET', cls._resource_name, **params)


class ActionAPIResource(object):
    """
    Actionable API Resource
    """
    @classmethod
    def _trigger_class_action(cls, method, name, id=None, params=None, **body):
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

        :param body: action body
        :type body: dictionary

        :returns: Dictionary representing the API's JSON response
        """
        if params is None:
            params = {}

        if id is None:
            path = '{resource_name}/{action_name}'.format(
                resource_name=cls._resource_name,
                action_name=name
            )
            return APIClient.submit(method, path, body, **params)

        path = '{resource_name}/{resource_id}/{action_name}'.format(
            resource_name=cls._resource_name,
            resource_id=id,
            action_name=name
        )
        return APIClient.submit(method, path, body, **params)

    @classmethod
    def _trigger_action(cls, method, name, id=None, **body):
        """
        Trigger an action

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param name: action name
        :type name: string

        :param id: trigger the action for the specified resource object
        :type id: id

        :param body: action body
        :type body: dictionary

        :returns: Dictionary representing the API's JSON response
        """
        if id is None:
            return APIClient.submit(method, name, body)

        path = '{action_name}/{resource_id}'.format(
            action_name=name,
            resource_id=id
        )
        return APIClient.submit(method, path, body)
