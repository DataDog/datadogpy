# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
    ListableAPIResource,
)


class Screenboard(
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
    ListableAPIResource,
):
    """
    A wrapper around Screenboard HTTP API.
    """

    _resource_name = "screen"

    @classmethod
    def share(cls, board_id):
        """
        Share the screenboard with given id

        :param board_id: screenboard to share
        :type board_id: id

        :returns: Dictionary representing the API's JSON response
        """
        return super(Screenboard, cls)._trigger_action("POST", "screen/share", board_id)

    @classmethod
    def revoke(cls, board_id):
        """
        Revoke a shared screenboard with given id

        :param board_id: screenboard to revoke
        :type board_id: id

        :returns: Dictionary representing the API's JSON response
        """
        return super(Screenboard, cls)._trigger_action("DELETE", "screen/share", board_id)
