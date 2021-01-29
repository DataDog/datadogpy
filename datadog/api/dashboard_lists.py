# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    AddableAPISubResource,
    CreateableAPIResource,
    DeletableAPIResource,
    DeletableAPISubResource,
    GetableAPIResource,
    ListableAPIResource,
    ListableAPISubResource,
    UpdatableAPIResource,
    UpdatableAPISubResource,
)

from datadog.api.dashboard_list_v2 import DashboardListV2


class DashboardList(
    AddableAPISubResource,
    CreateableAPIResource,
    DeletableAPIResource,
    DeletableAPISubResource,
    GetableAPIResource,
    ListableAPIResource,
    ListableAPISubResource,
    UpdatableAPIResource,
    UpdatableAPISubResource,
):
    """
    A wrapper around Dashboard List HTTP API.
    """

    _resource_name = "dashboard/lists/manual"
    _sub_resource_name = "dashboards"

    # Support for new API version (api.DashboardList.v2)
    # Note: This needs to be removed after complete migration of these endpoints from v1 to v2.
    v2 = DashboardListV2()
