# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import time
# import unittest
# import threading

from datadog import lambda_metric, datadog_lambda_wrapper
# from datadog.threadstats.aws_lambda import _lambda_stats


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
