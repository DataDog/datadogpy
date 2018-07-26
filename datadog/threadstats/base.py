"""
ThreadStats is a tool for collecting application metrics without hindering
performance. It collects metrics in the application thread with very little overhead
and allows flushing metrics in process, in a thread or in a greenlet, depending
on your application's needs.
"""
# stdlib
from contextlib import contextmanager
from functools import wraps
from time import time
import atexit
import logging
import os

# datadog
from datadog.api.exceptions import ApiNotInitialized
from datadog.threadstats.events import EventsAggregator
from datadog.threadstats.metrics import MetricsAggregator, Counter, Gauge, Histogram, Timing
from datadog.threadstats.reporters import HttpReporter

# Loggers
log = logging.getLogger('datadog.threadstats')


class ThreadStats(object):

    def __init__(self, namespace="", constant_tags=None):
        """
        Initialize a threadstats object.

        :param namespace: Namespace to prefix all metric names
        :type namespace: string

        :param constant_tags: Tags to attach to every metric reported by this client
        :type constant_tags: list of strings

        :envvar DATADOG_TAGS: Tags to attach to every metric reported by ThreadStats client
        :type DATADOG_TAGS: list of strings
        """
        # Parameters
        self.namespace = namespace
        env_tags = [tag for tag in os.environ.get('DATADOG_TAGS', '').split(',') if tag]
        if constant_tags is None:
            constant_tags = []
        self.constant_tags = constant_tags + env_tags

        # State
        self._disabled = True

    def start(self, flush_interval=10, roll_up_interval=10, device=None,
              flush_in_thread=True, flush_in_greenlet=False, disabled=False):
        """
        Start the ThreadStats instance with the specified metric flushing method and preferences.

        By default, metrics will be flushed in a thread.

        >>> stats.start()

        If you're running a gevent server and want to flush metrics in a
        greenlet, set *flush_in_greenlet* to True. Be sure to import and monkey
        patch gevent before starting ThreadStats. ::

        >>> from gevent import monkey; monkey.patch_all()
        >>> stats.start(flush_in_greenlet=True)

        If you'd like to flush metrics in process, set *flush_in_thread*
        to False, though you'll have to call ``flush`` manually to post metrics
        to the server. ::

        >>> stats.start(flush_in_thread=False)

        If for whatever reason, you need to disable metrics collection in a
        hurry, set ``disabled`` to True and metrics won't be collected or flushed.

        >>> stats.start(disabled=True)

        *Note:* Please remember to set your API key before,
            using datadog module ``initialize`` method.

        >>> from datadog import initialize, ThreadStats
        >>> initialize(api_key='my_api_key')
        >>> stats = ThreadStats()
        >>> stats.start()
        >>> stats.increment('home.page.hits')

        :param flush_interval: The number of seconds to wait between flushes.
        :type flush_interval: int
        :param flush_in_thread: True if you'd like to spawn a thread to flush metrics.
            It will run every `flush_interval` seconds.
        :type flush_in_thread: bool
        :param flush_in_greenlet: Set to true if you'd like to flush in a gevent greenlet.
        :type flush_in_greenlet: bool
        :param disabled: Disable metrics collection
        :type disabled: bool
        """
        self.flush_interval = flush_interval
        self.roll_up_interval = roll_up_interval
        self.device = device
        self._disabled = disabled
        self._is_auto_flushing = False

        # Create an aggregator
        self._metric_aggregator = MetricsAggregator(self.roll_up_interval)
        self._event_aggregator = EventsAggregator()

        # The reporter is responsible for sending metrics off to their final destination.
        # It's abstracted to support easy unit testing and in the near future, forwarding
        # to the datadog agent.
        self.reporter = HttpReporter()

        self._is_flush_in_progress = False
        self.flush_count = 0
        if self._disabled:
            log.info("ThreadStats instance is disabled. No metrics will flush.")
        else:
            if flush_in_greenlet:
                self._start_flush_greenlet()
            elif flush_in_thread:
                self._start_flush_thread()

        # Flush all remaining metrics on exit
        atexit.register(lambda: self.flush(float('inf')))

    def stop(self):
        if not self._is_auto_flushing:
            return True
        if self._flush_thread:
            self._flush_thread.end()
            self._is_auto_flushing = False
            return True

    def event(self, title, text, alert_type=None, aggregation_key=None,
              source_type_name=None, date_happened=None, priority=None,
              tags=None, hostname=None):
        """
        Send an event. Attributes are the same as the Event API. (http://docs.datadoghq.com/api/)

        >>> stats.event('Man down!', 'This server needs assistance.')
        >>> stats.event('The web server restarted', \
            'The web server is up again', alert_type='success')
        """
        if not self._disabled:
            # Append all client level tags to every event
            event_tags = tags
            if self.constant_tags:
                if tags:
                    event_tags = tags + self.constant_tags
                else:
                    event_tags = self.constant_tags

            self._event_aggregator.add_event(
                title=title, text=text, alert_type=alert_type, aggregation_key=aggregation_key,
                source_type_name=source_type_name, date_happened=date_happened, priority=priority,
                tags=event_tags, host=hostname)

    def gauge(self, metric_name, value, timestamp=None, tags=None, sample_rate=1, host=None):
        """
        Record the current ``value`` of a metric. The most recent value in
        a given flush interval will be recorded. Optionally, specify a set of
        tags to associate with the metric. This should be used for sum values
        such as total hard disk space, process uptime, total number of active
        users, or number of rows in a database table.

        >>> stats.gauge('process.uptime', time.time() - process_start_time)
        >>> stats.gauge('cache.bytes.free', cache.get_free_bytes(), tags=['version:1.0'])
        """
        if not self._disabled:
            self._metric_aggregator.add_point(metric_name, tags, timestamp or time(), value, Gauge,
                                              sample_rate=sample_rate, host=host)

    def increment(self, metric_name, value=1, timestamp=None, tags=None, sample_rate=1, host=None):
        """
        Increment the counter by the given ``value``. Optionally, specify a list of
        ``tags`` to associate with the metric. This is useful for counting things
        such as incrementing a counter each time a page is requested.

        >>> stats.increment('home.page.hits')
        >>> stats.increment('bytes.processed', file.size())
        """
        if not self._disabled:
            self._metric_aggregator.add_point(metric_name, tags, timestamp or time(), value,
                                              Counter, sample_rate=sample_rate, host=host)

    def decrement(self, metric_name, value=1, timestamp=None, tags=None, sample_rate=1, host=None):
        """
        Decrement a counter, optionally setting a value, tags and a sample
        rate.

        >>> stats.decrement('files.remaining')
        >>> stats.decrement('active.connections', 2)
        """
        if not self._disabled:
            self._metric_aggregator.add_point(metric_name, tags, timestamp or time(), -value,
                                              Counter, sample_rate=sample_rate, host=host)

    def histogram(self, metric_name, value, timestamp=None, tags=None, sample_rate=1, host=None):
        """
        Sample a histogram value. Histograms will produce metrics that
        describe the distribution of the recorded values, namely the maximum,
        median, average, count and the 95th percentile. Optionally, specify
        a list of ``tags`` to associate with the metric.

        >>> stats.histogram('uploaded_file.size', uploaded_file.size())
        """
        if not self._disabled:
            self._metric_aggregator.add_point(metric_name, tags, timestamp or time(), value,
                                              Histogram, sample_rate=sample_rate, host=host)

    def timing(self, metric_name, value, timestamp=None, tags=None, sample_rate=1, host=None):
        """
        Record a timing, optionally setting tags and a sample rate.

        >>> stats.timing("query.response.time", 1234)
        """
        if not self._disabled:
            self._metric_aggregator.add_point(metric_name, tags, timestamp or time(), value,
                                              Timing, sample_rate=sample_rate, host=host)

    @contextmanager
    def timer(self, metric_name, sample_rate=1, tags=None, host=None):
        """
        A context manager that will track the distribution of the contained code's run time.
        Optionally specify a list of tags to associate with the metric.
        ::

            def get_user(user_id):
                with stats.timer('user.query.time'):
                    # Do what you need to ...
                    pass

            # Is equivalent to ...
            def get_user(user_id):
                start = time.time()
                try:
                    # Do what you need to ...
                    pass
                finally:
                    stats.histogram('user.query.time', time.time() - start)
        """
        start = time()
        try:
            yield
        finally:
            end = time()
            self.timing(metric_name, end - start, end, tags=tags,
                        sample_rate=sample_rate, host=host)

    def timed(self, metric_name, sample_rate=1, tags=None, host=None):
        """
        A decorator that will track the distribution of a function's run time.
        Optionally specify a list of tags to associate with the metric.
        ::

            @stats.timed('user.query.time')
            def get_user(user_id):
                # Do what you need to ...
                pass

            # Is equivalent to ...
            start = time.time()
            try:
                get_user(user_id)
            finally:
                stats.histogram('user.query.time', time.time() - start)
        """
        def wrapper(func):
            @wraps(func)
            def wrapped(*args, **kwargs):
                with self.timer(metric_name, sample_rate, tags, host):
                    result = func(*args, **kwargs)
                    return result
            return wrapped
        return wrapper

    def flush(self, timestamp=None):
        """
        Flush and post all metrics to the server. Note that this is a blocking
        call, so it is likely not suitable for user facing processes. In those
        cases, it's probably best to flush in a thread or greenlet.
        """
        try:
            if self._is_flush_in_progress:
                log.debug("A flush is already in progress. Skipping this one.")
                return False
            if self._disabled:
                log.info("Not flushing because we're disabled.")
                return False

            self._is_flush_in_progress = True

            # Process metrics
            metrics = self._get_aggregate_metrics(timestamp or time())
            count_metrics = len(metrics)
            if count_metrics:
                self.flush_count += 1
                log.debug("Flush #%s sending %s metrics" % (self.flush_count, count_metrics))
                self.reporter.flush_metrics(metrics)
            else:
                log.debug("No metrics to flush. Continuing.")

            # Process events
            events = self._get_aggregate_events()
            count_events = len(events)
            if count_events:
                self.flush_count += 1
                log.debug("Flush #%s sending %s events" % (self.flush_count, count_events))
                self.reporter.flush_events(events)
            else:
                log.debug("No events to flush. Continuing.")
        except ApiNotInitialized:
            raise
        except Exception:
            try:
                log.exception("Error flushing metrics and events")
            except Exception:
                pass
        finally:
            self._is_flush_in_progress = False

    def _get_aggregate_metrics(self, flush_time=None):
        """
        Get, format and return the rolled up metrics from the aggregator.
        """
        # Get rolled up metrics
        rolled_up_metrics = self._metric_aggregator.flush(flush_time)

        # FIXME: emit a dictionary from the aggregator
        metrics = []
        for timestamp, value, name, tags, host, metric_type, interval in rolled_up_metrics:
            metric_tags = tags
            metric_name = name

            # Append all client level tags to every metric
            if self.constant_tags:
                if tags:
                    metric_tags = tags + self.constant_tags
                else:
                    metric_tags = self.constant_tags

            # Resolve the metric name
            if self.namespace:
                metric_name = self.namespace + "." + name

            metric = {
                'metric': metric_name,
                'points': [[timestamp, value]],
                'type': metric_type,
                'host': host,
                'device': self.device,
                'tags': metric_tags,
                'interval': interval
            }
            metrics.append(metric)
        return metrics

    def _get_aggregate_events(self):
        # Get events
        events = self._event_aggregator.flush()
        return events

    def _start_flush_thread(self):
        """ Start a thread to flush metrics. """
        from datadog.threadstats.periodic_timer import PeriodicTimer
        if self._is_auto_flushing:
            log.info("Autoflushing already started.")
            return
        self._is_auto_flushing = True

        # A small helper for logging and flushing.
        def flush():
            try:
                log.debug("Flushing metrics in thread")
                self.flush()
            except:
                try:
                    log.exception("Error flushing in thread")
                except:
                    pass

        log.info("Starting flush thread with interval %s." % self.flush_interval)
        self._flush_thread = PeriodicTimer(self.flush_interval, flush)
        self._flush_thread.start()

    def _start_flush_greenlet(self):
        if self._is_auto_flushing:
            log.info("Autoflushing already started.")
            return
        self._is_auto_flushing = True

        import gevent

        # A small helper for flushing.
        def flush():
            while True:
                try:
                    log.debug("Flushing metrics in greenlet")
                    self.flush()
                    gevent.sleep(self.flush_interval)
                except:
                    try:
                        log.exception("Error flushing in greenlet")
                    except:
                        pass

        log.info("Starting flush greenlet with interval %s." % self.flush_interval)
        gevent.spawn(flush)
