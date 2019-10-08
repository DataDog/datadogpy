import os
from datadog import api as dog
from datadog import initialize

TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
API_KEY = os.environ.get("DD_TEST_CLIENT_API_KEY", "a" * 32)
APP_KEY = os.environ.get("DD_TEST_CLIENT_APP_KEY", "a" * 40)
API_HOST = os.environ.get("DATADOG_HOST")
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}

class TestAzureIntegration:

    test_tenant_name = "testc44-1234-5678-9101-cc00736ftest"
    test_client_id = "testc7f6-1234-5678-9101-3fcbf464test"
    test_client_secret = "testingx./Sw*g/Y33t..R1cH+hScMDt"
    test_new_tenant_name = "1234abcd-1234-5678-9101-abcd1234abcd"
    test_new_client_id = "abcd1234-5678-1234-5678-1234abcd5678"
    not_yet_installed_error = 'Azure Integration not yet installed.'

    @classmethod
    def setup_class(cls):
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

    def test_azure_create(self):
        output = dog.Azure.create(
            tenant_name=self.test_tenant_name,
            host_filters="api:test",
            client_id=self.test_client_id,
            client_secret=self.test_client_secret
        )
        assert output == {}

    def test_azure_list(self):
        tests_pass = False
        for i in dog.Azure.list():
            if ( i['tenant_name'] == self.test_tenant_name and
                 i['host_filters'] == 'api:test' ):
                tests_pass = True
        assert tests_pass

    def test_azure_update_host_filters(self):
        dog.Azure.update_host_filters(
            tenant_name=self.test_tenant_name,
            host_filters='api:test2',
            client_id=self.test_client_id
        )
        tests_pass = False
        for i in dog.Azure.list():
            if i['host_filters'] == 'api:test2':
                tests_pass = True
        assert tests_pass

    def test_azure_update(self):
        dog.Azure.update(
            tenant_name=self.test_tenant_name,
            new_tenant_name=self.test_new_tenant_name,
            host_filters="api:test3",
            client_id=self.test_client_id,
            new_client_id=self.test_new_client_id,
            client_secret=self.test_client_secret
        )
        tests_pass = False
        for i in dog.Azure.list():
            if ( i['tenant_name'] == self.test_new_tenant_name and
                 i['host_filters'] == 'api:test3' ):
                tests_pass = True
        assert tests_pass

    def test_azure_delete(self):
        dog.Azure.delete(
            tenant_name=self.test_new_tenant_name,
            client_id=self.test_new_client_id
        )
        tests_pass = True
        list_output = dog.Azure.list()
        if type(list_output) == list:
            for i in dog.Azure.list():
                if i['tenant_name'] == self.test_new_tenant_name:
                    tests_pass = False
        elif self.not_yet_installed_error in list_output['errors'][0]:
            pass
        assert tests_pass
