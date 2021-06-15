# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    ActionAPIResource,
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
)


class User(
    ActionAPIResource,
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
):

    _resource_name = "user"

    """
    A wrapper around User HTTP API.
    """

    @classmethod
    def invite(cls, emails):
        """
        Send an invite to join datadog to each of the email addresses in the
        *emails* list. If *emails* is a string, it will be wrapped in a list and
        sent. Returns a list of email addresses for which an email was sent.

        :param emails: emails addresses to invite to join datadog
        :type emails: string list

        :returns: Dictionary representing the API's JSON response
        """
        print("[DEPRECATION] User.invite() is deprecated. Use `create` instead.")

        if not isinstance(emails, list):
            emails = [emails]

        body = {
            "emails": emails,
        }

        return super(User, cls)._trigger_action("POST", "/invite_users", **body)
