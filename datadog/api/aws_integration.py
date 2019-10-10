from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    SearchableAPIResource, DeletableAPIResource, UpdatableAPIResource, \
    UpdatableAPISubResource, ListableAPISubResource, AddableAPISubResource


class Aws(GetableAPIResource, CreateableAPIResource, SearchableAPIResource,
          DeletableAPIResource, ListableAPISubResource, UpdatableAPIResource,
          UpdatableAPISubResource, AddableAPISubResource):
    """
    A wrapper around AWS Integration API.
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
    def update(cls, id=_resource_id, **body):
        """
        Update an AWS integration config.

        :param account_id: Your AWS Account ID without dashes. \
        Consult the Datadog AWS integration to learn more about \
        your AWS account ID.
        :type account_id: string

        :param existing_account_id: Your existing AWS Account ID without dashes. \
        Consult the Datadog AWS integration to learn more about \
        your AWS account ID. This is the account to be updated.
        :type account_id: string

        :param access_key_id: If your AWS account is a GovCloud \
        or China account, enter the corresponding Access Key ID.
        :type access_key_id: string

        :param existing_access_key_id: If your AWS account is a GovCloud \
        or China account, enter the existing Access Key ID to be changed.
        :type access_key_id: string

        :param secret_access_key: If your AWS account is a GovCloud \
        or China account, enter the corresponding Secret Access Key.
        :type access_key_id: string

        :param existing_secret_access_key: If your AWS account is a GovCloud \
        or China account, enter the existing key to be changed.
        :type access_key_id: string

        :param role_name: Your Datadog role delegation name. \
        For more information about you AWS account Role name, \
        see the Datadog AWS integration configuration info.
        :type role_name: string

        :param existing_role_name: Your existing Datadog role delegation name. \
        For more information about you AWS account Role name, \
        see the Datadog AWS integration configuration info. \
        This is the role_name to be updated.
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

        The following will depend on whether role delegation or access keys are being used.
        If using role delegation, use the fields for role_name and account_id.
        For access keys, use fields for access_key_id and secret_access_key.

        >>> existing_account_id = "<EXISTING_AWS_ACCOUNT_ID>"
        >>> existing_role_name = "<EXISTING_AWS_ROLE_NAME>"
        >>> existing_access_key_id = "<AWS_ACCESS_KEY_ID>"
        >>> existing_secret_access_key = "<AWS_SECRET_ACCESS_KEY>"
        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> access_key_id = "<AWS_ACCESS_KEY_ID>"
        >>> role_name = "DatadogAwsRole"
        >>> filter_tags = ["<KEY>:<VALUE>"]
        >>> host_tags = ["<KEY>:<VALUE>"]
        >>> account_specific_namespace_rules = {"namespace1":true/false, "namespace2":true/false}

        >>> api.Aws.update(account_id=account_id, role_name=role_name, \
        filter_tags=filter_tags,host_tags=host_tags,\
        account_specific_namespace_rules=account_specific_namespace_rules)
        """
        params = {}
        params['account_id'] = body.get('existing_account_id')
        params['role_name'] = body.get('existing_role_name')
        params['access_key_id'] = body.get('existing_access_key_id')
        params['secret_access_key'] = body.get('existing_secret_access_key')
        return super(Aws, cls).update(id=id, params=params, **body)

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
