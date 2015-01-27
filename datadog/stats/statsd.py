import logging
import socket
from random import random


log = logging.getLogger('dd.datadogpy')


class StatsdAggregator(object):

    def __init__(self, host='localhost', port=8125):
        self.host = host
        self.port = int(port)
        self.address = (self.host, self.port)
        self.socket = None
        self._send = self._send_to_server
        self.connect(self.host, self.port)
        self.encoding = 'utf-8'

    def connect(self, host, port):
        """
        Connect to the statsd server on the given host and port.
        """
        self.host = host
        self.port = int(port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.connect((self.host, self.port))
        self.socket_sendto = self.socket.sendto

    def _send_to_server(self, packet):
        try:
            self.socket.send(packet.encode(self.encoding))
        except socket.error:
            log.info("Error submitting metric, will try refreshing the socket")
            self.connect(self._host, self._port)
            try:
                self.socket.send(packet.encode(self.encoding))
            except socket.error:
                log.exception("Failed to send packet with a newly binded socket")

    def add_point(self, metric, tags, timestamp, value, metric_class, sample_rate=1, host=None):
        if sample_rate == 1 or random() < sample_rate:
            payload = '%s:%s|%s' % (metric, value, metric_class.stats_tag)
            if host is not None:
                if not tags:
                    tags = []
                tags.append('host:%s' % host)
            if sample_rate != 1:
                payload += '|@%s' % sample_rate
            if tags:
                payload += '|#' + ','.join(tags)
            try:
                self._send(payload)
            except Exception:
                log.exception('couldnt submit statsd point')

    def _escape_event_content(self, string):
        return string.replace('\n', '\\n')

    def add_event(self, title, text, alert_type, aggregation_key, source_type_name,
                  date_happened, priority, tags, host):
        title = self._escape_event_content(title)
        text = self._escape_event_content(text)
        payload = u'_e{%d,%d}:%s|%s' % (len(title), len(text), title, text)
        if date_happened:
            payload = '%s|d:%d' % (payload, date_happened)
        if host:
            payload = '%s|h:%s' % (payload, host)
        if aggregation_key:
            payload = '%s|k:%s' % (payload, aggregation_key)
        if priority:
            payload = '%s|p:%s' % (payload, priority)
        if source_type_name:
            payload = '%s|s:%s' % (payload, source_type_name)
        if alert_type:
            payload = '%s|t:%s' % (payload, alert_type)
        if tags:
            payload = '%s|#%s' % (payload, ','.join(tags))

        if len(payload) > 8 * 1024:
            raise Exception(u'Event "%s" payload is too big (more that 8KB), '
                            'event discarded' % title)
        try:
            self.socket.send(payload.encode(self.encoding))
        except Exception:
            log.exception('couldnt submit statsd event ')
