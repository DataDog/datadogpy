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

TEST_ACCOUNT_ID = "123456789101"
TEST_ROLE_NAME = "DatadogApiTestRole"
TEST_LAMBDA_ARN = "arn:aws:lambda:us-east-1:123456789101:function:APITest"
AVAILABLE_SERVICES = 6


class TestAwsLogsIntegration:

    @classmethod
    def setup_class(cls):
        """ setup any state specific to the execution of the given class.
        """
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
        dog.AwsIntegration.create(
            account_id=TEST_ACCOUNT_ID,
            role_name=TEST_ROLE_NAME
        )

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a setup_method
        call.
        """
        dog.AwsIntegration.delete(account_id=TEST_ACCOUNT_ID, role_name=TEST_ROLE_NAME)

    def test_list_log_services(self):
        output = dog.AwsLogsIntegration.list_log_services()
        assert len(output) >= AVAILABLE_SERVICES

    def test_aws_logs_crud(self):
        add_lambda_arn_output = dog.AwsLogsIntegration.add_log_lambda_arn(
            account_id=TEST_ACCOUNT_ID,
            lambda_arn=TEST_LAMBDA_ARN
        )
        assert add_lambda_arn_output == {}
        save_services_output = dog.AwsLogsIntegration.save_services(
            account_id=TEST_ACCOUNT_ID,
            services=["s3", "elb", "elbv2", "cloudfront", "redshift", "lambda"]
        )
        assert save_services_output == {}
        list_output = dog.AwsLogsIntegration.list()
        expected_fields = [
            'services',
            'lambdas',
            'account_id'
        ]
        assert all(k in list_output[0].keys() for k in expected_fields)
        delete_output = dog.AwsLogsIntegration.delete_config(
            account_id=TEST_ACCOUNT_ID,
            lambda_arn=TEST_LAMBDA_ARN
        )
        assert delete_output == {}

    def test_check_lambda(self):
        output = dog.AwsLogsIntegration.check_lambda(
            account_id=TEST_ACCOUNT_ID,
            lambda_arn=TEST_LAMBDA_ARN
        )
        assert 'status' in output.keys()

    def test_check_services(self):
        output = dog.AwsLogsIntegration.check_services(
            account_id=TEST_ACCOUNT_ID,
            services=["s3", "elb", "elbv2", "cloudfront", "redshift", "lambda"]
        )
        assert 'status' in output.keys()
