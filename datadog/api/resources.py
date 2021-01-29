# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Datadog API resources.
"""

from datadog.api.api_client import APIClient


class CreateableAPIResource(object):
    """
    Creatable API Resource
    """

    @classmethod
    def create(cls, attach_host_name=False, method="POST", id=None, params=None, **body):
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
        api_version = getattr(cls, "_api_version", None)

        if method == "GET":
            return APIClient.submit("GET", path, api_version, **body)
        if id is None:
            return APIClient.submit("POST", path, api_version, body, attach_host_name=attach_host_name, **params)

        path = "{resource_name}/{resource_id}".format(resource_name=cls._resource_name, resource_id=id)
        return APIClient.submit("POST", path, api_version, body, attach_host_name=attach_host_name, **params)


class SendableAPIResource(object):
    """
    Fork of CreateableAPIResource class with different method names
    """

    @classmethod
    def send(cls, attach_host_name=False, id=None, compress_payload=False, **body):
        """
        Create an API resource object

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param id: create a new resource object as a child of the given object
        :type id: id

        :param compress_payload: compress the payload using zlib
        :type compress_payload: bool

        :param body: new resource object attributes
        :type body: dictionary

        :returns: Dictionary representing the API's JSON response
        """
        api_version = getattr(cls, "_api_version", None)

        if id is None:
            return APIClient.submit(
                "POST",
                cls._resource_name,
                api_version,
                body,
                attach_host_name=attach_host_name,
                compress_payload=compress_payload,
            )

        path = "{resource_name}/{resource_id}".format(resource_name=cls._resource_name, resource_id=id)
        return APIClient.submit(
            "POST", path, api_version, body, attach_host_name=attach_host_name, compress_payload=compress_payload
        )


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

        path = "{resource_name}/{resource_id}".format(resource_name=cls._resource_name, resource_id=id)
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("PUT", path, api_version, body, **params)


class CustomUpdatableAPIResource(object):
    """
    Updatable API Resource with custom HTTP Verb
    """

    @classmethod
    def update(cls, method=None, id=None, params=None, **body):
        """
        Update an API resource object

        :param method: HTTP method, defaults to PUT
        :type params: string

        :param params: updatable resource id
        :type params: string

        :param params: updated resource object source
        :type params: dictionary

        :param body: updated resource object attributes
        :type body: dictionary

        :returns: Dictionary representing the API's JSON response
        """

        if method is None:
            method = "PUT"
        if params is None:
            params = {}

        path = "{resource_name}/{resource_id}".format(resource_name=cls._resource_name, resource_id=id)
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit(method, path, api_version, body, **params)


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
        path = "{resource_name}/{resource_id}".format(resource_name=cls._resource_name, resource_id=id)
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("DELETE", path, api_version, **params)


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
        path = "{resource_name}/{resource_id}".format(resource_name=cls._resource_name, resource_id=id)
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("GET", path, api_version, **params)


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
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("GET", cls._resource_name, api_version, **params)


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

        path = "{resource_name}/{resource_id}/{sub_resource_name}".format(
            resource_name=cls._resource_name, resource_id=id, sub_resource_name=cls._sub_resource_name
        )
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("GET", path, api_version, **params)


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

        path = "{resource_name}/{resource_id}/{sub_resource_name}".format(
            resource_name=cls._resource_name, resource_id=id, sub_resource_name=cls._sub_resource_name
        )
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("POST", path, api_version, body, **params)


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

        path = "{resource_name}/{resource_id}/{sub_resource_name}".format(
            resource_name=cls._resource_name, resource_id=id, sub_resource_name=cls._sub_resource_name
        )
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("PUT", path, api_version, body, **params)


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

        path = "{resource_name}/{resource_id}/{sub_resource_name}".format(
            resource_name=cls._resource_name, resource_id=id, sub_resource_name=cls._sub_resource_name
        )
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("DELETE", path, api_version, body, **params)


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
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("GET", cls._resource_name, api_version, **params)


class ActionAPIResource(object):
    """
    Actionable API Resource
    """

    @classmethod
    def _trigger_class_action(cls, method, action_name, id=None, params=None, **body):
        """
        Trigger an action

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param action_name: action name
        :type action_name: string

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

        api_version = getattr(cls, "_api_version", None)

        if id is None:
            path = "{resource_name}/{action_name}".format(resource_name=cls._resource_name, action_name=action_name)
        else:
            path = "{resource_name}/{resource_id}/{action_name}".format(
                resource_name=cls._resource_name, resource_id=id, action_name=action_name
            )
        if method == "GET":
            # Do not add body to GET requests, it causes 400 Bad request responses on EU site
            body = None
        return APIClient.submit(method, path, api_version, body, **params)

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
        api_version = getattr(cls, "_api_version", None)
        if id is None:
            return APIClient.submit(method, name, api_version, body)

        path = "{action_name}/{resource_id}".format(action_name=name, resource_id=id)
        if method == "GET":
            # Do not add body to GET requests, it causes 400 Bad request responses on EU site
            body = None
        return APIClient.submit(method, path, api_version, body)


class UpdatableAPISyntheticsSubResource(object):
    """
    Update Synthetics sub resource
    """

    @classmethod
    def update_synthetics_items(cls, id, params=None, **body):
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

        path = "{resource_name}/tests/{resource_id}/{sub_resource_name}".format(
            resource_name=cls._resource_name, resource_id=id, sub_resource_name=cls._sub_resource_name
        )
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("PUT", path, api_version, body, **params)


class UpdatableAPISyntheticsResource(object):
    """
    Update Synthetics resource
    """

    @classmethod
    def update_synthetics(cls, id, params=None, **body):
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

        path = "{resource_name}/tests/{resource_id}".format(resource_name=cls._resource_name, resource_id=id)
        api_version = getattr(cls, "_api_version", None)

        return APIClient.submit("PUT", path, api_version, body, **params)


class ActionAPISyntheticsResource(object):
    """
    Actionable Synthetics API Resource
    """

    @classmethod
    def _trigger_synthetics_class_action(cls, method, name, id=None, params=None, **body):
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

        api_version = getattr(cls, "_api_version", None)

        if id is None:
            path = "{resource_name}/{action_name}".format(resource_name=cls._resource_name, action_name=name)
        else:
            path = "{resource_name}/{action_name}/{resource_id}".format(
                resource_name=cls._resource_name, resource_id=id, action_name=name
            )
        if method == "GET":
            # Do not add body to GET requests, it causes 400 Bad request responses on EU site
            body = None
        return APIClient.submit(method, path, api_version, body, **params)
