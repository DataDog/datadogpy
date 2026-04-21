# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Security Monitoring Rule API.
"""
from typing import Any, Dict, Optional

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
        # type: (**Any) -> Any
        """
        Get all security monitoring rules.

        :param params: additional parameters to filter security monitoring rules
        :type params: dict

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).get_all(**params)

    @classmethod
    def get(cls, rule_id, **params):  # type: ignore[override]
        # type: (str, **Any) -> Any
        """
        Get a security monitoring rule's details.

        :param rule_id: ID of the security monitoring rule
        :type rule_id: str

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).get(rule_id, **params)

    @classmethod
    def create(cls, attach_host_name=False, method="POST", id=None, params=None, **body):
        # type: (bool, str, Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
        """
        Create a security monitoring rule.

        :param body: Parameters to create the security monitoring rule with
        :type body: dict

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).create(
            attach_host_name=attach_host_name, method=method, id=id, params=params, **body
        )

    @classmethod
    def update(cls, rule_id, **params):  # type: ignore[override]
        # type: (str, **Any) -> Any
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
    def delete(cls, rule_id, **params):  # type: ignore[override]
        # type: (str, **Any) -> Any
        """
        Delete a security monitoring rule.

        :param rule_id: ID of the security monitoring rule to delete
        :type rule_id: str

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringRule, cls).delete(rule_id, **params)
