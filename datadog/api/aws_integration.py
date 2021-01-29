# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    DeletableAPIResource,
    UpdatableAPIResource,
    UpdatableAPISubResource,
    ListableAPISubResource,
)


class AwsIntegration(
    GetableAPIResource,
    CreateableAPIResource,
    DeletableAPIResource,
    ListableAPISubResource,
    UpdatableAPIResource,
    UpdatableAPISubResource,
):
    """
    A wrapper around AWS Integration API.
    """

    _resource_name = "integration"
    _resource_id = "aws"

    @classmethod
    def list(cls, **params):
        """
        List all Datadog-AWS integrations available in your Datadog organization.

        >>> api.AwsIntegration.list()
        """
        return super(AwsIntegration, cls).get(id=cls._resource_id, **params)

    @classmethod
    def create(cls, **params):
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

        :param excluded_regions: An array of AWS regions to exclude \
        from metrics collection.
        :type excluded_regions: list of strings

        :returns: Dictionary representing the API's JSON response

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> access_key_id = "<AWS_ACCESS_KEY_ID>"
        >>> role_name = "DatadogAwsRole"
        >>> filter_tags = ["<KEY>:<VALUE>"]
        >>> host_tags = ["<KEY>:<VALUE>"]
        >>> account_specific_namespace_rules = {"namespace1":true/false, "namespace2":true/false}
        >>> excluded_regions = ["us-east-1", "us-west-1"]

        >>> api.AwsIntegration.create(account_id=account_id, role_name=role_name, \
        filter_tags=filter_tags,host_tags=host_tags,\
        account_specific_namespace_rules=account_specific_namespace_rules \
        excluded_regions=excluded_regions)
        """
        return super(AwsIntegration, cls).create(id=cls._resource_id, **params)

    @classmethod
    def update(cls, **body):
        """
        Update an AWS integration config.

        :param account_id: Your existing AWS Account ID without dashes. \
        Consult the Datadog AWS integration to learn more about \
        your AWS account ID.
        :type account_id: string

        :param new_account_id: Your new AWS Account ID without dashes. \
        Consult the Datadog AWS integration to learn more about \
        your AWS account ID. This is the account to be updated.
        :type new_account_id: string

        :param role_name: Your existing Datadog role delegation name. \
        For more information about you AWS account Role name, \
        see the Datadog AWS integration configuration info.
        :type role_name: string

        :param new_role_name: Your new Datadog role delegation name. \
        For more information about you AWS account Role name, \
        see the Datadog AWS integration configuration info. \
        This is the role_name to be updated.
        :type new_role_name: string

        :param access_key_id: If your AWS account is a GovCloud \
        or China account, enter the existing Access Key ID.
        :type access_key_id: string

        :param new_access_key_id: If your AWS account is a GovCloud \
        or China account, enter the new Access Key ID to be set.
        :type new_access_key_id: string

        :param secret_access_key: If your AWS account is a GovCloud \
        or China account, enter the existing Secret Access Key.
        :type secret_access_key: string

        :param new_secret_access_key: If your AWS account is a GovCloud \
        or China account, enter the new key to be set.
        :type new_secret_access_key: string

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

        :param excluded_regions: An array of AWS regions to exclude \
        from metrics collection.
        :type excluded_regions: list of strings

        :returns: Dictionary representing the API's JSON response

        The following will depend on whether role delegation or access keys are being used.
        If using role delegation, use the fields for role_name and account_id.
        For access keys, use fields for access_key_id and secret_access_key.

        Both the existing fields and new fields are required no matter what. i.e. If the config is \
        account_id/role_name based, then `account_id`, `role_name`, `new_account_id`, and \
        `new_role_name` are all required.

        For access_key based accounts, `access_key_id`, `secret_access_key`, `new_access_key_id`, \
        and `new_secret_access_key` are all required.

        >>> account_id = "<EXISTING_AWS_ACCOUNT_ID>"
        >>> role_name = "<EXISTING_AWS_ROLE_NAME>"
        >>> access_key_id = "<EXISTING_AWS_ACCESS_KEY_ID>"
        >>> secret_access_key = "<EXISTING_AWS_SECRET_ACCESS_KEY>"
        >>> new_account_id = "<NEW_AWS_ACCOUNT_ID>"
        >>> new_role_name = "<NEW_AWS_ROLE_NAME>"
        >>> new_access_key_id = "<NEW_AWS_ACCESS_KEY_ID>"
        >>> new_secret_access_key = "<NEW_AWS_SECRET_ACCESS_KEY_ID>"
        >>> filter_tags = ["<KEY>:<VALUE>"]
        >>> host_tags = ["<KEY>:<VALUE>"]
        >>> account_specific_namespace_rules = {"namespace1":true/false, "namespace2":true/false}
        >>> excluded_regions = ["us-east-1", "us-west-1"]

        >>> api.AwsIntegration.update(account_id=account_id, role_name=role_name, \
        new_account_id=new_account_id, new_role_name=new_role_name, \
        filter_tags=filter_tags,host_tags=host_tags,\
        account_specific_namespace_rules=account_specific_namespace_rules, \
        excluded_regions=excluded_regions)
        """
        params = {}
        if body.get("account_id") and body.get("role_name"):
            params["account_id"] = body.pop("account_id")
            params["role_name"] = body.pop("role_name")
            if body.get("new_account_id"):
                body["account_id"] = body.pop("new_account_id")
            if body.get("new_role_name"):
                body["role_name"] = body.pop("new_role_name")
        if body.get("access_key_id") and body.get("secret_access_key"):
            params["access_key_id"] = body.pop("access_key_id")
            params["secret_access_key"] = body.pop("secret_access_key")
            if body.get("new_access_key_id"):
                body["access_key_id"] = body.pop("new_access_key_id")
            if body.get("new_secret_access_key"):
                body["secret_access_key"] = body.pop("new_secret_access_key")
        return super(AwsIntegration, cls).update(id=cls._resource_id, params=params, **body)

    @classmethod
    def delete(cls, **body):
        """
        Delete a given Datadog-AWS integration.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> role_name = "<Datadog Integration Role Name>"

        >>> api.AwsIntegration.delete()
        """
        return super(AwsIntegration, cls).delete(id=cls._resource_id, body=body)

    @classmethod
    def list_namespace_rules(cls, **params):
        """
        List all namespace rules available as options.

        >>> api.AwsIntegration.list_namespace_rules()
        """
        cls._sub_resource_name = "available_namespace_rules"
        return super(AwsIntegration, cls).get_items(id=cls._resource_id, **params)

    @classmethod
    def generate_new_external_id(cls, **params):
        """
        Generate a new AWS external id for a given AWS account id and role name pair.

        >>> account_id = "<AWS_ACCOUNT_ID>"
        >>> role_name = "<Datadog Integration Role Name>"

        >>> api.AwsIntegration.generate_new_external_id()
        """
        cls._sub_resource_name = "generate_new_external_id"
        return super(AwsIntegration, cls).update_items(id=cls._resource_id, **params)
