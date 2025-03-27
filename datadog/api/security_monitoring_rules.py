# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Security Monitoring Rule API.
"""

from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    ListableAPIResource,
    UpdatableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
)


class SecurityMonitoringRule(
    GetableAPIResource,
    CreateableAPIResource,
    ListableAPIResource,
    UpdatableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
):
    """
    A wrapper around Security Monitoring Rule API.
    """

    _resource_name = "security_monitoring/rules"
    _api_version = "v2"

    @classmethod
    def get_all(cls, **params):
        """
        Get all security monitoring rules.

        :param params: additional parameters to filter security monitoring rules
        :type params: dict

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).get_all(**params)

    @classmethod
    def get(cls, rule_id, **params):
        """
        Get a security monitoring rule's details.

        :param rule_id: ID of the security monitoring rule
        :type rule_id: str

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).get(rule_id, **params)

    @classmethod
    def create(cls, **params):
        """
        Create a security monitoring rule.

        :param params: Parameters to create the security monitoring rule with
        :type params: dict

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).create(**params)

    @classmethod
    def update(cls, rule_id, **params):
        """
        Update a security monitoring rule.

        :param rule_id: ID of the security monitoring rule to update
        :type rule_id: str
        :param params: Parameters to update the security monitoring rule with
        :type params: dict

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).update(rule_id, **params)

    @classmethod
    def delete(cls, rule_id, **params):
        """
        Delete a security monitoring rule.

        :param rule_id: ID of the security monitoring rule to delete
        :type rule_id: str

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).delete(rule_id, **params)
