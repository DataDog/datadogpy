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


class DashboardList(AddableAPISubResource, CreateableAPIResource, DeletableAPIResource,
                    DeletableAPISubResource, GetableAPIResource, ListableAPIResource,
                    ListableAPISubResource, UpdatableAPIResource, UpdatableAPISubResource):
    """
    A wrapper around Dashboard List HTTP API.
    """
    _resource_name = 'dashboard/lists/manual'
    _sub_resource_name = 'dashboards'
