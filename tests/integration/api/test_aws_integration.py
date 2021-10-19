# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

from itertools import product

import pytest

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

    @pytest.fixture(autouse=True)  # TODO , scope="class"
    def aws_integration(self, dog):
        """Remove pending AWS Integrations."""
        yield
        for account_id, role_name in product(ACCOUNT_IDS, ROLE_NAMES):
            dog.AwsIntegration.delete(account_id=account_id, role_name=role_name)

    def test_create(self, dog):
        output = dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_3,
            role_name=TEST_ROLE_NAME,
            host_tags=["api:test"],
            filter_tags=["filter:test"],
            account_specific_namespace_rules={'auto_scaling': False, 'opsworks': False}
        )
        assert "external_id" in output

    def test_list(self, dog):
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
        ]
        assert all(k in output['accounts'][0].keys() for k in expected_fields)

    def test_delete(self, dog):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_1,
            role_name=TEST_ROLE_NAME
        )
        output = dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID_1, role_name=TEST_ROLE_NAME)
        assert output == {}

    def test_generate_new_external_id(self, dog):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        output = dog.AwsIntegration.generate_new_external_id(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )

        assert "external_id" in output

    def test_list_namespace_rules(self, dog):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        output = dog.AwsIntegration.list_namespace_rules(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )
        assert len(output) >= AVAILABLE_NAMESPACES

    def test_update(self, dog):
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME
        )

        dog.AwsIntegration.update(
            account_id=TEST_ACCOUNT_ID_2,
            role_name=TEST_ROLE_NAME,
            new_account_id=TEST_ACCOUNT_ID_4,
            host_tags=["api:test2"],
            new_role_name=TEST_ROLE_NAME_2,
            excluded_regions=["us-east-1","us-west-1"]
        )

        output = dog.AwsIntegration.list()
        tests_pass = False
        for i in output['accounts']:
            assert "excluded_regions" in i.keys()
            if i.get('account_id') == TEST_ACCOUNT_ID_4 and i.get('role_name') == TEST_ROLE_NAME_2 and i.get('excluded_regions') == ["us-east-1","us-west-1"]:
                tests_pass = True
        assert tests_pass
