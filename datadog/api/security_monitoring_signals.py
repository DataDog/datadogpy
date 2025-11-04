# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Security Monitoring Signals API.
"""

from datadog.api.resources import (
    GetableAPIResource,
    ListableAPIResource,
    SearchableAPIResource,
    ActionAPIResource,
)


class SecurityMonitoringSignal(
    GetableAPIResource,
    ListableAPIResource,
    SearchableAPIResource,
    ActionAPIResource,
):
    """
    A wrapper around Security Monitoring Signal API.
    """

    _resource_name = "security_monitoring/signals"
    _api_version = "v2"

    @classmethod
    def get(cls, signal_id, **params):
        """
        Get a security signal's details.

        :param signal_id: ID of the security signal
        :type signal_id: str

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringSignal, cls).get(signal_id, **params)

    @classmethod
    def get_all(cls, **params):
        """
        Get all security signals.

        :param params: additional parameters to filter security signals
            Valid options are:
            - filter[query]: search query to filter security signals
            - filter[from]: minimum timestamp for returned security signals
            - filter[to]: maximum timestamp for returned security signals
            - sort: sort order, can be 'timestamp', '-timestamp', etc.
            - page[size]: number of signals to return per page
            - page[cursor]: cursor to use for pagination
        :type params: dict

        :returns: Dictionary representing the API's JSON response
        """
        return super(SecurityMonitoringSignal, cls).get_all(**params)

    @classmethod
    def change_triage_state(cls, signal_id, state, **params):
        """
        Change the triage state of security signals.

        :param signal_id: signal ID to update
        :type signal_id: str
        :param state: new triage state ('open', 'archived', 'under_review')
        :type state: str
        :param params: additional parameters
        :type params: dict

        :returns: Dictionary representing the API's JSON response
        """
        body = {
            "data": {
                "attributes": {
                    "state": state,
                },
                "id": signal_id,
                "type": "signal_metadata",
            }
        }

        return cls._trigger_class_action("PATCH", "state", id=signal_id, **body)
