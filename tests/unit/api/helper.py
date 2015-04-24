# python
import unittest

# datadog
from datadog import initialize, api
from datadog.api.base import CreateableAPIResource, UpdatableAPIResource, DeletableAPIResource,\
    GetableAPIResource, ListableAPIResource, ActionAPIResource
from datadog.util.compat import iteritems, json

# 3p
import requests
from mock import patch, Mock

API_KEY = "apikey"
APP_KEY = "applicationkey"
API_HOST = "host"
HOST_NAME = "agent.hostname"
FAKE_PROXY = {
    "https": "http://user:pass@10.10.1.10:3128/",
}


class MockReponse(requests.Response):
    content = None

    def raise_for_status(self):
        pass


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
        self.request_mock.request = Mock(return_value=MockReponse())

    def request_called_with(self, method, url, data=None, params=None):
        (req_method, req_url), others = self.request_mock.request.call_args
        assert method == req_method, req_method
        assert url == req_url, req_url

        if data:
            assert 'data' in others
            assert json.dumps(data) == others['data'], others['data']

        if params:
            assert 'params' in others
            for (k, v) in iteritems(params):
                assert k in others['params'], others['params']
                assert v == others['params'][k]

    def tearDown(self):
        self.request_patcher.stop()


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
