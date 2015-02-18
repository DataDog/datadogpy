from datadog.util.compat import iteritems
from datadog.api.base import GetableAPIResource, CreateableAPIResource, \
    SearchableAPIResource


class Event(GetableAPIResource, CreateableAPIResource, SearchableAPIResource):
    """
    A wrapper around Event HTTP API.
    """
    _class_name = 'event'
    _class_url = '/events'
    _plural_class_name = 'events'
    _json_name = 'event'
    _timestamp_keys = set(['start', 'end'])

    @classmethod
    def create(cls, **params):
        """
        Post an event.

        :param title: title for the new event
        :type title: string

        :param text: event message
        :type text: string

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
        :type host: list of strings

        :param device_name: device_name to post the event with
        :type device_name: list of strings

        :return: JSON response from HTTP request

        >>> title = "Something big happened!"
        >>> text = 'And let me tell you all about it here!'
        >>> tags = ['version:1', 'application:web']

        >>> api.Event.create(title=title, text=text, tags=tags)
        """
        return super(Event, cls).create(attach_host_name=True, **params)

    @classmethod
    def query(cls, **params):
        """
        Get the events that occurred between the *start* and *end* POSIX timestamps,
        optional filtered by *priority* ("low" or "normal"), *sources* and
        *tags*.

        See the `event API documentation <http://api.datadoghq.com/events>`_ for the
        event data format.

        :return: JSON response from HTTP request

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
