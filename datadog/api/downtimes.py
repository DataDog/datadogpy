from datadog.api.resources import GetableAPIResource, CreateableAPIResource,\
    UpdatableAPIResource, ListableAPIResource, DeletableAPIResource, \
    ActionAPIResource


class Downtime(GetableAPIResource, CreateableAPIResource, UpdatableAPIResource,
               ListableAPIResource, DeletableAPIResource, ActionAPIResource):
    """
    A wrapper around Monitor Downtiming HTTP API.
    """
    _resource_name = 'downtime'

    @classmethod
    def cancel_downtime_by_scope(cls, **body):
        """
        Cancels all downtimes matching the scope.

        :param scope: scope to cancel downtimes by
        :type scope: string

        :returns: Dictionary representing the API's JSON response
        """
        return super(Downtime, cls)._trigger_class_action('POST', 'cancel/by_scope', **body)
