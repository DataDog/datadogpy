from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, DeletableAPIResource, ActionAPIResource
from datadog.api.exceptions import ApiError


class Dashboard(GetableAPIResource, CreateableAPIResource,
                UpdatableAPIResource, DeletableAPIResource,
                ActionAPIResource):
    """
    A wrapper around Dashboard HTTP API.
    """
    _resource_name = 'dashboard'

    @classmethod
    def get_all(cls, layout_type=None):
        """
        Get a list of all custom dashboards

        :param layout_type: type of the layout. If provided, only dashboard of this type will be returned
        :type layout_type: 'ordered' or 'free' string

        :returns: Dictionary representing the API's JSON response
        """
        params = {}

        if layout_type is None:
            # Get all custom dashboards
            params['query'] = 'dashboard_type:custom_screenboard,custom_timeboard'
        else:
            if layout_type not in ['ordered', 'free']:
                raise ApiError('Invalid layout_type, expected one of: %s'
                               % ', '.join(['ordered', 'free']))
            else:
                dashboard_type = 'custom_timeboard' if layout_type == 'ordered' else 'custom_screenboard'
                params['query'] = 'dashboard_type:{0}'.format(dashboard_type)

        return super(Dashboard, cls)._trigger_action('GET', 'dashboards', params=params)
