# stdlib
from functools import wraps
import os
import tempfile

# 3p
import mock
from nose.tools import assert_raises, assert_true, assert_false

# datadog
from datadog import initialize, api
from datadog.api import Metric
from datadog.api.exceptions import ApiNotInitialized
from datadog.util.compat import is_p3k
from tests.unit.api.helper import (
    DatadogAPIWithInitialization,
    DatadogAPINoInitialization,
    MyCreatable,
    MyUpdatable,
    MyDeletable,
    MyGetable,
    MyListable,
    MyActionable,
    API_KEY,
    APP_KEY,
    API_HOST,
    HOST_NAME,
    FAKE_PROXY)


def preserve_environ_datadog(func):
    """
    Decorator to preserve the original environment value.
    """
    @wraps(func)
    def wrapper(env_name, *args, **kwds):
        environ_api_param = os.environ.get(env_name)
        try:
            return func(env_name, *args, **kwds)
        finally:
            # restore the original environ value
            if environ_api_param:
                os.environ[env_name] = environ_api_param
            elif os.environ.get(env_name):
                del os.environ[env_name]

    return wrapper


class TestInitialization(DatadogAPINoInitialization):

    def test_no_initialization_fails(self, test='sisi'):
        assert_raises(ApiNotInitialized, MyCreatable.create)

        # No API key => only stats in statsd mode should work
        initialize()
        api._api_key = None
        assert_raises(ApiNotInitialized, MyCreatable.create)

        # Finally, initialize with an API key
        initialize(api_key=API_KEY, api_host=API_HOST)
        MyCreatable.create()
        assert self.request_mock.request.call_count == 1

    @mock.patch('datadog.util.config.get_config_path')
    def test_get_hostname(self, mock_config_path):
        # Generate a fake agent config
        tmpfilepath = os.path.join(tempfile.gettempdir(), "tmp-agentconfig")
        with open(tmpfilepath, "wb") as f:
            if is_p3k():
                f.write(bytes("[Main]\n", 'UTF-8'))
                f.write(bytes("hostname: {0}\n".format(HOST_NAME), 'UTF-8'))
            else:
                f.write("[Main]\n")
                f.write("hostname: {0}\n".format(HOST_NAME))
        # Mock get_config_path to return this fake agent config
        mock_config_path.return_value = tmpfilepath

        initialize()
        assert api._host_name == HOST_NAME, api._host_name

    def test_request_parameters(self):
        # Test API, application keys, API host and proxies
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST, proxies=FAKE_PROXY)

        # Make a simple API call
        MyCreatable.create()

        _, options = self.request_mock.request.call_args

        assert 'params' in options

        assert 'api_key' in options['params']
        assert options['params']['api_key'] == API_KEY
        assert 'application_key' in options['params']
        assert options['params']['application_key'] == APP_KEY

        assert 'proxies' in options
        assert options['proxies'] == FAKE_PROXY

        assert 'headers' in options
        assert options['headers'] == {'Content-Type': 'application/json'}

    def test_initialization_from_env(self):
        @preserve_environ_datadog
        def test_api_params_from_env(env_name, attr_name, env_value):
            """
            Set env_name environment variable to env_value
            Assert api.attr_name = env_value
            """
            os.environ[env_name] = env_value
            initialize()
            self.assertEquals(getattr(api, attr_name), env_value)

        @preserve_environ_datadog
        def test_api_params_default(env_name, attr_name, expected_value):
            """
            Unset env_name environment variable
            Assert api.attr_name = expected_value
            """
            if os.environ.get(env_name):
                del os.environ[env_name]
            initialize()
            self.assertEquals(getattr(api, attr_name), expected_value)

        @preserve_environ_datadog
        def test_api_params_from_params(env_name, parameter, attr_name, value ):
            """
            Unset env_name environment variable
            Initialize API with parameter=value
            Assert api.attr_name = value
            """
            if os.environ.get(env_name):
                del os.environ[env_name]
            initialize(api_host='http://localhost')
            self.assertEquals(api._api_host, 'http://localhost')

        # Default values
        test_api_params_default("DATADOG_API_KEY", "_api_key", None)
        test_api_params_default("DATADOG_APP_KEY", "_application_key", None)
        test_api_params_default("DATADOG_HOST", "_api_host", "https://app.datadoghq.com")

        # From environment
        test_api_params_from_env("DATADOG_API_KEY", "_api_key", env_value="apikey")
        test_api_params_from_env("DATADOG_APP_KEY", "_application_key", env_value="appkey")
        test_api_params_from_env("DATADOG_HOST", "_api_host", env_value="http://localhost")

        # From parameters
        test_api_params_from_params("DATADOG_API_KEY", "api_key", "_api_key", "apikey2")
        test_api_params_from_params("DATADOG_APP_KEY", "app_key", "_application_key", "appkey2")
        test_api_params_from_params("DATADOG_HOST", "api_host", "_api_host", "http://127.0.0.1")


class TestResources(DatadogAPIWithInitialization):

    def test_creatable(self):
        MyCreatable.create(mydata="val")
        self.request_called_with('POST', "host/api/v1/creatables", data={'mydata': "val"})

        MyCreatable.create(mydata="val", attach_host_name=True)
        self.request_called_with('POST', "host/api/v1/creatables",
                                 data={'mydata': "val", 'host': api._host_name})

    def test_getable(self):
        getable_object_id = 123
        MyGetable.get(getable_object_id, otherparam="val")
        self.request_called_with('GET', "host/api/v1/getables/" + str(getable_object_id),
                                 params={'otherparam': "val"})

    def test_listable(self):
        MyListable.get_all(otherparam="val")
        self.request_called_with('GET', "host/api/v1/listables", params={'otherparam': "val"})

    def test_updatable(self):
        updatable_object_id = 123
        MyUpdatable.update(updatable_object_id, params={'myparam': "val1"}, mydata="val2")
        self.request_called_with('PUT', "host/api/v1/updatables/" + str(updatable_object_id),
                                 params={'myparam': "val1"}, data={'mydata': "val2"})

    def test_detalable(self):
        deletable_object_id = 123
        MyDeletable.delete(deletable_object_id, otherparam="val")
        self.request_called_with('DELETE', "host/api/v1/deletables/" + str(deletable_object_id),
                                 params={'otherparam': "val"})

    def test_actionable(self):
        actionable_object_id = 123
        MyActionable.trigger_class_action('POST', "actionname", id=actionable_object_id,
                                          mydata="val")
        self.request_called_with('POST', "host/api/v1/actionables/" + str(actionable_object_id) +
                                 "/actionname", data={'mydata': "val"})

        MyActionable.trigger_action('POST', "actionname", id=actionable_object_id, mydata="val")
        self.request_called_with('POST', "host/api/v1/actionname/" + str(actionable_object_id),
                                 data={'mydata': "val"})

    def test_metric_submit_query_switch(self):
        """
        Specific to Metric subpackages: endpoints are different for submission and queries
        """
        Metric.send(points="val")
        self.request_called_with('POST', "host/api/v1/series",
                                 data={'series': [{'points': "val", 'host': api._host_name}]})

        Metric.query(start="val1", end="val2")
        self.request_called_with('GET', "host/api/v1/query",
                                 params={'from': "val1", 'to': "val2"})
