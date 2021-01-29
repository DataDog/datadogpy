# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    AddableAPISubResource,
    DeletableAPISubResource,
    ListableAPISubResource,
    UpdatableAPISubResource,
)


class DashboardListV2(ListableAPISubResource, AddableAPISubResource, UpdatableAPISubResource, DeletableAPISubResource):
    """
    A wrapper around Dashboard List HTTP API.
    """

    _resource_name = "dashboard/lists/manual"
    _sub_resource_name = "dashboards"
    _api_version = "v2"
