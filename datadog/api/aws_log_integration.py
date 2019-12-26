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

from datadog.api.resources import DeletableAPISubResource, \
    ListableAPISubResource, AddableAPISubResource


class AwsLogsIntegration(DeletableAPISubResource, ListableAPISubResource,
                         AddableAPISubResource):
    """
    A wrapper around AWS Logs API.
    """
    _resource_name = 'integration'
    _resource_id = 'aws'

    @classmethod
    def list_log_services(cls, **params):
        """
        List all namespace rules available as options.

        >>> api.AwsLogsIntegration.list_log_services()
        """
        cls._sub_resource_name = 'logs/services'
        return super(AwsLogsIntegration, cls).get_items(id=cls._resource_id, **params)

    @classmethod
    def add_log_lambda_arn(cls, **params):
        """
        Attach the Lambda ARN of the Lambda created for the Datadog-AWS \
        log collection to your AWS account ID to enable log collection.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> lambda_arn = "<AWS_LAMBDA_ARN>"

        >>> api.AwsLogsIntegration.add_log_lambda_arn(account_id=account_id, lambda_arn=lambda_arn)
        """
        cls._sub_resource_name = 'logs'
        return super(AwsLogsIntegration, cls).add_items(id=cls._resource_id, **params)

    @classmethod
    def save_services(cls, **params):
        """
        Enable Automatic Log collection for your AWS services.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> services = ["s3", "elb", "elbv2", "cloudfront", "redshift", "lambda"]

        >>> api.AwsLogsIntegration.save_services()
        """
        cls._sub_resource_name = 'logs/services'
        return super(AwsLogsIntegration, cls).add_items(id=cls._resource_id, **params)

    @classmethod
    def delete_config(cls, **params):
        """
        Delete a Datadog-AWS log collection configuration by removing the specific Lambda ARN \
        associated with a given AWS account.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> lambda_arn = "<AWS_LAMBDA_ARN>"

        >>> api.AwsLogsIntegration.delete_config(account_id=account_id, lambda_arn=lambda_arn)
        """
        cls._sub_resource_name = 'logs'
        return super(AwsLogsIntegration, cls).delete_items(id=cls._resource_id, **params)

    @classmethod
    def check_lambda(cls, **params):
        """
        Check function to see if a lambda_arn exists within an account. \
        This sends a job on our side if it does not exist, then immediately returns \
        the status of that job. Subsequent requests will always repeat the above, so this endpoint \
        can be polled intermittently instead of blocking.

        Returns a status of 'created' when it's checking if the Lambda exists in the account.
        Returns a status of 'waiting' while checking.
        Returns a status of 'checked and ok' if the Lambda exists.
        Returns a status of 'error' if the Lambda does not exist.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> lambda_arn = "<AWS_LAMBDA_ARN>"

        >>> api.AwsLogsIntegration.check_lambda(account_id=account_id, lambda_arn=lambda_arn)
        """
        cls._sub_resource_name = 'logs/check_async'
        return super(AwsLogsIntegration, cls).add_items(id=cls._resource_id, **params)

    @classmethod
    def check_services(cls, **params):
        """
        Test if permissions are present to add log-forwarding triggers for the \
        given services + AWS account. Input is the same as for save_services.
        Done async, so can be repeatedly polled in a non-blocking fashion until \
        the async request completes

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> services = ["s3", "elb", "elbv2", "cloudfront", "redshift", "lambda"]

        >>> api.AwsLogsIntegration.check_services()
        """
        cls._sub_resource_name = 'logs/services_async'
        return super(AwsLogsIntegration, cls).add_items(id=cls._resource_id, **params)

    @classmethod
    def list(cls, **params):
        """
        List all Datadog-AWS Logs integrations available in your Datadog organization.

        >>> api.AwsLogsIntegration.list()
        """
        cls._sub_resource_name = 'logs'
        return super(AwsLogsIntegration, cls).get_items(id=cls._resource_id, **params)
