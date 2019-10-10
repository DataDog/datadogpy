import os
from datadog import api as dog
from datadog import initialize

API_KEY = os.environ.get("DD_TEST_CLIENT_API_KEY", "a" * 32)
APP_KEY = os.environ.get("DD_TEST_CLIENT_APP_KEY", "a" * 40)
API_HOST = os.environ.get("DATADOG_HOST")
TEST_ACCOUNT_ID_1 = "123456789101"
TEST_ACCOUNT_ID_2 = "123456789102"
TEST_ACCOUNT_ID_3 = "123456789103"
TEST_ACCOUNT_ID_4 = "123456789104"
TEST_ROLE_NAME = "DatadogApiTestRole"
TEST_ROLE_NAME_2 = "DatadogApiTestRolo"


class TestAwsIntegration:

    @classmethod
    def setup_class(cls):
        """ setup any state tied to the execution of the class. called at class
        level before and after all test methods of the class are called.
        """
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
        dog.Aws.create(
            account_id=TEST_ACCOUNT_ID_1,
            role_name=TEST_ROLE_NAME
        )
        dog.Aws.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a setup_method
        call.
        """
        dog.Aws.delete(account_id=TEST_ACCOUNT_ID_1, role_name=TEST_ROLE_NAME)
        dog.Aws.delete(account_id=TEST_ACCOUNT_ID_4, role_name=TEST_ROLE_NAME_2)

    def test_create(self):
        output = dog.Aws.create(
            account_id=TEST_ACCOUNT_ID_3,
            role_name=TEST_ROLE_NAME,
            host_tags=["api:test"],
            filter_tags=["filter:test"],
            account_specific_namespace_rules={'auto_scaling': False, 'opsworks': False}
        )
        try:
            assert "external_id" in output
        finally:
            dog.Aws.delete(account_id=TEST_ACCOUNT_ID_3, role_name=TEST_ROLE_NAME)

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
        output = dog.Aws.delete(account_id=TEST_ACCOUNT_ID_1, role_name=TEST_ROLE_NAME)
        assert output == {}

    def test_generate_new_external_id(self):
        output = dog.Aws.generate_new_external_id(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        assert "external_id" in output

    def test_list_namespace_rules(self):
        output = dog.Aws.list_namespace_rules(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        assert len(output) >= 76

    def test_update(self):
        dog.Aws.update(
            existing_account_id=TEST_ACCOUNT_ID_2,
            existing_role_name=TEST_ROLE_NAME,
            account_id=TEST_ACCOUNT_ID_4,
            host_tags=["api:test2"],
            role_name=TEST_ROLE_NAME_2
        )
        output = dog.Aws.list()
        tests_pass = False
        for i in output['accounts']:
            if i['account_id'] == TEST_ACCOUNT_ID_4 and i['role_name'] == TEST_ROLE_NAME_2:
                tests_pass = True
        assert tests_pass
