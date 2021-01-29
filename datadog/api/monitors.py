# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
)


class Monitor(
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
):
    """
    A wrapper around Monitor HTTP API.
    """

    _resource_name = "monitor"

    @classmethod
    def get(cls, id, **params):
        """
        Get monitor's details.

        :param id: monitor to retrieve
        :type id: id

        :param group_states: string list indicating what, if any, group states to include
        :type group_states: string list, strings are chosen from one or more \
        from 'all', 'alert', 'warn', or 'no data'

        :returns: Dictionary representing the API's JSON response
        """
        if "group_states" in params and isinstance(params["group_states"], list):
            params["group_states"] = ",".join(params["group_states"])

        return super(Monitor, cls).get(id, **params)

    @classmethod
    def get_all(cls, **params):
        """
        Get all monitor details.

        :param group_states: string list indicating what, if any, group states to include
        :type group_states: string list, strings are chosen from one or more \
        from 'all', 'alert', 'warn', or 'no data'

        :param name: name to filter the list of monitors by
        :type name: string

        :param tags: tags to filter the list of monitors by scope
        :type tags: string list

        :param monitor_tags: list indicating what service and/or custom tags, if any, \
        should be used to filter the list of monitors
        :type monitor_tags: string list

        :returns: Dictionary representing the API's JSON response
        """
        for p in ["group_states", "tags", "monitor_tags"]:
            if p in params and isinstance(params[p], list):
                params[p] = ",".join(params[p])

        return super(Monitor, cls).get_all(**params)

    @classmethod
    def mute(cls, id, **body):
        """
        Mute a monitor.

        :param scope: scope to apply the mute
        :type scope: string

        :param end: timestamp for when the mute should end
        :type end: POSIX timestamp


        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("POST", "mute", id, **body)

    @classmethod
    def unmute(cls, id, **body):
        """
        Unmute a monitor.

        :param scope: scope to apply the unmute
        :type scope: string

        :param all_scopes: if True, clears mute settings for all scopes
        :type all_scopes: boolean

        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("POST", "unmute", id, **body)

    @classmethod
    def mute_all(cls):
        """
        Globally mute monitors.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("POST", "mute_all")

    @classmethod
    def unmute_all(cls):
        """
        Cancel global monitor mute setting (does not remove mute settings for individual monitors).

        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("POST", "unmute_all")

    @classmethod
    def search(cls, **params):
        """
        Search monitors.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("GET", "search", params=params)

    @classmethod
    def search_groups(cls, **params):
        """
        Search monitor groups.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("GET", "groups/search", params=params)

    @classmethod
    def can_delete(cls, **params):
        """
        Checks if the monitors corresponding to the monitor ids can be deleted.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("GET", "can_delete", params=params)

    @classmethod
    def validate(cls, **body):
        """
        Checks if the monitors definition is valid.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Monitor, cls)._trigger_class_action("POST", "validate", **body)
