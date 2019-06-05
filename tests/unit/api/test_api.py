# stdlib
from copy import deepcopy
from functools import wraps
import os
import tempfile
from time import time

# 3p
import mock

# datadog
from datadog import initialize, api, util
from datadog.api import (
    Distribution,
    Metric,
    ServiceCheck
)
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
    FAKE_PROXY
)


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
        self.assertEqual(self.request_mock.call_count(), 1)

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
        self.assertEqual(api._host_name, HOST_NAME, api._host_name)

    def test_request_parameters(self):
        """
        API parameters are set with `initialize` method.
        """
        # Test API, application keys, API host, and some HTTP client options
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

        # Make a simple API call
        MyCreatable.create()

        _, options = self.request_mock.call_args()

        # Assert `requests` parameters
        self.assertIn('params', options)

        self.assertIn('api_key', options['params'])
        self.assertEqual(options['params']['api_key'], API_KEY)
        self.assertIn('application_key', options['params'])
        self.assertEqual(options['params']['application_key'], APP_KEY)

        self.assertIn('headers', options)
        self.assertEqual(options['headers'], {'Content-Type': 'application/json'})

    def test_initialize_options(self):
        """
        HTTP client and API options are set with `initialize` method.
        """
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST,
                   proxies=FAKE_PROXY, cacert=False)

        # Make a simple API call
        MyCreatable.create()

        _, options = self.request_mock.call_args()

        # Assert `requests` parameters
        self.assertIn('proxies', options)
        self.assertEqual(options['proxies'], FAKE_PROXY)

        self.assertIn('verify', options)
        self.assertEqual(options['verify'], False)

        # Arm the `requests` to raise
        self.arm_requests_to_raise()

        # No exception should be raised (mute=True by default)
        MyCreatable.create()

        # Repeat with mute to False
        initialize(api_key=API_KEY, mute=False)
        self.assertRaises(ApiError, MyCreatable.create)

    def test_default_values(self):
        initialize()

        self.assertIsNone(api._api_key)
        self.assertIsNone(api._application_key)
        self.assertEqual(api._api_host, "https://api.datadoghq.com")
        self.assertEqual(api._host_name, util.hostname.get_hostname())

    def test_env_var_values(self):
        os.environ["DATADOG_API_KEY"] = "API_KEY_ENV"
        os.environ["DATADOG_APP_KEY"] = "APP_KEY_ENV"
        os.environ["DATADOG_HOST"] = "HOST_ENV"

        initialize()

        self.assertEqual(api._api_key, "API_KEY_ENV")
        self.assertEqual(api._application_key, "APP_KEY_ENV")
        self.assertEqual(api._api_host, "HOST_ENV")
        self.assertEqual(api._host_name, util.hostname.get_hostname())

        del os.environ["DATADOG_API_KEY"]
        del os.environ["DATADOG_APP_KEY"]
        del os.environ["DATADOG_HOST"]

        os.environ["DD_API_KEY"] = "API_KEY_ENV_DD"
        os.environ["DD_APP_KEY"] = "APP_KEY_ENV_DD"
        api._api_key = None
        api._application_key = None

        initialize()

        self.assertEqual(api._api_key, "API_KEY_ENV_DD")
        self.assertEqual(api._application_key, "APP_KEY_ENV_DD")

    def test_function_param_value(self):
        initialize(api_key="API_KEY", app_key="APP_KEY", api_host="HOST", host_name="HOSTNAME")

        self.assertEqual(api._api_key, "API_KEY")
        self.assertEqual(api._application_key, "APP_KEY")
        self.assertEqual(api._api_host, "HOST")
        self.assertEqual(api._host_name, "HOSTNAME")

    def test_precedence(self):
        # Initialize first with env vars
        os.environ["DATADOG_API_KEY"] = "API_KEY_ENV"
        os.environ["DATADOG_APP_KEY"] = "APP_KEY_ENV"
        os.environ["DATADOG_HOST"] = "HOST_ENV"

        initialize()

        self.assertEqual(api._api_key, "API_KEY_ENV")
        self.assertEqual(api._application_key, "APP_KEY_ENV")
        self.assertEqual(api._api_host, "HOST_ENV")
        self.assertEqual(api._host_name, util.hostname.get_hostname())

        # Initialize again to check given parameters take precedence over already set value and env vars
        initialize(api_key="API_KEY", app_key="APP_KEY", api_host="HOST", host_name="HOSTNAME")

        self.assertEqual(api._api_key, "API_KEY")
        self.assertEqual(api._application_key, "APP_KEY")
        self.assertEqual(api._api_host, "HOST")
        self.assertEqual(api._host_name, "HOSTNAME")

        # Initialize again without specifying attributes to check that already initialized value takes precedence
        initialize()

        self.assertEqual(api._api_key, "API_KEY")
        self.assertEqual(api._application_key, "APP_KEY")
        self.assertEqual(api._api_host, "HOST")
        self.assertEqual(api._host_name, "HOSTNAME")

        del os.environ["DATADOG_API_KEY"]
        del os.environ["DATADOG_APP_KEY"]
        del os.environ["DATADOG_HOST"]


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
        _, kwargs = self.request_mock.call_args()
        self.assertIsNone(kwargs["data"])

    def test_listable(self):
        """
        Listable resource logic.
        """
        MyListable.get_all(otherparam="val")
        self.request_called_with('GET', "host/api/v1/listables", params={'otherparam': "val"})
        _, kwargs = self.request_mock.call_args()
        self.assertIsNone(kwargs["data"])

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
        _, kwargs = self.request_mock.call_args()
        self.assertIsNone(kwargs["data"])

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
            params={'param1': 'val1', 'param2': 'val2'}
        )
        _, kwargs = self.request_mock.call_args()
        self.assertIsNone(kwargs["data"])

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

        MyActionable.trigger_action(
            'GET',
            'actionname',
            id=actionable_object_id,
        )
        self.request_called_with(
            'GET',
            'host/api/v1/actionname/{0}'.format(actionable_object_id)
        )
        _, kwargs = self.request_mock.call_args()
        self.assertIsNone(kwargs["data"])


class TestMetricResource(DatadogAPIWithInitialization):

    def submit_and_assess_metric_payload(self, serie, attach_host_name=True):
        """
        Helper to assess the metric payload format.
        """
        now = time()

        if isinstance(serie, dict):
            Metric.send(attach_host_name=attach_host_name, **deepcopy(serie))
            serie = [serie]
        else:
            Metric.send(deepcopy(serie), attach_host_name=attach_host_name)

        payload = self.get_request_data()

        for i, metric in enumerate(payload['series']):
            if attach_host_name:
                self.assertEqual(set(metric.keys()), set(['metric', 'points', 'host']))
                self.assertEqual(metric['host'], api._host_name)
            else:
                self.assertEqual(set(metric.keys()), set(['metric', 'points']))

            self.assertEqual(metric['metric'], serie[i]['metric'])

            # points is a list of 1 point
            self.assertTrue(isinstance(metric['points'], list))
            self.assertEqual(len(metric['points']), 1)
            # it consists of a [time, value] pair
            self.assertEqual(len(metric['points'][0]), 2)
            # its value == value we sent
            self.assertEqual(metric['points'][0][1], float(serie[i]['points']))
            # it's time not so far from current time
            assert now - 1 < metric['points'][0][0] < now + 1

    def submit_and_assess_dist_payload(self, serie, attach_host_name=True):
        """
        Helper to assess the metric payload format.
        """
        now = time()

        if isinstance(serie, dict):
            Distribution.send(attach_host_name=attach_host_name, **deepcopy(serie))
            serie = [serie]
        else:
            Distribution.send(deepcopy(serie), attach_host_name=attach_host_name)

        payload = self.get_request_data()

        for i, metric in enumerate(payload['series']):
            if attach_host_name:
                self.assertEqual(set(metric.keys()), set(['metric', 'points', 'host']))
                self.assertEqual(metric['host'], api._host_name)
            else:
                self.assertEqual(set(metric.keys()), set(['metric', 'points']))

            self.assertEqual(metric['metric'], serie[i]['metric'])

            # points is a list of 1 point
            self.assertTrue(isinstance(metric['points'], list))
            self.assertEqual(len(metric['points']), 1)
            # it consists of a [time, value] pair
            self.assertEqual(len(metric['points'][0]), 2)
            # its value == value we sent
            self.assertEqual(metric['points'][0][1], serie[i]['points'][0][1])
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

        # Single point no hostname
        serie = dict(metric='metric.1', points=13)
        self.submit_and_assess_metric_payload(serie, attach_host_name=False)

        # Multiple point no hostname
        serie = [dict(metric='metric.1', points=13),
                 dict(metric='metric.2', points=19)]
        self.submit_and_assess_metric_payload(serie, attach_host_name=False)

    def test_dist_points_submission(self):
        """
        Assess the distribution data payload format, when submitting a single or multiple points.
        """
        # Single point
        serie = dict(metric='metric.1', points=[[time(), [13]]])
        self.submit_and_assess_dist_payload(serie)

        # Multiple point
        serie = [dict(metric='metric.1', points=[[time(), [13]]]),
                 dict(metric='metric.2', points=[[time(), [19]]])]
        self.submit_and_assess_dist_payload(serie)

        # Single point no hostname
        serie = dict(metric='metric.1', points=[[time(), [13]]])
        self.submit_and_assess_dist_payload(serie, attach_host_name=False)

        # Multiple point no hostname
        serie = [dict(metric='metric.1', points=[[time(), [13]]]),
                 dict(metric='metric.2', points=[[time(), [19]]])]
        self.submit_and_assess_dist_payload(serie, attach_host_name=False)

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
