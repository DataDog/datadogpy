import os
from datadog import api as dog
from datadog import initialize

TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
API_KEY = os.environ.get("DD_TEST_CLIENT_API_KEY", "a" * 32)
APP_KEY = os.environ.get("DD_TEST_CLIENT_APP_KEY", "a" * 40)
API_HOST = os.environ.get("DATADOG_HOST")
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}


class TestGcpIntegration:

    test_project_id = "datadog-apitest"
    test_client_email = "api-dev@datadog-sandbox.iam.gserviceaccount.com"

    @classmethod
    def setup_class(cls):
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

    def test_gcp_create(self):
        output = dog.Gcp.create(
            type="service_account",
            project_id=self.test_project_id,
            private_key_id="123456789abcdefghi123456789abcdefghijklm",
            private_key="fake_key",
            client_email=self.test_client_email,
            client_id="123456712345671234567",
            auth_uri="fake_uri",
            token_uri="fake_uri",
            auth_provider_x509_cert_url="fake_url",
            client_x509_cert_url="fake_url",
            host_filters="api:test"
        )
        assert output == {}

    def test_gcp_update(self):
        dog.Gcp.update(
            project_id=self.test_project_id,
            client_email=self.test_client_email,
            host_filters="api:test2",
            automute=True
        )
        tests_pass = False
        for i in dog.Gcp.list():
            if (i['project_id'] == self.test_project_id and
                    i['host_filters'] == 'api:test2' and
                    i['automute'] is True):
                tests_pass = True
        assert tests_pass

    def test_gcp_list(self):
        tests_pass = False
        for i in dog.Gcp.list():
            if (i['project_id'] == self.test_project_id and
                    i['host_filters'] == 'api:test2' and
                    i['automute'] is True):
                tests_pass = True
        assert tests_pass

    def test_gcp_delete(self):
        output = dog.Gcp.delete(
            project_id=self.test_project_id,
            client_email=self.test_client_email
        )
        assert output == {}
