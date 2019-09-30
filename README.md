The Datadog Python library
===========================
[![Unit Tests](https://dev.azure.com/datadoghq/datadogpy/_apis/build/status/DataDog.datadogpy.unit?branchName=master)](https://dev.azure.com/datadoghq/datadogpy/_build/latest?definitionId=10&branchName=master)
[![Integration Tests](https://dev.azure.com/datadoghq/datadogpy/_apis/build/status/DataDog.datadogpy.integration?branchName=master)](https://dev.azure.com/datadoghq/datadogpy/_build/latest?definitionId=13&branchName=master)
[![Documentation Status](https://readthedocs.org/projects/datadogpy/badge/?version=latest)](https://readthedocs.org/projects/datadogpy/?badge=latest)
[![PyPI - Version](https://img.shields.io/pypi/v/datadog.svg)](https://pypi.org/project/datadog)
[![PyPI - Downloads](https://pepy.tech/badge/datadog)](https://pepy.tech/project/datadog)

Datadogpy is a collection of tools suitable for inclusion in existing Python projects or for development of standalone scripts. It provides an abstraction on top of Datadog's raw HTTP interface and the Agent's StatsD metrics aggregation server, to interact with Datadog and efficiently report events and metrics.

For usage of StatsD metrics, the Agent must be [running and available](https://docs.datadoghq.com/developers/dogstatsd/).

- Library Documentation: http://datadogpy.readthedocs.org/en/latest/
- HTTP API Documentation: http://docs.datadoghq.com/api/
- DatadogHQ: http://datadoghq.com

See [CHANGELOG.md](CHANGELOG.md) for changes.

Installation
------------
To install from pip:

    pip install datadog

To install from source:

    python setup.py install


Quick Start Guide
-----------------
```python
# Configure the module according to your needs
from datadog import initialize

options = {
    'api_key':'api_key',
    'app_key':'app_key'
}

initialize(**options)

# Use Datadog REST API client
from datadog import api

title = "Something big happened!"
text = 'And let me tell you all about it here!'
tags = ['version:1', 'application:web']

api.Event.create(title=title, text=text, tags=tags)


# Use Statsd, a Python client for DogStatsd
from datadog import statsd

# Uncomment to set namespace or add tags to everything
# statsd.namespace = 'localdev'
# statsd.constant_tags = ['testing', 'dogstats']

statsd.increment('whatever')
statsd.gauge('foo', 42)

# Or ThreadStats, an alternative tool to collect and flush metrics, using Datadog REST API
from datadog import ThreadStats
stats = ThreadStats()
stats.start()
stats.increment('home.page.hits')

```

Environment Variables
---------------------

As an alternate method to using the `initialize` function with the `options` parameters, set the environment variables `DATADOG_API_KEY` and `DATADOG_APP_KEY` within the context of your application.

If `DATADOG_API_KEY` or `DATADOG_APP_KEY` are not set, the library will attempt to fall back to Datadog's APM environmnent variable prefixes: `DD_API_KEY` and `DD_APP_KEY`.

```python
from datadog import initialize, api

# Assuming you've set `DD_API_KEY` and `DD_APP_KEY` in your env,
# initialize() will pick it up automatically
initialize()

title = "Something big happened!"
text = 'And let me tell you all about it here!'
tags = ['version:1', 'application:web']

api.Event.create(title=title, text=text, tags=tags)
```

Thread Safety
-------------
`DogStatsD` and `ThreadStats` are thread-safe.

Origin detection over UDP
-------------
Origin detection is a method to detect which pod `DogStatsD` packets are coming from in order to add the pod's tags to the tag list.
The `DogStatsD` client attaches an internal tag, `entity_id`. The value of this tag is the content of the `DD_ENTITY_ID` environment variable if found, which is the pod's UID.
This tag will be used by the Datadog Agent to insert container tags to the metrics. You should only `append` to the `constant_tags` list to avoid overwriting this global tag.

To enable origin detection over UDP, add the following lines to your application manifest
```yaml
env:
  - name: DD_ENTITY_ID
    valueFrom:
      fieldRef:
        fieldPath: metadata.uid
```
