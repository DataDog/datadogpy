from datadog.api.resources import (
    ActionAPIResource,
    CreateableAPIResource,
    DeletableAPIResource,
    GetableAPIResource,
    ListableAPIResource,
    UpdatableAPIResource
)


class DashboardList(ActionAPIResource, CreateableAPIResource, DeletableAPIResource,
                    GetableAPIResource, ListableAPIResource, UpdatableAPIResource):
    """
    A wrapper around Dashboard List HTTP API.
    """
    _class_url = '/dashboard/lists/manual'

    @classmethod
    def get_dashboards(cls, id, **params):
        """
        Get dashboards for a dashboard list.

        :returns: Dictionary representing the API's JSON response
        """
        return super(DashboardList, cls)._trigger_class_action('GET', 'dashboards', id, params)

    @classmethod
    def add_dashboards(cls, id, **body):
        """
        Add dashboards to a dashboard list.

        :param dashboards: dashboards to add to the dashboard list
        :type dashboards: list of dashboard dicts, e.g. [{"type": "custom_timeboard", "id": 1104}]

        :returns: Dictionary representing the API's JSON response
        """
        return super(DashboardList, cls)._trigger_class_action(
            'POST', 'dashboards', id, params=None, **body
        )

    @classmethod
    def update_dashboards(cls, id, **body):
        """
        Update dashboards of a dashboard list.

        :param dashboards: dashboards of the dashboard list
        :type dashboards: list of dashboard dicts, e.g. [{"type": "custom_timeboard", "id": 1104}]

        :returns: Dictionary representing the API's JSON response
        """
        return super(DashboardList, cls)._trigger_class_action(
            'PUT', 'dashboards', id, params=None, **body
        )

    @classmethod
    def delete_dashboards(cls, id, **body):
        """
        Delete dashboards from a dashboard list.

        :param dashboards: dashboards to delete from the dashboard list
        :type dashboards: list of dashboard dicts, e.g. [{"type": "custom_timeboard", "id": 1234}]

        :returns: Dictionary representing the API's JSON response
        """
        return super(DashboardList, cls)._trigger_class_action(
            'DELETE', 'dashboards', id, params=None, **body
        )
