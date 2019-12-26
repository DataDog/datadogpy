# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from datadog import api as dog
from datadog import initialize
from tests.integration.api.constants import API_KEY, APP_KEY, API_HOST


class TestGcpIntegration:

    test_project_id = "datadog-apitest"
    test_client_email = "api-dev@datadog-sandbox.iam.gserviceaccount.com"

    @classmethod
    def setup_class(cls):
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

    @classmethod
    def teardown_class(cls):
        # Should be deleted as part of the test
        # but cleanup here if test fails
        dog.GcpIntegration.delete(
            project_id=cls.test_project_id,
            client_email=cls.test_client_email
        )

    def test_gcp_crud(self):
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
