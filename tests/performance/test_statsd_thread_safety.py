# stdlib
from collections import deque
from functools import reduce
import threading
import time
import unittest

# 3p
from mock import patch

# datadog
from datadog.dogstatsd.base import DogStatsd
from datadog.util.compat import is_p3k


class FakeSocket(object):
    """
    Mocked socket for testing.
    """
    def __init__(self):
        self.payloads = deque()

    def send(self, payload):
        if is_p3k():
            assert type(payload) == bytes
        else:
            assert type(payload) == str

        self.payloads.append(payload)

    def recv(self):
        try:
            return self.payloads
        except IndexError:
            return None

    def __repr__(self):
        return str(self.payloads)


class TestDogStatsdThreadSafety(unittest.TestCase):
    """
    DogStatsd thread safety tests.
    """
    def setUp(self):
        """
        Mock a socket.
        """
        self.socket = FakeSocket()

    def assertMetrics(self, values):
        """
        Helper, assertions on metrics.
        """
        count = len(values)

        # Split packet per metric (required when buffered) and discard empty packets
        packets = map(lambda x: x.split(b"\n"), self.socket.recv())
        packets = reduce(lambda prev, ele: prev + ele, packets, [])
        packets = list(filter(lambda x: x, packets))

        # Count
        self.assertEquals(
            len(packets), count,
            u"Metric size assertion failed: expected={expected}, received={received}".format(
                expected=count, received=len(packets)
            )
        )
        # Values
        for packet in packets:
            metric_value = int(packet.split(b':', 1)[1].split(b'|', 1)[0])
            self.assertIn(
                metric_value, values,
                u"Metric assertion failed: unexpected metric value {metric_value}".format(
                    metric_value=metric_value
                )
            )
            values.remove(metric_value)

    def test_socket_creation(self):
        """
        Socket creation plays well with multiple threads.
        """
        # Create a DogStatsd client but no socket
        statsd = DogStatsd()

        # Submit metrics from different threads to create a socket
        threads = []
        for value in range(10000):
            t = threading.Thread(target=statsd.gauge, args=("foo", value))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    @staticmethod
    def _submit_with_multiple_threads(statsd, submit_method, values):
        """
        Helper, use the given statsd client and method to submit the values
        within multiple threads.
        """
        threads = []
        for value in values:
            t = threading.Thread(
                target=getattr(statsd, submit_method),
                args=("foo", value)
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def test_increment(self):
        """
        Increments can be submitted from concurrent threads.
        """
        # Create a DogStatsd client with a mocked socket
        statsd = DogStatsd()
        statsd.socket = self.socket

        # Samples
        values = set(range(10000))

        # Submit metrics from different threads
        self._submit_with_multiple_threads(statsd, "increment", values)

        #  All metrics were properly submitted
        self.assertMetrics(values)

    def test_decrement(self):
        """
        Decrements can be submitted from concurrent threads.
        """
        # Create a DogStatsd client with a mocked socket
        statsd = DogStatsd()
        statsd.socket = self.socket

        # Samples
        values = set(range(10000))
        expected_value = set([-value for value in values])

        # Submit metrics from different threads
        self._submit_with_multiple_threads(statsd, "decrement", expected_value)

        #  All metrics were properly submitted
        self.assertMetrics(values)

    def test_gauge(self):
        """
        Gauges can be submitted from concurrent threads.
        """
        # Create a DogStatsd client with a mocked socket
        statsd = DogStatsd()
        statsd.socket = self.socket

        # Samples
        values = set(range(10000))

        # Submit metrics from different threads
        self._submit_with_multiple_threads(statsd, "gauge", values)

        #  All metrics were properly submitted
        self.assertMetrics(values)

    def test_histogram(self):
        """
        Histograms can be submitted from concurrent threads.
        """
        # Create a DogStatsd client with a mocked socket
        statsd = DogStatsd()
        statsd.socket = self.socket

        # Samples
        values = set(range(10000))

        # Submit metrics from different threads
        self._submit_with_multiple_threads(statsd, "histogram", values)

        #  All metrics were properly submitted
        self.assertMetrics(values)

    def test_timing(self):
        """
        Timings can be submitted from concurrent threads.
        """
        # Create a DogStatsd client with a mocked socket
        statsd = DogStatsd()
        statsd.socket = self.socket

        # Samples
        values = set(range(10000))

        # Submit metrics from different threads
        self._submit_with_multiple_threads(statsd, "timing", values)

        # All metrics were properly submitted
        self.assertMetrics(values)

    def test_send_batch_metrics(self):
        """
        Metrics can be buffered, submitted from concurrent threads.
        """
        with DogStatsd() as batch_statsd:
            # Create a DogStatsd buffer client with a mocked socket
            batch_statsd.socket = self.socket

            # Samples
            values = set(range(10000))

            # Submit metrics from different threads
            self._submit_with_multiple_threads(batch_statsd, "gauge", values)

        # All metrics were properly submitted
        self.assertMetrics(values)

    @patch('datadog.dogstatsd.context.time')
    def test_timed_decorator_threaded(self, mock_time):
        """
        `timed` decorator plays well with concurrent threads.
        """
        # Create a DogStatsd client with a mocked socket
        statsd = DogStatsd()
        statsd.socket = self.socket

        # Set up the mocked time
        mock_time.return_value = 0

        # Method to time
        @statsd.timed("foo")
        def bar():
            """
            Wait 5 time units and return.
            """
            initial_time = mock_time.return_value
            while mock_time.return_value < initial_time + 2:
                pass

        # Run the method within multiple threads
        threads = []
        for value in range(10):
            t = threading.Thread(target=bar)
            threads.append(t)
            # Bump time so that previous thread can complete
            mock_time.return_value += 1
            t.start()
            # Sleep to let the threads start
            time.sleep(0.1)

        # Bump time so that all threads completes
        time.sleep(0.1)
        mock_time.return_value += 1
        time.sleep(0.1)
        mock_time.return_value += 1

        for t in threads:
            t.join()

        # All metrics were properly submitted
        expected_values = [2 for _ in range(0, 10)]
        self.assertMetrics(expected_values)

    @patch('datadog.dogstatsd.context.time')
    def test_timed_context_manager_threaded(self, mock_time):
        """
        `timed` context manager plays well with concurrent threads.
        """
        # Create a DogStatsd client with a mocked socket
        statsd = DogStatsd()
        statsd.socket = self.socket

        # Set up the mocked time
        mock_time.return_value = 0

        # Method to time
        def bar():
            """
            Wait 5 time units and return.
            """
            initial_time = mock_time.return_value

            with statsd.timed("foo"):
                while mock_time.return_value < initial_time + 2:
                    pass

        # Run the method within multiple threads
        threads = []
        for value in range(10):
            t = threading.Thread(target=bar)
            threads.append(t)
            # Bump time so that previous thread can complete
            mock_time.return_value += 1
            t.start()
            # Sleep to let the threads start
            time.sleep(0.1)

        # Bump time so that all threads completes
        time.sleep(0.1)
        mock_time.return_value += 1
        time.sleep(0.1)
        mock_time.return_value += 1

        for t in threads:
            t.join()

        # All metrics were properly submitted
        expected_values = [2 for _ in range(0, 10)]
        self.assertMetrics(expected_values)
