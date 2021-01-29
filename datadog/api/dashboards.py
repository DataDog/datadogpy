# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    DeletableAPIResource,
    ListableAPIResource,
)


class Dashboard(
    GetableAPIResource, CreateableAPIResource, UpdatableAPIResource, DeletableAPIResource, ListableAPIResource
):
    """
    A wrapper around Dashboard HTTP API.
    """

    _resource_name = "dashboard"
