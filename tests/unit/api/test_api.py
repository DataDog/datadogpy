# stdlib
import os
import tempfile
import time

# 3p
import mock
from nose.tools import assert_raises, assert_true, assert_false

# datadog
from datadog import initialize, api, stats
from datadog.util.compat import is_p3k
from datadog.api.exceptions import ApiNotInitialized
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


class TestInitialization(DatadogAPINoInitialization):

    def test_no_initialization_fails(self):
        assert_raises(ApiNotInitialized, MyCreatable.create)
        assert_true(stats._disabled)

        # No API key => only stats in statsd mode should work
        initialize()
        assert_false(stats._disabled)
        assert_false(stats._needs_flush)
        assert_raises(ApiNotInitialized, MyCreatable.create)

        # Make sure stats in HTTP API mode raises too
        initialize(statsd=False, flush_in_thread=False)
        stats.increment("IWillRaiseAnException")
        assert_raises(ApiNotInitialized, stats.flush, int(time.time()) + 60)
        stats.event("IAmATitle", "IWillRaiseAnException")
        assert_raises(ApiNotInitialized, stats.flush, int(time.time()) + 60)

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
