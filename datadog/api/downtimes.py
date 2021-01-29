# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
)


class Downtime(
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
):
    """
    A wrapper around Monitor Downtiming HTTP API.
    """

    _resource_name = "downtime"

    @classmethod
    def cancel_downtime_by_scope(cls, **body):
        """
        Cancels all downtimes matching the scope.

        :param scope: scope to cancel downtimes by
        :type scope: string

        :returns: Dictionary representing the API's JSON response
        """
        return super(Downtime, cls)._trigger_class_action("POST", "cancel/by_scope", **body)
