# stdlib
from copy import deepcopy
from functools import wraps
import os
import tempfile
from time import time

# 3p
import mock

# datadog
from datadog import initialize, api
from datadog.api import Metric, ServiceCheck
from datadog.api.exceptions import ApiError, ApiNotInitialized
from datadog.util.compat import is_p3k
from tests.unit.api.helper import (
    DatadogAPIWithInitialization,
    DatadogAPINoInitialization,
    MyCreatable,
    MyUpdatable,
    MyDeletable,
    MyGetable,
    MyListable,
    MyListableSubResource,
    MyAddableSubResource,
    MyUpdatableSubResource,
    MyDeletableSubResource,
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

    def test_no_initialization_fails(self):
        """
        Raise ApiNotInitialized exception when `initialize` has not ran or no API key was set.
        """
        self.assertRaises(ApiNotInitialized, MyCreatable.create)

        # No API key => only stats in statsd mode should work
        initialize()
        api._api_key = None
        self.assertRaises(ApiNotInitialized, MyCreatable.create)

        # Finally, initialize with an API key
        initialize(api_key=API_KEY, api_host=API_HOST)
        MyCreatable.create()
        self.assertEquals(self.request_mock.request.call_count, 1)

    @mock.patch('datadog.util.config.get_config_path')
    def test_get_hostname(self, mock_config_path):
        """
        API hostname parameter fallback with Datadog Agent hostname when available.
        """
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
        self.assertEquals(api._host_name, HOST_NAME, api._host_name)

    def test_request_parameters(self):
        """
        API parameters are set with `initialize` method.
        """
        # Test API, application keys, API host, and some HTTP client options
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

        # Make a simple API call
        MyCreatable.create()

        _, options = self.request_mock.request.call_args

        # Assert `requests` parameters
        self.assertIn('params', options)

        self.assertIn('api_key', options['params'])
        self.assertEquals(options['params']['api_key'], API_KEY)
        self.assertIn('application_key', options['params'])
        self.assertEquals(options['params']['application_key'], APP_KEY)

        self.assertIn('headers', options)
        self.assertEquals(options['headers'], {'Content-Type': 'application/json'})

    def test_initialize_options(self):
        """
        HTTP client and API options are set with `initialize` method.
        """
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST,
                   proxies=FAKE_PROXY, cacert=False)

        # Make a simple API call
        MyCreatable.create()

        _, options = self.request_mock.request.call_args

        # Assert `requests` parameters
        self.assertIn('proxies', options)
        self.assertEquals(options['proxies'], FAKE_PROXY)

        self.assertIn('verify', options)
        self.assertEquals(options['verify'], False)

        # Arm the `requests` to raise
        self.arm_requests_to_raise()

        # No exception should be raised (mute=True by default)
        MyCreatable.create()

        # Repeat with mute to False
        initialize(api_key=API_KEY, mute=False)
        self.assertRaises(ApiError, MyCreatable.create)

    def test_initialization_from_env(self):
        """
        Set API parameters in `initialize` from environment variables.
        """
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
        test_api_params_default("DATADOG_HOST", "_api_host", "https://api.datadoghq.com")

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
        """
        Creatable resource logic.
        """
        MyCreatable.create(mydata="val")
        self.request_called_with('POST', "host/api/v1/creatables", data={'mydata': "val"})

        MyCreatable.create(mydata="val", attach_host_name=True)
        self.request_called_with('POST', "host/api/v1/creatables",
                                 data={'mydata': "val", 'host': api._host_name})

    def test_getable(self):
        """
        Getable resource logic.
        """
        getable_object_id = 123
        MyGetable.get(getable_object_id, otherparam="val")
        self.request_called_with('GET', "host/api/v1/getables/" + str(getable_object_id),
                                 params={'otherparam': "val"})

    def test_listable(self):
        """
        Listable resource logic.
        """
        MyListable.get_all(otherparam="val")
        self.request_called_with('GET', "host/api/v1/listables", params={'otherparam': "val"})

    def test_updatable(self):
        """
        Updatable resource logic.
        """
        updatable_object_id = 123
        MyUpdatable.update(updatable_object_id, params={'myparam': "val1"}, mydata="val2")
        self.request_called_with('PUT', "host/api/v1/updatables/" + str(updatable_object_id),
                                 params={'myparam': "val1"}, data={'mydata': "val2"})

    def test_detalable(self):
        """
        Deletable resource logic.
        """
        deletable_object_id = 123
        MyDeletable.delete(deletable_object_id, otherparam="val")
        self.request_called_with('DELETE', "host/api/v1/deletables/" + str(deletable_object_id),
                                 params={'otherparam': "val"})

    def test_listable_sub_resources(self):
        """
        Listable sub-resources logic.
        """
        resource_id = 123
        MyListableSubResource.get_items(resource_id, otherparam="val")
        self.request_called_with(
            'GET',
            'host/api/v1/resource_name/{0}/sub_resource_name'.format(resource_id),
            params={'otherparam': "val"}
        )

    def test_addable_sub_resources(self):
        """
        Addable sub-resources logic.
        """
        resource_id = 123
        MyAddableSubResource.add_items(resource_id, params={'myparam': 'val1'}, mydata='val2')
        self.request_called_with(
            'POST',
            'host/api/v1/resource_name/{0}/sub_resource_name'.format(resource_id),
            params={'myparam': 'val1'},
            data={'mydata': 'val2'}
        )

    def test_updatable_sub_resources(self):
        """
        Updatable sub-resources logic.
        """
        resource_id = 123
        MyUpdatableSubResource.update_items(resource_id, params={'myparam': 'val1'}, mydata='val2')
        self.request_called_with(
            'PUT',
            'host/api/v1/resource_name/{0}/sub_resource_name'.format(resource_id),
            params={'myparam': 'val1'},
            data={'mydata': 'val2'}
        )

    def test_deletable_sub_resources(self):
        """
        Deletable sub-resources logic.
        """
        resource_id = 123
        MyDeletableSubResource.delete_items(resource_id, params={'myparam': 'val1'}, mydata='val2')
        self.request_called_with(
            'DELETE',
            'host/api/v1/resource_name/{0}/sub_resource_name'.format(resource_id),
            params={'myparam': 'val1'},
            data={'mydata': 'val2'}
        )

    def test_actionable(self):
        """
        Actionable resource logic.
        """
        actionable_object_id = 123
        MyActionable.trigger_class_action(
            'POST',
            'actionname',
            id=actionable_object_id,
            params={'myparam': 'val1'},
            mydata='val',
            mydata2='val2'
        )
        self.request_called_with(
            'POST',
            'host/api/v1/actionables/{0}/actionname'.format(str(actionable_object_id)),
            params={'myparam': 'val1'},
            data={'mydata': 'val', 'mydata2': 'val2'}
        )

        MyActionable.trigger_class_action(
            'POST',
            'actionname',
            id=actionable_object_id,
            mydata='val',
            mydata2='val2'
        )
        self.request_called_with(
            'POST',
            'host/api/v1/actionables/{0}/actionname'.format(str(actionable_object_id)),
            params={},
            data={'mydata': 'val', 'mydata2': 'val2'}
        )

        MyActionable.trigger_class_action(
            'GET',
            'actionname',
            id=actionable_object_id,
            params={'param1': 'val1', 'param2': 'val2'}
        )
        self.request_called_with(
            'GET',
            'host/api/v1/actionables/{0}/actionname'.format(str(actionable_object_id)),
            params={'param1': 'val1', 'param2': 'val2'},
            data={}
        )

        MyActionable.trigger_action(
            'POST',
            'actionname',
            id=actionable_object_id,
            mydata="val"
        )
        self.request_called_with(
            'POST',
            'host/api/v1/actionname/{0}'.format(actionable_object_id),
            data={'mydata': "val"}
        )


class TestMetricResource(DatadogAPIWithInitialization):

    def submit_and_assess_metric_payload(self, serie):
        """
        Helper to assess the metric payload format.
        """
        now = time()

        if isinstance(serie, dict):
            Metric.send(**deepcopy(serie))
            serie = [serie]
        else:
            Metric.send(deepcopy(serie))

        payload = self.get_request_data()

        for i, metric in enumerate(payload['series']):
            self.assertEquals(set(metric.keys()), set(['metric', 'points', 'host']))

            self.assertEquals(metric['metric'], serie[i]['metric'])
            self.assertEquals(metric['host'], api._host_name)

            # points is a list of 1 point
            self.assertTrue(isinstance(metric['points'], list))
            self.assertEquals(len(metric['points']), 1)
            # it consists of a [time, value] pair
            self.assertEquals(len(metric['points'][0]), 2)
            # its value == value we sent
            self.assertEquals(metric['points'][0][1], float(serie[i]['points']))
            # it's time not so far from current time
            assert now - 1 < metric['points'][0][0] < now + 1

    def test_metric_submit_query_switch(self):
        """
        Endpoints are different for submission and queries.
        """
        Metric.send(points=(123, 456))
        self.request_called_with('POST', "host/api/v1/series",
                                 data={'series': [{'points': [[123, 456.0]], 'host': api._host_name}]})

        Metric.query(start="val1", end="val2")
        self.request_called_with('GET', "host/api/v1/query",
                                 params={'from': "val1", 'to': "val2"})

    def test_points_submission(self):
        """
        Assess the data payload format, when submitting a single or multiple points.
        """
        # Single point
        serie = dict(metric='metric.1', points=13)
        self.submit_and_assess_metric_payload(serie)

        # Multiple point
        serie = [dict(metric='metric.1', points=13),
                 dict(metric='metric.2', points=19)]
        self.submit_and_assess_metric_payload(serie)

    def test_data_type_support(self):
        """
        `Metric` API supports `real` numerical data types.
        """
        from decimal import Decimal
        from fractions import Fraction

        m_long = int(1)  # long in Python 3.x

        if not is_p3k():
            m_long = long(1)

        supported_data_types = [1, 1.0, m_long, Decimal(1), Fraction(1, 2)]

        for point in supported_data_types:
            serie = dict(metric='metric.numerical', points=point)
            self.submit_and_assess_metric_payload(serie)

class TestServiceCheckResource(DatadogAPIWithInitialization):

    def test_service_check_supports_none_parameters(self):
        """
        ServiceCheck should support none parameters

        ```
        $ dog service_check check check_pg host0 1
        ```

        resulted in `RuntimeError: dictionary changed size during iteration`
        """
        ServiceCheck.check(
            check='check_pg', host_name='host0', status=1, message=None,
            timestamp=None, tags=None)
