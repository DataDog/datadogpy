# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.exceptions import ApiError
from datadog.api.resources import GetableAPIResource, CreateableAPIResource, SearchableAPIResource
from datadog.util.compat import iteritems


class Event(GetableAPIResource, CreateableAPIResource, SearchableAPIResource):
    """
    A wrapper around Event HTTP API.
    """

    _resource_name = "events"
    _timestamp_keys = set(["start", "end"])

    @classmethod
    def create(cls, attach_host_name=True, **params):
        """
        Post an event.

        :param title: title for the new event
        :type title: string

        :param text: event message
        :type text: string

        :param aggregation_key: key by which to group events in event stream
        :type aggregation_key: string

        :param alert_type: "error", "warning", "info" or "success".
        :type alert_type: string

        :param date_happened: when the event occurred. if unset defaults to the current time. \
        (POSIX timestamp)
        :type date_happened: integer

        :param handle: user to post the event as. defaults to owner of the application key used \
        to submit.
        :type handle: string

        :param priority: priority to post the event as. ("normal" or "low", defaults to "normal")
        :type priority: string

        :param related_event_id: post event as a child of the given event
        :type related_event_id: id

        :param tags: tags to post the event with
        :type tags: list of strings

        :param host: host to post the event with
        :type host: string

        :param device_name: device_name to post the event with
        :type device_name: list of strings

        :returns: Dictionary representing the API's JSON response

        >>> title = "Something big happened!"
        >>> text = 'And let me tell you all about it here!'
        >>> tags = ['version:1', 'application:web']

        >>> api.Event.create(title=title, text=text, tags=tags)
        """
        if params.get("alert_type"):
            if params["alert_type"] not in ["error", "warning", "info", "success"]:
                raise ApiError("Parameter alert_type must be either error, warning, info or success")

        return super(Event, cls).create(attach_host_name=attach_host_name, **params)

    @classmethod
    def query(cls, **params):
        """
        Get the events that occurred between the *start* and *end* POSIX timestamps,
        optional filtered by *priority* ("low" or "normal"), *sources* and
        *tags*.

        See the `event API documentation <http://docs.datadoghq.com/api/#events-get-all>`_ for the
        event data format.

        :returns: Dictionary representing the API's JSON response

        >>> api.Event.query(start=1313769783, end=1419436870, priority="normal", \
            tags=["application:web"])
        """

        def timestamp_to_integer(k, v):
            if k in cls._timestamp_keys:
                return int(v)
            else:
                return v

        params = dict((k, timestamp_to_integer(k, v)) for k, v in iteritems(params))

        return super(Event, cls)._search(**params)
