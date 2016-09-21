#!/usr/bin/env python
"""
DogStatsd is a Python client for DogStatsd, a Statsd fork for Datadog.
"""
# stdlib
from random import random
import logging
import os
import socket
import struct

# datadog
from datadog.dogstatsd.context import TimedContextManagerDecorator
from datadog.util.compat import imap

# datadog
from datadog.util.compat import text


# Logging
log = logging.getLogger('datadog.dogstatsd')


class DogStatsd(object):
    OK, WARNING, CRITICAL, UNKNOWN = (0, 1, 2, 3)

    def __init__(self, host='localhost', port=8125, max_buffer_size=50, namespace=None,
                 constant_tags=None, use_ms=False, use_default_route=False):
        """
        Initialize a DogStatsd object.

        >>> statsd = DogStatsd()

        :param host: the host of the DogStatsd server.
        :type host: string

        :param port: the port of the DogStatsd server.
        :type port: integer

        :param max_buffer_size: Maximum number of metrics to buffer before sending to the server
        if sending metrics in batch
        :type max_buffer_size: integer

        :param namepace: Namespace to prefix all metric names
        :type namepace: string

        :param constant_tags: Tags to attach to all metrics
        :type constant_tags: list of strings

        :param use_ms: Report timed values in milliseconds instead of seconds (default False)
        :type use_ms: boolean

        :envvar DATADOG_TAGS: Tags to attach to every metric reported by dogstatsd client
        :type constant_tags: list of strings

        :param use_default_route: Dynamically set the statsd host to the default route
        (Useful when running the client in a container)
        :type use_default_route: boolean

        """
        self.host = host
        self.port = int(port)
        self.socket = None
        self.max_buffer_size = max_buffer_size
        self._send = self._send_to_server
        self.encoding = 'utf-8'
        env_tags = [tag for tag in os.environ.get('DATADOG_TAGS', '').split(',') if tag]
        if constant_tags is None:
            constant_tags = []
        self.constant_tags = constant_tags + env_tags
        self.namespace = namespace
        self.use_ms = use_ms
        self.use_default_route = use_default_route
        if self.use_default_route:
            self.host = self._get_default_route()

    def __enter__(self):
        self.open_buffer(self.max_buffer_size)
        return self

    def __exit__(self, type, value, traceback):
        self.close_buffer()

    def _get_default_route(self):
        try:
            with open('/proc/net/route') as f:
                for line in f.readlines():
                    fields = line.strip().split()
                    if fields[1] == '00000000':
                        return socket.inet_ntoa(struct.pack('<L', int(fields[2], 16)))
        except IOError as e:
            log.error('Unable to open /proc/net/route: %s', e)

        return None

    def get_socket(self):
        """
        Return a connected socket.

        Note: connect the socket before assigning it to the class instance to
        avoid bad thread race conditions.
        """
        if not self.socket:
            if self.use_default_route:
                self.host = self._get_default_route()

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect((self.host, self.port))
            self.socket = sock
        return self.socket

    def open_buffer(self, max_buffer_size=50):
        """
        Open a buffer to send a batch of metrics in one packet.

        You can also use this as a context manager.

        >>> with DogStatsd() as batch:
        >>>     batch.gauge('users.online', 123)
        >>>     batch.gauge('active.connections', 1001)
        """
        self.max_buffer_size = max_buffer_size
        self.buffer = []
        self._send = self._send_to_buffer

    def close_buffer(self):
        """
        Flush the buffer and switch back to single metric packets.
        """
        self._send = self._send_to_server
        self._flush_buffer()

    def gauge(self, metric, value, tags=None, sample_rate=1):
        """
        Record the value of a gauge, optionally setting a list of tags and a
        sample rate.

        >>> statsd.gauge('users.online', 123)
        >>> statsd.gauge('active.connections', 1001, tags=["protocol:http"])
        """
        return self._report(metric, 'g', value, tags, sample_rate)

    def increment(self, metric, value=1, tags=None, sample_rate=1):
        """
        Increment a counter, optionally setting a value, tags and a sample
        rate.

        >>> statsd.increment('page.views')
        >>> statsd.increment('files.transferred', 124)
        """
        self._report(metric, 'c', value, tags, sample_rate)

    def decrement(self, metric, value=1, tags=None, sample_rate=1):
        """
        Decrement a counter, optionally setting a value, tags and a sample
        rate.

        >>> statsd.decrement('files.remaining')
        >>> statsd.decrement('active.connections', 2)
        """
        metric_value = -value if value else value
        self._report(metric, 'c', metric_value, tags, sample_rate)

    def histogram(self, metric, value, tags=None, sample_rate=1):
        """
        Sample a histogram value, optionally setting tags and a sample rate.

        >>> statsd.histogram('uploaded.file.size', 1445)
        >>> statsd.histogram('album.photo.count', 26, tags=["gender:female"])
        """
        self._report(metric, 'h', value, tags, sample_rate)

    def timing(self, metric, value, tags=None, sample_rate=1):
        """
        Record a timing, optionally setting tags and a sample rate.

        >>> statsd.timing("query.response.time", 1234)
        """
        self._report(metric, 'ms', value, tags, sample_rate)

    def timed(self, metric=None, tags=None, sample_rate=1, use_ms=None):
        """
        A decorator or context manager that will measure the distribution of a
        function's/context's run time. Optionally specify a list of tags or a
        sample rate. If the metric is not defined as a decorator, the module
        name and function name will be used. The metric is required as a context
        manager.
        ::

            @statsd.timed('user.query.time', sample_rate=0.5)
            def get_user(user_id):
                # Do what you need to ...
                pass

            # Is equivalent to ...
            with statsd.timed('user.query.time', sample_rate=0.5):
                # Do what you need to ...
                pass

            # Is equivalent to ...
            start = time.time()
            try:
                get_user(user_id)
            finally:
                statsd.timing('user.query.time', time.time() - start)
        """
        return TimedContextManagerDecorator(self, metric, tags, sample_rate, use_ms)

    def set(self, metric, value, tags=None, sample_rate=1):
        """
        Sample a set value.

        >>> statsd.set('visitors.uniques', 999)
        """
        self._report(metric, 's', value, tags, sample_rate)

    def _report(self, metric, metric_type, value, tags, sample_rate):
        """
        Create a metric packet and send it.

        More information about the packets' format: http://docs.datadoghq.com/guides/dogstatsd/
        """
        if value is None:
            return

        if sample_rate != 1 and random() > sample_rate:
            return

        payload = []

        # Resolve the full tag list
        if self.constant_tags:
            if tags:
                tags = tags + self.constant_tags
            else:
                tags = self.constant_tags

        # Create/format the metric packet
        if self.namespace:
            payload.extend([self.namespace, "."])
        payload.extend([metric, ":", value, "|", metric_type])

        if sample_rate != 1:
            payload.extend(["|@", sample_rate])

        if tags:
            payload.extend(["|#", ",".join(tags)])

        encoded = "".join(imap(text, payload))

        # Send it
        self._send(encoded)

    def _send_to_server(self, packet):
        try:
            # If set, use socket directly
            (self.socket or self.get_socket()).send(packet.encode(self.encoding))
        except socket.error:
            log.info("Error submitting packet, will try refreshing the socket")
            self.socket = None
            try:
                self.get_socket().send(packet.encode(self.encoding))
            except socket.error:
                log.exception("Failed to send packet with a newly binded socket")

    def _send_to_buffer(self, packet):
        self.buffer.append(packet)
        if len(self.buffer) >= self.max_buffer_size:
            self._flush_buffer()

    def _flush_buffer(self):
        self._send_to_server("\n".join(self.buffer))
        self.buffer = []

    def _escape_event_content(self, string):
        return string.replace('\n', '\\n')

    def _escape_service_check_message(self, string):
        return string.replace('\n', '\\n').replace('m:', 'm\:')

    def event(self, title, text, alert_type=None, aggregation_key=None,
              source_type_name=None, date_happened=None, priority=None,
              tags=None, hostname=None):
        """
        Send an event. Attributes are the same as the Event API.
            http://docs.datadoghq.com/api/

        >>> statsd.event('Man down!', 'This server needs assistance.')
        >>> statsd.event('The web server restarted', 'The web server is up again', alert_type='success')  # NOQA
        """
        title = self._escape_event_content(title)
        text = self._escape_event_content(text)

        # Append all client level tags to every event
        if self.constant_tags:
            if tags:
                tags += self.constant_tags
            else:
                tags = self.constant_tags

        string = u'_e{%d,%d}:%s|%s' % (len(title), len(text), title, text)
        if date_happened:
            string = '%s|d:%d' % (string, date_happened)
        if hostname:
            string = '%s|h:%s' % (string, hostname)
        if aggregation_key:
            string = '%s|k:%s' % (string, aggregation_key)
        if priority:
            string = '%s|p:%s' % (string, priority)
        if source_type_name:
            string = '%s|s:%s' % (string, source_type_name)
        if alert_type:
            string = '%s|t:%s' % (string, alert_type)
        if tags:
            string = '%s|#%s' % (string, ','.join(tags))

        if len(string) > 8 * 1024:
            raise Exception(u'Event "%s" payload is too big (more that 8KB), '
                            'event discarded' % title)

        self._send(string)

    def service_check(self, check_name, status, tags=None, timestamp=None,
                      hostname=None, message=None):
        """
        Send a service check run.

        >>> statsd.service_check('my_service.check_name', DogStatsd.WARNING)
        """
        message = self._escape_service_check_message(message) if message is not None else ''

        string = u'_sc|{0}|{1}'.format(check_name, status)

        if timestamp:
            string = u'{0}|d:{1}'.format(string, timestamp)
        if hostname:
            string = u'{0}|h:{1}'.format(string, hostname)
        if tags:
            string = u'{0}|#{1}'.format(string, ','.join(tags))
        if message:
            string = u'{0}|m:{1}'.format(string, message)

        self._send(string)


statsd = DogStatsd()
