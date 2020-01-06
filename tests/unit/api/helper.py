# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
from io import BytesIO
import unittest
import json

# 3p
from mock import Mock
import requests

# datadog
from datadog import initialize, api
from datadog.api.http_client import RequestClient
from datadog.api.exceptions import ApiError
from datadog.api.resources import (
    CreateableAPIResource,
    UpdatableAPIResource,
    DeletableAPIResource,
    GetableAPIResource,
    ListableAPIResource,
    ListableAPISubResource,
    AddableAPISubResource,
    UpdatableAPISubResource,
    DeletableAPISubResource,
    ActionAPIResource
)
from datadog.util.compat import iteritems, is_p3k
from tests.util.contextmanagers import EnvVars


API_KEY = "apikey"
APP_KEY = "applicationkey"
API_HOST = "https://example.com"
HOST_NAME = "agent.hostname"
FAKE_PROXY = {
    "https": "http://user:pass@10.10.1.10:3128/",
}


class MockSession(object):
    """docstring for MockSession"""
    _args = None
    _kwargs = None
    _count = 0

    def request(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        self._count += 1
        return MockResponse()

    def call_args(self):
        return self._args, self._kwargs

    def call_count(self):
        return self._count


class MockResponse(requests.Response):

    def __init__(self, raise_for_status=False):
        super(MockResponse, self).__init__()
        self._raise_for_status = raise_for_status

    def raise_for_status(self):
        if not self._raise_for_status:
            return
        raise ApiError({'errors': ""})


# A few API Resources
class MyCreatable(CreateableAPIResource):
    _resource_name = 'creatables'

class MyParamsApiKeyCreatable(CreateableAPIResource):
    _resource_name = 'series'

class MyUpdatable(UpdatableAPIResource):
    _resource_name = 'updatables'


class MyGetable(GetableAPIResource):
    _resource_name = 'getables'


class MyListable(ListableAPIResource):
    _resource_name = 'listables'


class MyDeletable(DeletableAPIResource):
    _resource_name = 'deletables'


class MyListableSubResource(ListableAPISubResource):
    _resource_name = 'resource_name'
    _sub_resource_name = 'sub_resource_name'


class MyAddableSubResource(AddableAPISubResource):
    _resource_name = 'resource_name'
    _sub_resource_name = 'sub_resource_name'


class MyUpdatableSubResource(UpdatableAPISubResource):
    _resource_name = 'resource_name'
    _sub_resource_name = 'sub_resource_name'


class MyDeletableSubResource(DeletableAPISubResource):
    _resource_name = 'resource_name'
    _sub_resource_name = 'sub_resource_name'


class MyActionable(ActionAPIResource):
    _resource_name = 'actionables'

    @classmethod
    def trigger_class_action(cls, method, name, id=None, params=None, **body):
        super(MyActionable, cls)._trigger_class_action(method, name, id, params, **body)

    @classmethod
    def trigger_action(cls, method, name, id=None, **body):
        super(MyActionable, cls)._trigger_action(method, name, id, **body)


# Test classes
class DatadogAPITestCase(unittest.TestCase):

    def setUp(self):
        # Mock patch requests
        self.request_mock = MockSession()
        RequestClient._session = self.request_mock
        # self.request_patcher = patch('requests.Session')
        # request_class_mock = self.request_patcher.start()
        # self.request_mock = request_class_mock.return_value
        # self.request_mock.request = Mock(return_value=MockResponse())

    def tearDown(self):
        RequestClient._session = None

    def load_request_response(self, status_code=200, response_body='{}', raise_for_status=False):
        """
        Load the repsonse body from the given payload
        """
        mock_response = MockResponse(raise_for_status=raise_for_status)
        if is_p3k():
            mock_response.raw = BytesIO(bytes(response_body, 'utf-8'))
        else:
            mock_response.raw = BytesIO(response_body)
        mock_response.status_code = status_code

        self.request_mock.request = Mock(return_value=mock_response)

    def arm_requests_to_raise(self):
        """
        Arm the mocked request to raise for status.
        """
        self.request_mock.request = Mock(return_value=MockResponse(raise_for_status=True))

    def get_request_data(self):
        """
        Returns JSON formatted data from the submitted `requests`.
        """
        _, kwargs = self.request_mock.call_args()
        return json.loads(kwargs['data'])

    def request_called_with(self, method, url, data=None, params=None):
        (req_method, req_url), others = self.request_mock.call_args()
        self.assertEqual(method, req_method, req_method)
        self.assertEqual(url, req_url, req_url)

        if data:
            self.assertIn('data', others)
            others_data = json.loads(others['data'])
            self.assertEqual(data, others_data, others['data'])

        if params:
            self.assertIn('params', others)
            for (k, v) in iteritems(params):
                self.assertIn(k, others['params'], others['params'])
                self.assertEqual(v, others['params'][k])

    def assertIn(self, first, second, msg=None):
        msg = msg or "{0} not in {1}".format(first, second)
        self.assertTrue(first in second, msg)


class DatadogAPINoInitialization(DatadogAPITestCase):
    def tearDown(self):
        super(DatadogAPINoInitialization, self).tearDown()
        # Restore default values
        api._api_key = None
        api._application_key = None
        api._api_host = None
        api._host_name = None
        api._proxies = None

    def setUp(self):
        super(DatadogAPINoInitialization, self).setUp()
        api._api_key = api._application_key = api._host_name = api._api_host = None


class DatadogAPIWithInitialization(DatadogAPITestCase):
    def setUp(self):
        super(DatadogAPIWithInitialization, self).setUp()
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

    def tearDown(self):
        super(DatadogAPIWithInitialization, self).tearDown()
        # Restore default values
        api._api_key = None
        api._application_key = None
        api._api_host = None
        api._host_name = None
        api._proxies = None
