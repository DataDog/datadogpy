import time

from datadog import lambda_metric, datadog_lambda_wrapper


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
