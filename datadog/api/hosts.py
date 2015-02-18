from datadog.api.base import ActionAPIResource


class Host(ActionAPIResource):
    """
    A wrapper around Host HTTP API.
    """
    _class_url = '/host'

    @classmethod
    def mute(cls, host_name, **params):
        """
        Mute a host.

        :param host_name: hostname
        :type host_name: string

        :param end: timestamp to end muting
        :type end: POSIX timestamp

        :param override: if true and the host is already muted, will overwrite\
         existing end on the host
        :type override: bool

        :returns: JSON response from HTTP API request

        """
        return super(Host, cls)._trigger_class_action('POST', 'mute', host_name, **params)

    @classmethod
    def unmute(cls, host_name):
        """
        Unmute a host.

        :param host_name: hostname
        :type host_name: string

        :returns: JSON response from HTTP API request

        """
        return super(Host, cls)._trigger_class_action('POST', 'unmute', host_name)
