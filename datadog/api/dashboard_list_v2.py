from datadog.api.resources import (
    AddableAPISubResource,
    DeletableAPISubResource,
    ListableAPISubResource,
    UpdatableAPISubResource
)


class DashboardListV2(ListableAPISubResource, AddableAPISubResource,
                      UpdatableAPISubResource, DeletableAPISubResource):
    """
    A wrapper around Dashboard List HTTP API.
    """
    _resource_name = 'dashboard/lists/manual'
    _sub_resource_name = 'dashboards'
    _api_version = 'v2'
