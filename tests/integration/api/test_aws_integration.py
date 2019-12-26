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

from itertools import product

TEST_ACCOUNT_ID_1 = "123456789101"
TEST_ACCOUNT_ID_2 = "123456789102"
TEST_ACCOUNT_ID_3 = "123456789103"
TEST_ACCOUNT_ID_4 = "123456789104"
TEST_ROLE_NAME = "DatadogApiTestRole"
TEST_ROLE_NAME_2 = "DatadogApiTestRolo"

ROLE_NAMES = [TEST_ROLE_NAME, TEST_ROLE_NAME_2]
ACCOUNT_IDS = [TEST_ACCOUNT_ID_1, TEST_ACCOUNT_ID_2, TEST_ACCOUNT_ID_3, TEST_ACCOUNT_ID_4]
AVAILABLE_NAMESPACES = 76

class TestAwsIntegration:

    # List of dictionaries representing the AWS Accounts to cleanup between tests
    # Ex: [{"account_id": "1234", "role_name": "R1"}, {"account_id": "5678", "role_name": "r2"}]
    accounts_to_cleanup = []

    @classmethod
    def setup_class(cls):
        """ setup any state tied to the execution of the class. called at class
        level before and after all test methods of the class are called.
        """
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

        for acc in product(ACCOUNT_IDS, ROLE_NAMES):
            cls.accounts_to_cleanup.append({'account_id': acc[0], 'role_name': acc[1]})

    def teardown_method(self, method):
        for account in self.accounts_to_cleanup:
            dog.AwsIntegration.delete(account_id=account['account_id'], role_name=account.get('role_name'))

    def test_create(self):
        output = dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_3,
            role_name=TEST_ROLE_NAME,
            host_tags=["api:test"],
            filter_tags=["filter:test"],
            account_specific_namespace_rules={'auto_scaling': False, 'opsworks': False}
        )
        assert "external_id" in output

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
