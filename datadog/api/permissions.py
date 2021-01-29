# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    ActionAPIResource,
    CreateableAPIResource,
    CustomUpdatableAPIResource,
    DeletableAPIResource,
    GetableAPIResource,
    ListableAPIResource,
)


class Permissions(
    ActionAPIResource,
    CreateableAPIResource,
    CustomUpdatableAPIResource,
    GetableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
):
    """
    A wrapper around Tag HTTP API.
    """

    _resource_name = "permissions"
    _api_version = "v2"
