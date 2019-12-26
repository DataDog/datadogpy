# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from datadog.api.resources import (
    AddableAPISubResource,
    CreateableAPIResource,
    DeletableAPIResource,
    DeletableAPISubResource,
    GetableAPIResource,
    ListableAPIResource,
    ListableAPISubResource,
    UpdatableAPIResource,
    UpdatableAPISubResource
)

from datadog.api.dashboard_list_v2 import DashboardListV2


class DashboardList(AddableAPISubResource, CreateableAPIResource, DeletableAPIResource,
                    DeletableAPISubResource, GetableAPIResource, ListableAPIResource,
                    ListableAPISubResource, UpdatableAPIResource, UpdatableAPISubResource):
    """
    A wrapper around Dashboard List HTTP API.
    """
    _resource_name = 'dashboard/lists/manual'
    _sub_resource_name = 'dashboards'

    # Support for new API version (api.DashboardList.v2)
    # Note: This needs to be removed after complete migration of these endpoints from v1 to v2.
    v2 = DashboardListV2()
