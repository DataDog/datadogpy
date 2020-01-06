# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import time
# import unittest
import threading

from datadog import lambda_metric, datadog_lambda_wrapper
from datadog.threadstats.aws_lambda import _lambda_stats


TOTAL_NUMBER_OF_THREADS = 1000


class MemoryReporter(object):
    """ A reporting class that reports to memory for testing. """

    def __init__(self):
        self.distributions = []
        self.dist_flush_counter = 0

    def flush_distributions(self, dists):
        self.distributions += dists
        self.dist_flush_counter = self.dist_flush_counter + 1


@datadog_lambda_wrapper
def wrapped_function(id):
    lambda_metric("dist_" + str(id), 42)
    # sleep makes the os continue another thread
    time.sleep(0.001)

    lambda_metric("common_dist", 42)


# Lambda wrapper - mute thread safety test, python 2.7 issues
# class TestWrapperThreadSafety(unittest.TestCase):

#     def test_wrapper_thread_safety(self):
#         _lambda_stats.reporter = MemoryReporter()

#         for i in range(TOTAL_NUMBER_OF_THREADS):
#             threading.Thread(target=wrapped_function, args=[i]).start()
#         # Wait all threads to finish
#         time.sleep(10)

#         # Check that at least one flush happened
#         self.assertGreater(_lambda_stats.reporter.dist_flush_counter, 0)

#         dists = _lambda_stats.reporter.distributions
#         self.assertEqual(len(dists), TOTAL_NUMBER_OF_THREADS + 1)
