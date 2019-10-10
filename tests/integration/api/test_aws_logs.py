import os
from datadog import api as dog
from datadog import initialize

API_KEY = os.environ.get("DD_TEST_CLIENT_API_KEY", "a" * 32)
APP_KEY = os.environ.get("DD_TEST_CLIENT_APP_KEY", "a" * 40)
API_HOST = os.environ.get("DATADOG_HOST")
TEST_ACCOUNT_ID = "123456789101"
TEST_ROLE_NAME = "DatadogApiTestRole"
TEST_LAMBDA_ARN = "arn:aws:lambda:us-east-1:123456789101:function:APITest"


class TestAwsLogs:

    @classmethod
    def setup_class(cls):
        """ setup any state specific to the execution of the given class.
        """
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
        dog.Aws.create(
            account_id=TEST_ACCOUNT_ID,
            role_name=TEST_ROLE_NAME
        )

    @classmethod
    def teardown_class(cls):
        """ teardown any state that was previously setup with a setup_method
        call.
        """
        dog.Aws.delete(account_id=TEST_ACCOUNT_ID, role_name=TEST_ROLE_NAME)

    def test_list_log_services(self):
        output = dog.AwsLogs.list_log_services()
        assert len(output) >= 6

    def test_add_log_lambda_arn(self):
        output = dog.AwsLogs.add_log_lambda_arn(
            account_id=TEST_ACCOUNT_ID,
            lambda_arn=TEST_LAMBDA_ARN
        )
        assert output == {}

    def test_save_services(self):
        output = dog.AwsLogs.save_services(
            account_id=TEST_ACCOUNT_ID,
            services=["s3", "elb", "elbv2", "cloudfront", "redshift", "lambda"]
        )
        assert output == {}

    def test_aws_logs_list(self):
        output = dog.AwsLogs.list()
        expected_fields = [
            'services',
            'lambdas',
            'account_id'
        ]
        assert all(k in output[0].keys() for k in expected_fields)

    def test_delete_aws_log_config(self):
        output = dog.AwsLogs.delete_config(
            account_id=TEST_ACCOUNT_ID,
            lambda_arn=TEST_LAMBDA_ARN
        )
        assert output == {}

    def test_check_lambda(self):
        output = dog.AwsLogs.check_lambda(
            account_id=TEST_ACCOUNT_ID,
            lambda_arn=TEST_LAMBDA_ARN
        )
        assert 'status' in output.keys()

    def test_check_services(self):
        output = dog.AwsLogs.check_services(
            account_id=TEST_ACCOUNT_ID,
            services=["s3", "elb", "elbv2", "cloudfront", "redshift", "lambda"]
        )
        assert 'status' in output.keys()
