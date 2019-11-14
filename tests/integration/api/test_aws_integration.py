from datadog import api as dog
from datadog import initialize
from tests.integration.api.constants import API_KEY, APP_KEY, API_HOST

TEST_ACCOUNT_ID_1 = "123456789101"
TEST_ACCOUNT_ID_2 = "123456789102"
TEST_ACCOUNT_ID_3 = "123456789103"
TEST_ACCOUNT_ID_4 = "123456789104"
TEST_ROLE_NAME = "DatadogApiTestRole"
TEST_ROLE_NAME_2 = "DatadogApiTestRolo"
AVAILABLE_NAMESPACES = 76


class TestAwsIntegration:

    @classmethod
    def setup_class(cls):
        """ setup any state tied to the execution of the class. called at class
        level before and after all test methods of the class are called.
        """
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

    def test_create(self):
        output = dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_3,
            role_name=TEST_ROLE_NAME,
            host_tags=["api:test"],
            filter_tags=["filter:test"],
            account_specific_namespace_rules={'auto_scaling': False, 'opsworks': False}
        )
        try:
            assert "external_id" in output
        finally:
            dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_3, role_name=TEST_ROLE_NAME)

    def test_list(self):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_1,
            role_name=TEST_ROLE_NAME
        )
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        output = dog.AwsIntegration.list()
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
        dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_1, role_name=TEST_ROLE_NAME)
        dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_2, role_name=TEST_ROLE_NAME)

    def test_delete(self):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_1,
            role_name=TEST_ROLE_NAME
        )
        output = dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_1, role_name=TEST_ROLE_NAME)
        assert output == {}

    def test_generate_new_external_id(self):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        output = dog.AwsIntegration.generate_new_external_id(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        assert "external_id" in output
        dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_2, role_name=TEST_ROLE_NAME)

    def test_list_namespace_rules(self):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        output = dog.AwsIntegration.list_namespace_rules(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        assert len(output) >= AVAILABLE_NAMESPACES
        dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_2, role_name=TEST_ROLE_NAME)

    def test_update(self):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        dog.AwsIntegration.update(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME,
            new_account_id=TEST_ACCOUNT_ID_4,
            host_tags=["api:test2"],
            new_role_name=TEST_ROLE_NAME_2
        )
        output = dog.AwsIntegration.list()
        tests_pass = False
        for i in output['accounts']:
            if i.get('account_id') == TEST_ACCOUNT_ID_4 and i.get('role_name') == TEST_ROLE_NAME_2:
                tests_pass = True
        assert tests_pass
        dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_4, role_name=TEST_ROLE_NAME_2)
