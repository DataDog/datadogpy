import os
from datadog import api as dog
from datadog import initialize

TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
API_KEY = os.environ.get("DD_TEST_CLIENT_API_KEY", "a" * 32)
APP_KEY = os.environ.get("DD_TEST_CLIENT_APP_KEY", "a" * 40)
API_HOST = os.environ.get("DATADOG_HOST")
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}


class TestAwsIntegration:

    @classmethod
    def setup_class(cls):
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

    def setup_method(self, method):
        """ setup any state tied to the execution of the given method in a
        class.  setup_method is invoked for every test method of a class.
        """
        dog.Aws.create(
            account_id="123456789101",
            role_name="DatadogApiTestRole"
        )
        dog.Aws.create(
            account_id="123456789102",
            role_name="DatadogApiTestRole"
        )

    def teardown_method(self, method):
        """ teardown any state that was previously setup with a setup_method
        call.
        """
        dog.Aws.delete(account_id="123456789101", role_name="DatadogApiTestRole")
        dog.Aws.delete(account_id="123456789106", role_name="DatadogApiTestRolo")

    def test_create(self):
        output = dog.Aws.create(
            account_id="123456789103",
            role_name="DatadogApiTestRole",
            host_tags=["api:test"]
        )
        assert "external_id" in output
        dog.Aws.delete(account_id="123456789103", role_name="DatadogApiTestRole")

    def test_list(self):
        output = dog.Aws.list()
        assert "accounts" in output
        assert len(output['accounts']) >= 2
        expected_fields = [
            'errors',
            'filter_tags',
            'host_tags',
            'account_specific_namespace_rules',
            'role_name',
            'account_id'
        ]
        assert all(k in output['accounts'][0].keys() for k in expected_fields)

    def test_delete(self):
        output = dog.Aws.delete(account_id="123456789101", role_name="DatadogApiTestRole")
        assert output == {}

    def test_generate_new_external_id(self):
        output = dog.Aws.generate_new_external_id(
            account_id="123456789102",
            role_name="DatadogApiTestRole"
        )
        assert "external_id" in output

    def test_list_namespace_rules(self):
        output = dog.Aws.list_namespace_rules(
            account_id="123456789102",
            role_name="DatadogApiTestRole"
        )
        assert len(output) >= 76

    def test_update(self):
        dog.Aws.update(
            existing_account_id="123456789102",
            existing_role_name="DatadogApiTestRole",
            account_id="123456789106",
            host_tags=["api:test2"],
            role_name="DatadogApiTestRolo"
        )
        output = dog.Aws.list()
        tests_pass = False
        for i in output['accounts']:
            if i['account_id'] == '123456789106' and i['role_name'] == 'DatadogApiTestRolo':
                tests_pass = True
        assert tests_pass
