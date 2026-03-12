# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Datadog API resources.
"""
from typing import Any, Dict, Optional

from datadog.api.api_client import APIClient


class CreateableAPIResource(object):
    """
    Creatable API Resource
    """

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def create(cls, attach_host_name=False, method="POST", id=None, params=None, **body):
        # type: (bool, str, Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def send(cls, attach_host_name=False, id=None, compress_payload=False, **body):
        # type: (bool, Optional[Any], bool, **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def update(cls, id, params=None, **body):
        # type: (Any, Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def update(cls, method=None, id=None, params=None, **body):
        # type: (Optional[str], Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def delete(cls, id, **params):
        # type: (Any, **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def get(cls, id, **params):
        # type: (Any, **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def get_all(cls, **params):
        # type: (**Any) -> Any
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

    _resource_name = ""  # type: str
    _sub_resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def get_items(cls, id, **params):
        # type: (Any, **Any) -> Any
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

    _resource_name = ""  # type: str
    _sub_resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def add_items(cls, id, params=None, **body):
        # type: (Any, Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _sub_resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def update_items(cls, id, params=None, **body):
        # type: (Any, Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _sub_resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def delete_items(cls, id, params=None, **body):
        # type: (Any, Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def _search(cls, **params):
        # type: (**Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def _trigger_class_action(cls, method, action_name, id=None, params=None, **body):
        # type: (str, str, Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
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
        body_request = None if method == "GET" else body  # type: Optional[Dict[str, Any]]
        return APIClient.submit(method, path, api_version, body_request, **params)

    @classmethod
    def _trigger_action(cls, method, name, id=None, **body):
        # type: (str, str, Optional[Any], **Any) -> Any
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
        body_request = None if method == "GET" else body  # type: Optional[Dict[str, Any]]
        return APIClient.submit(method, path, api_version, body_request)


class UpdatableAPISyntheticsSubResource(object):
    """
    Update Synthetics sub resource
    """

    _resource_name = ""  # type: str
    _sub_resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def update_synthetics_items(cls, id, params=None, **body):
        # type: (Any, Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def update_synthetics(cls, id, params=None, **body):
        # type: (Any, Optional[Dict[str, Any]], **Any) -> Any
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

    _resource_name = ""  # type: str
    _api_version = None  # type: Optional[str]

    @classmethod
    def _trigger_synthetics_class_action(cls, method, name, id=None, params=None, **body):
        # type: (str, str, Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
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
        body_request = None if method == "GET" else body  # type: Optional[Dict[str, Any]]
        return APIClient.submit(method, path, api_version, body_request, **params)
