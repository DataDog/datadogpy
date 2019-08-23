from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    SearchableAPIResource, DeletableAPISubResource, \
    UpdatableAPISubResource, ListableAPISubResource, AddableAPISubResource


class AwsLogs(GetableAPIResource, CreateableAPIResource, SearchableAPIResource,
              DeletableAPISubResource, ListableAPISubResource, UpdatableAPISubResource,
              AddableAPISubResource):
    """
    A wrapper around Event HTTP API.
    """
    _resource_name = 'integration'
    _resource_id = 'aws'

    @classmethod
    def list_log_services(cls, id=_resource_id, **params):
        """
        List all namespace rules available as options.

        >>> api.AwsLogs.list_log_services()
        """
        cls._sub_resource_name = 'logs/services'
        return super(AwsLogs, cls).get_items(id=id, **params)

    @classmethod
    def add_log_lambda_arn(cls, id=_resource_id, **params):
        """
        Attach the Lambda ARN of the Lambda created for the Datadog-AWS \
        log collection to your AWS account ID to enable log collection.

        >>> account_id = "601427279990"
        >>> lambda_arn = "arn:aws:lambda:us-east-1:601427279990:function:RickyLogsCollectionAPITest"

        >>> api.AwsLogs.add_log_lambda_arn(account_id=account_id, lambda_arn=lambda_arn)
        """
        cls._sub_resource_name = 'logs'
        return super(AwsLogs, cls).add_items(id=id, **params)

    @classmethod
    def save_services(cls, id=_resource_id, **params):
        """
        Enable Automatic Log collection for your AWS services.

        >>> account_id = "601427279990"
        >>> services = ["s3", "elb", "elbv2", "cloudfront", "redshift", "lambda"]

        >>> api.AwsLogs.save_services()
        """
        cls._sub_resource_name = 'logs/services'
        return super(AwsLogs, cls).add_items(id=id, **params)

    @classmethod
    def delete_config(cls, id=_resource_id, **params):
        """
        Delete a Datadog-AWS log collection configuration by removing the specific Lambda ARN \
        associated with a given AWS account.

        >>> account_id = "601427279990"
        >>> lambda_arn = "arn:aws:lambda:us-east-1:601427279990:function:RickyLogsCollectionAPITest"

        >>> api.AwsLogs.delete_config(account_id=account_id, lambda_arn=lambda_arn)
        """
        cls._sub_resource_name = 'logs'
        return super(AwsLogs, cls).delete_items(id=id, **params)
