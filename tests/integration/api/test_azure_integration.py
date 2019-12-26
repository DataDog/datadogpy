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

    @classmethod
    def teardown_class(cls):
        # Should be deleted as part of the test
        # but cleanup here if test fails
        dog.AzureIntegration.delete(
            tenant_name=cls.test_new_tenant_name,
            client_id=cls.test_new_client_id
        )

    def test_azure_crud(self):
        # Test Create
        create_output = dog.AzureIntegration.create(
            tenant_name=self.test_tenant_name,
            host_filters="api:test",
            client_id=self.test_client_id,
            client_secret=self.test_client_secret
        )
        assert create_output == {}
        # Test List
        list_tests_pass = False
        for i in dog.AzureIntegration.list():
            if (i['tenant_name'] == self.test_tenant_name and
                    i['host_filters'] == 'api:test'):
                list_tests_pass = True
        assert list_tests_pass
        # Test Update Host Filters
        dog.AzureIntegration.update_host_filters(
            tenant_name=self.test_tenant_name,
            host_filters='api:test2',
            client_id=self.test_client_id
        )
        update_host_filters_tests_pass = False
        for i in dog.AzureIntegration.list():
            if i['host_filters'] == 'api:test2':
                update_host_filters_tests_pass = True
        assert update_host_filters_tests_pass
        # Test Update
        dog.AzureIntegration.update(
            tenant_name=self.test_tenant_name,
            new_tenant_name=self.test_new_tenant_name,
            host_filters="api:test3",
            client_id=self.test_client_id,
            new_client_id=self.test_new_client_id,
            client_secret=self.test_client_secret
        )
        update_tests_pass = False
        for i in dog.AzureIntegration.list():
            if (i['tenant_name'] == self.test_new_tenant_name and
                    i['host_filters'] == 'api:test3'):
                update_tests_pass = True
        assert update_tests_pass
        # Test Delete
        dog.AzureIntegration.delete(
            tenant_name=self.test_new_tenant_name,
            client_id=self.test_new_client_id
        )
        delete_tests_pass = True
        list_output = dog.AzureIntegration.list()
        if type(list_output) == list:
            for i in dog.AzureIntegration.list():
                if i['tenant_name'] == self.test_new_tenant_name:
                    delete_tests_pass = False
        elif self.not_yet_installed_error in list_output['errors'][0]:
            pass
        assert delete_tests_pass
