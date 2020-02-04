# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

import pytest


class TestGcpIntegration:

    test_project_id = "datadog-apitest"
    test_client_email = "api-dev@datadog-sandbox.iam.gserviceaccount.com"

    @pytest.fixture(autouse=True)  # TODO , scope="class"
    def gcp_integration(self, dog):
        """Prepare GCP Integration."""
        yield
        # Should be deleted as part of the test
        # but cleanup here if test fails
        dog.GcpIntegration.delete(
            project_id=self.test_project_id,
            client_email=self.test_client_email
        )

    def test_gcp_crud(self, dog):
        # Test Create
        create_output = dog.GcpIntegration.create(
            type="service_account",
            project_id=self.test_project_id,
            private_key_id="fake_private_key_id",
            private_key="fake_key",
            client_email=self.test_client_email,
            client_id="123456712345671234567",
            auth_uri="fake_uri",
            token_uri="fake_uri",
            auth_provider_x509_cert_url="fake_url",
            client_x509_cert_url="fake_url",
            host_filters="api:test"
        )
        assert create_output == {}
        # Test Update
        dog.GcpIntegration.update(
            project_id=self.test_project_id,
            client_email=self.test_client_email,
            host_filters="api:test2",
            automute=True
        )
        update_tests_pass = False
        for i in dog.GcpIntegration.list():
            if (i['project_id'] == self.test_project_id and
                    i['host_filters'] == 'api:test2' and
                    i['automute'] is True):
                update_tests_pass = True
        assert update_tests_pass
        # Test List
        list_tests_pass = False
        for i in dog.GcpIntegration.list():
            if (i['project_id'] == self.test_project_id and
                    i['host_filters'] == 'api:test2' and
                    i['automute'] is True):
                list_tests_pass = True
        assert list_tests_pass
        # Test Delete
        delete_output = dog.GcpIntegration.delete(
            project_id=self.test_project_id,
            client_email=self.test_client_email
        )
        assert delete_output == {}
