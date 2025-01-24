# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import ActionAPIResource, SearchableAPIResource, ListableAPIResource


class Host(ActionAPIResource):
    """
    A wrapper around Host HTTP API.
    """

    _resource_name = "host"

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
        return super(Host, cls)._trigger_class_action("POST", "mute", host_name, **body)

    @classmethod
    def unmute(cls, host_name):
        """
        Unmute a host.

        :param host_name: hostname
        :type host_name: string

        :returns: Dictionary representing the API's JSON response

        """
        return super(Host, cls)._trigger_class_action("POST", "unmute", host_name)


class Hosts(ActionAPIResource, SearchableAPIResource, ListableAPIResource):
    """
    A wrapper around Hosts HTTP API.
    """

    _resource_name = "hosts"

    @classmethod
    def search(cls, **params):
        """
        Search among hosts live within the past 2 hours. Max 100
        results at a time.

        :param filter: query to filter search results
        :type filter: string

        :param sort_field: "status", "apps", "cpu", "iowait", or "load"
        :type sort_field: string

        :param sort_dir: "asc" or "desc"
        :type sort_dir: string

        :param start: host result to start at
        :type start: integer

        :param count: number of host results to return
        :type count: integer

        :returns: Dictionary representing the API's JSOn response

        """
        return super(Hosts, cls)._search(**params)

    @classmethod
    def totals(cls, **params):
        """
        Get total number of hosts active and up.

        :param from_: Number of seconds since UNIX epoch from which you want to search your hosts.
        :type from_: integer

        :returns: Dictionary representing the API's JSON response
        """
        return super(Hosts, cls)._trigger_class_action("GET", "totals", **params)

    @classmethod
    def get_all(cls, **params):
        """
        Get all hosts.

        :param filter: query to filter search results
        :type filter: string

        :param sort_field: field to sort by
        :type sort_field: string

        :param sort_dir: Direction of sort. Options include asc and desc.
        :type sort_dir: string

        :param start: Specify the starting point for the host search results.
            For example, if you set count to 100 and the first 100 results have already been returned,
            you can set start to 101 to get the next 100 results.
        :type start: integer

        :param count: number of hosts to return. Max 1000.
        :type count: integer

        :param from_: Number of seconds since UNIX epoch from which you want to search your hosts.
        :type from_: integer

        :param include_muted_hosts_data: Include data from muted hosts.
        :type include_muted_hosts_data: boolean

        :param include_hosts_metadata: Include metadata from the hosts
            (agent_version, machine, platform, processor, etc.).
        :type include_hosts_metadata: boolean

        :returns: Dictionary representing the API's JSON response
        """

        for param in ["filter"]:
            if param in params and isinstance(params[param], list):
                params[param] = ",".join(params[param])

        return super(Hosts, cls).get_all(**params)
