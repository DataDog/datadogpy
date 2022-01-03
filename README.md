# The Datadog Python library

[![Unit Tests](https://dev.azure.com/datadoghq/datadogpy/_apis/build/status/DataDog.datadogpy.unit?branchName=master)](https://dev.azure.com/datadoghq/datadogpy/_build/latest?definitionId=10&branchName=master)
[![Integration Tests](https://dev.azure.com/datadoghq/datadogpy/_apis/build/status/DataDog.datadogpy.integration?branchName=master)](https://dev.azure.com/datadoghq/datadogpy/_build/latest?definitionId=13&branchName=master)
[![Documentation Status](https://readthedocs.org/projects/datadogpy/badge/?version=latest)](https://readthedocs.org/projects/datadogpy/?badge=latest)
[![PyPI - Version](https://img.shields.io/pypi/v/datadog.svg)](https://pypi.org/project/datadog)
[![PyPI - Downloads](https://pepy.tech/badge/datadog)](https://pepy.tech/project/datadog)

The Datadog Python Library is a collection of tools suitable for inclusion in existing Python projects or for the development of standalone scripts. It provides an abstraction on top of Datadog's raw HTTP interface and the Agent's DogStatsD metrics aggregation server, to interact with Datadog and efficiently report events and metrics.

- Library Documentation: https://datadogpy.readthedocs.io/en/latest/
- HTTP API Documentation: https://docs.datadoghq.com/api/
- DatadogHQ: https://datadoghq.com

See [CHANGELOG.md](https://github.com/DataDog/datadogpy/blob/master/CHANGELOG.md) for changes.

## Installation

To install from pip:

    pip install datadog

To install from source:

    python setup.py install

## Datadog API

To support all Datadog HTTP APIs, a generated library is
available which will expose all the endpoints:
[datadog-api-client-python](https://github.com/DataDog/datadog-api-client-python).

Find below a working example for submitting an event to your Event Stream:

```python
from datadog import initialize, api

options = {
    "api_key": "<YOUR_API_KEY>",
    "app_key": "<YOUR_APP_KEY>",
}

initialize(**options)

title = "Something big happened!"
text = "And let me tell you all about it here!"
tags = ["version:1", "application:web"]

api.Event.create(title=title, text=text, tags=tags)
```

**Consult the full list of supported Datadog API endpoints with working code examples in [the Datadog API documentation](https://docs.datadoghq.com/api/latest/?code-lang=python).**

**Note**: The full list of available Datadog API endpoints is also available in the [Datadog Python Library documentation](https://datadogpy.readthedocs.io/en/latest/)

#### Environment Variables

As an alternate method to using the `initialize` function with the `options` parameters, set the environment variables `DATADOG_API_KEY` and `DATADOG_APP_KEY` within the context of your application.

If `DATADOG_API_KEY` or `DATADOG_APP_KEY` are not set, the library attempts to fall back to Datadog's APM environment variable prefixes: `DD_API_KEY` and `DD_APP_KEY`.

```python
from datadog import initialize, api

# Assuming you've set `DD_API_KEY` and `DD_APP_KEY` in your env,
# initialize() will pick it up automatically
initialize()

title = "Something big happened!"
text = "And let me tell you all about it here!"
tags = ["version:1", "application:web"]

api.Event.create(title=title, text=text, tags=tags)
```

In development, you can disable any `statsd` metric collection using `DD_DOGSTATSD_DISABLE=True` (or any not-empty value).

## DogStatsD

In order to use DogStatsD metrics, the Agent must be [running and available](https://docs.datadoghq.com/developers/dogstatsd/?code-lang=python).

### Instantiate the DogStatsD client with UDP

Once the Datadog Python Library is installed, instantiate the StatsD client using UDP in your code:

```python
from datadog import initialize, statsd

options = {
    "statsd_host": "127.0.0.1",
    "statsd_port": 8125,
}

initialize(**options)
```

See the full list of available [DogStatsD client instantiation parameters](https://docs.datadoghq.com/developers/dogstatsd/?code-lang=python#client-instantiation-parameters).

#### Instantiate the DogStatsd client with UDS

Once the Datadog Python Library is installed, instantiate the StatsD client using UDS in your code:
```python

from datadog import initialize, statsd

options = {
    "statsd_socket_path": PATH_TO_SOCKET,
}

initialize(**options)
```

#### Origin detection over UDP and UDS

Origin detection is a method to detect which pod `DogStatsD` packets are coming from in order to add the pod's tags to the tag list.
The `DogStatsD` client attaches an internal tag, `entity_id`. The value of this tag is the content of the `DD_ENTITY_ID` environment variable if found, which is the pod's UID. The Datadog Agent uses this tag to add container tags to the metrics. To avoid overwriting this global tag, make sure to only `append` to the `constant_tags` list.

To enable origin detection over UDP, add the following lines to your application manifest
```yaml
env:
  - name: DD_ENTITY_ID
    valueFrom:
      fieldRef:
        fieldPath: metadata.uid
```

### Usage
#### Metrics

After the client is created, you can start sending custom metrics to Datadog. See the dedicated [Metric Submission: DogStatsD documentation](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python) to see how to submit all supported metric types to Datadog with working code examples:

* [Submit a COUNT metric](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#count).
* [Submit a GAUGE metric](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#gauge).
* [Submit a SET metric](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#set)
* [Submit a HISTOGRAM metric](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#histogram)
* [Submit a TIMER metric](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#timer)
* [Submit a DISTRIBUTION metric](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#distribution)

Some options are supported when submitting metrics, like [applying a Sample Rate to your metrics](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#metric-submission-options) or [tagging your metrics with your custom tags](https://docs.datadoghq.com/metrics/dogstatsd_metrics_submission/?code-lang=python#metric-tagging).

#### Events

After the client is created, you can start sending events to your Datadog Event Stream. See the dedicated [Event Submission: DogStatsD documentation](https://docs.datadoghq.com/events/guides/dogstatsd/?code-lang=python) to see how to submit an event to your Datadog Event Stream.

#### Service Checks

After the client is created, you can start sending Service Checks to Datadog. See the dedicated [Service Check Submission: DogStatsD documentation](https://docs.datadoghq.com/developers/service_checks/dogstatsd_service_checks_submission/?code-lang=python) to see how to submit a Service Check to Datadog.

### Monitoring this client

This client automatically injects telemetry about itself in the DogStatsD stream.
Those metrics will not be counted as custom and will not be billed. This feature can be disabled using the `statsd.disable_telemetry()` method.

See [Telemetry documentation](https://docs.datadoghq.com/developers/dogstatsd/high_throughput/?code-lang=python#client-side-telemetry) to learn more about it.

### Benchmarks

_Note: You will need to install `psutil` package before running the benchmarks._

If you would like to get an approximate idea on the throughput that your DogStatsD library
can handle on your system, you can run the included local benchmark code:

```sh-session
$ # Python 2 Example
$ python2 -m unittest -vvv tests.performance.test_statsd_throughput

$ # Python 3 Example
$ python3 -m unittest -vvv tests.performance.test_statsd_throughput
```

You can also add set `BENCHMARK_*` to customize the runs:
```sh-session
$ # Example #1
$ BENCHMARK_NUM_RUNS=10 BENCHMARK_NUM_THREADS=1 BENCHMARK_NUM_DATAPOINTS=5000 BENCHMARK_TRANSPORT="UDP" python2 -m unittest -vvv tests.performance.test_statsd_throughput

$ # Example #2
$ BENCHMARK_NUM_THREADS=10 BENCHMARK_TRANSPORT="UDS" python3 -m unittest -vvv tests.performance.test_statsd_throughput
```

## Maximum packets size in high-throughput scenarios

In order to have the most efficient use of this library in high-throughput scenarios,
default values for the maximum packets size have already been set for both UDS (8192 bytes)
and UDP (1432 bytes) in order to have the best usage of the underlying network.
However, if you perfectly know your network and you know that a different value for the maximum packets
size should be used, you can set it with the parameter `max_buffer_len`. Example:

```python
from datadog import initialize

options = {
    "api_key": "<YOUR_API_KEY>",
    "app_key": "<YOUR_APP_KEY>",
    "max_buffer_len": 4096,
}

initialize(**options)
```

## Thread Safety

`DogStatsD` and `ThreadStats` are thread-safe.
