# stdlib
import unittest

# 3p
from mock import patch, Mock
import requests

# datadog
from datadog import initialize, api
from datadog.api.base import CreateableAPIResource, UpdatableAPIResource, DeletableAPIResource,\
    GetableAPIResource, ListableAPIResource, ActionAPIResource
from datadog.api.exceptions import ApiError
from datadog.util.compat import iteritems, json


API_KEY = "apikey"
APP_KEY = "applicationkey"
API_HOST = "host"
HOST_NAME = "agent.hostname"
FAKE_PROXY = {
    "https": "http://user:pass@10.10.1.10:3128/",
}


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
    _class_url = '/creatables'


class MyUpdatable(UpdatableAPIResource):
    _class_url = '/updatables'


class MyGetable(GetableAPIResource):
    _class_url = '/getables'


class MyListable(ListableAPIResource):
    _class_url = '/listables'


class MyDeletable(DeletableAPIResource):
    _class_url = '/deletables'


class MyActionable(ActionAPIResource):
    _class_url = '/actionables'

    @classmethod
    def trigger_class_action(cls, method, name, id=None, **params):
        super(MyActionable, cls)._trigger_class_action(method, name, id, **params)

    @classmethod
    def trigger_action(cls, method, name, id=None, **params):
        super(MyActionable, cls)._trigger_action(method, name, id, **params)


# Test classes
class DatadogAPITestCase(unittest.TestCase):

    def setUp(self):
        # Mock patch requests
        self.request_patcher = patch('requests.Session')
        request_class_mock = self.request_patcher.start()
        self.request_mock = request_class_mock.return_value
        self.request_mock.request = Mock(return_value=MockResponse())

    def tearDown(self):
        self.request_patcher.stop()

    def arm_requests_to_raise(self):
        """
        Arm the mocked request to raise for status.
        """
        self.request_mock.request = Mock(return_value=MockResponse(raise_for_status=True))

    def get_request_data(self):
        """
        Returns JSON formatted data from the submitted `requests`.
        """
        _, kwargs = self.request_mock.request.call_args
        return json.loads(kwargs['data'])

    def request_called_with(self, method, url, data=None, params=None):
        (req_method, req_url), others = self.request_mock.request.call_args
        self.assertEquals(method, req_method, req_method)
        self.assertEquals(url, req_url, req_url)

        if data:
            self.assertIn('data', others)
            self.assertEquals(json.dumps(data), others['data'], others['data'])

        if params:
            self.assertIn('params', others)
            for (k, v) in iteritems(params):
                self.assertIn(k, others['params'], others['params'])
                self.assertEquals(v, others['params'][k])

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


class DatadogAPIWithInitialization(DatadogAPITestCase):
    def setUp(self):
        super(DatadogAPIWithInitialization, self).setUp()
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
