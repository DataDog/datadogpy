from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, ListableAPIResource, DeletableAPIResource, \
    ActionAPIResource


class Monitor(GetableAPIResource, CreateableAPIResource, UpdatableAPIResource,
              ListableAPIResource, DeletableAPIResource, ActionAPIResource):
    """
    A wrapper around Monitor HTTP API.
    """
    _class_url = '/monitor'

    @classmethod
    def get(cls, id, **params):
        """
        Get monitor's details.

        :param id: monitor to retrieve
        :type id: id

        :param group_states: string list indicating what, if any, group states to include
        :type group_states: string list, strings are chosen from one or more \
        from 'all', 'alert', 'warn', or 'no data'

        :returns: JSON response from HTTP request
        """
        if 'group_states' in params and isinstance(params['group_states'], list):
            params['group_states'] = ','.join(params['group_states'])

        return super(Monitor, cls).get(id, **params)

    @classmethod
    def get_all(cls, **params):
        """
        Get all monitor details.

        :param group_states: string list indicating what, if any, group states to include
        :type group_states: string list, strings are chosen from one or more \
        from 'all', 'alert', 'warn', or 'no data'

        :param tags: tags to filter the list of monitors by scope
        :type tags: string list

        :returns: JSON response from HTTP request
        """
        if 'group_states' in params and isinstance(params['group_states'], list):
            params['group_states'] = ','.join(params['group_states'])

        return super(Monitor, cls).get_all(**params)

    @classmethod
    def mute(cls, id, **params):
        """
        Mute a monitor.

        :param scope: scope to apply the mute
        :type scope: string

        :param end: timestamp for when the mute should end
        :type end: POSIX timestamp


        :returns: JSON response from HTTP request
        """
        return super(Monitor, cls)._trigger_class_action('POST', 'mute', id, **params)

    @classmethod
    def unmute(cls, id, **params):
        """
        Unmute a monitor.

        :param scope: scope to apply the unmute
        :type scope: string

        :param all_scopes: if True, clears mute settings for all scopes
        :type all_scopes: boolean

        :returns: JSON response from HTTP request
        """
        return super(Monitor, cls)._trigger_class_action('POST', 'unmute', id, **params)

    @classmethod
    def mute_all(cls):
        """
        Globally mute monitors.

        :returns: JSON response from HTTP request
        """
        return super(Monitor, cls)._trigger_class_action('POST', 'mute_all')

    @classmethod
    def unmute_all(cls):
        """
        Cancel global monitor mute setting (does not remove mute settings for individual monitors).

        :returns: JSON response from HTTP request
        """
        return super(Monitor, cls)._trigger_class_action('POST', 'unmute_all')
