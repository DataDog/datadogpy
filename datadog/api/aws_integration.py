from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    SearchableAPIResource, DeletableAPIResource, \
    UpdatableAPISubResource, ListableAPISubResource, AddableAPISubResource


class Aws(GetableAPIResource, CreateableAPIResource, SearchableAPIResource,
          DeletableAPIResource, ListableAPISubResource, UpdatableAPISubResource,
          AddableAPISubResource):
    """
    A wrapper around Event HTTP API.
    """
    _resource_name = 'integration'
    _resource_id = 'aws'

    @classmethod
    def list(cls, id=_resource_id, **params):
        """
        List all Datadog-AWS integrations available in your Datadog organization.

        >>> api.Aws.list()
        """
        return super(Aws, cls).get(id=id, **params)

    @classmethod
    def create(cls, id=_resource_id, **params):
        """
        Add a new AWS integration config.

        :param account_id: Your AWS Account ID without dashes. \
        Consult the Datadog AWS integration to learn more about \
        your AWS account ID.
        :type account_id: string

        :param access_key_id: If your AWS account is a GovCloud \
        or China account, enter the corresponding Access Key ID.
        :type access_key_id: string

        :param role_name: Your Datadog role delegation name. \
        For more information about you AWS account Role name, \
        see the Datadog AWS integration configuration info.
        :type role_name: string

        :param filter_tags: The array of EC2 tags (in the form key:value) \
        defines a filter that Datadog uses when collecting metrics from EC2. \
        Wildcards, such as ? (for single characters) and * (for multiple characters) \
        can also be used. Only hosts that match one of the defined tags will be imported \
        into Datadog. The rest will be ignored. Host matching a given tag can also be \
        excluded by adding ! before the tag. e.x. \
        env:production,instance-type:c1.*,!region:us-east-1 For more information \
        on EC2 tagging, see the AWS tagging documentation.
        :type filter_tags: list of strings

        :param host_tags: Array of tags (in the form key:value) to add to all hosts and \
        metrics reporting through this integration.
        :type host_tags: list of strings

        :param account_specific_namespace_rules: An object (in the form \
        {"namespace1":true/false, "namespace2":true/false}) that enables \
        or disables metric collection for specific AWS namespaces for this \
        AWS account only. A list of namespaces can be found at the \
        /v1/integration/aws/available_namespace_rules endpoint.
        :type account_specific_namespace_rules: dictionary

        :returns: Dictionary representing the API's JSON response

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> access_key_id = "<AWS_ACCESS_KEY_ID>"
        >>> role_name = "DatadogAwsRole"
        >>> filter_tags = ["<KEY>:<VALUE>"]
        >>> host_tags = ["<KEY>:<VALUE>"]
        >>> account_specific_namespace_rules = {"namespace1":true/false, "namespace2":true/false}

        >>> api.Aws.create(account_id=account_id, role_name=role_name, \
        filter_tags=filter_tags,host_tags=host_tags,\
        account_specific_namespace_rules=account_specific_namespace_rules)
        """
        return super(Aws, cls).create(id=id, **params)

    @classmethod
    def delete(cls, id=_resource_id, **body):
        """
        Delete a given Datadog-AWS integration.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> role_name = "<Datadog Integration Role Name>"

        >>> api.Aws.delete()
        """
        return super(Aws, cls).delete(id=id, body=body)

    @classmethod
    def list_namespace_rules(cls, id=_resource_id, **params):
        """
        List all namespace rules available as options.

        >>> api.Aws.list_namespace_rules()
        """
        cls._sub_resource_name = 'available_namespace_rules'
        return super(Aws, cls).get_items(id=id, **params)

    @classmethod
    def generate_new_external_id(cls, id=_resource_id, **params):
        """
        Generate a new AWS external id for a given AWS account id and role name pair.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> role_name = "<Datadog Integration Role Name>"

        >>> api.Aws.generate_new_external_id()
        """
        cls._sub_resource_name = 'generate_new_external_id'
        return super(Aws, cls).update_items(id=id, **params)

    @classmethod
    def list_log_services(cls, id=_resource_id, **params):
        """
        List all namespace rules available as options.

        >>> api.Aws.list_log_services()
        """
        cls._sub_resource_name = 'logs/services'
        return super(Aws, cls).get_items(id=id, **params)

    @classmethod
    def add_log_lambda_arn(cls, id=_resource_id, **params):
        """
        List all namespace rules available as options.

        >>> api.Aws.add_log_lambda_arn()
        """
        cls._sub_resource_name = 'logs'
        return super(Aws, cls).add_items(id=id, **params)
