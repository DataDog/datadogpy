from datadog.api.resources import ActionAPIResource, ListableAPIResource


class Host(ActionAPIResource):
    """
    A wrapper around Host HTTP API.
    """
    _resource_name = 'host'

    @classmethod
    def mute(cls, host_name, **body):
        """
        Mute a host.

        :param host_name: hostname
        :type host_name: string

        :param end: timestamp to end muting
        :type end: POSIX timestamp

        :param override: if true and the host is already muted, will override\
         existing end on the host
        :type override: bool

        :param message: message to associate with the muting of this host
        :type message: string

        :returns: Dictionary representing the API's JSON response

        """
        return super(Host, cls)._trigger_class_action('POST', 'mute', host_name, **body)

    @classmethod
    def unmute(cls, host_name):
        """
        Unmute a host.

        :param host_name: hostname
        :type host_name: string

        :returns: Dictionary representing the API's JSON response

        """
        return super(Host, cls)._trigger_class_action('POST', 'unmute', host_name)


class Hosts(ActionAPIResource, ListableAPIResource):
    """
    A wrapper around Hosts HTTP API.
    """
    _resource_name = 'hosts'

    @classmethod
    def totals(cls):
        """
        Get total number of hosts active and up.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Hosts, cls)._trigger_class_action('GET', 'totals')
