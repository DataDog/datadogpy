The Datadog Python library
===========================
[![Build Status](https://travis-ci.org/DataDog/datadogpy.svg?branch=master)](https://travis-ci.org/DataDog/datadogpy)

Datadogpy is a collection of tools suitable for inclusion in existing Python projects or for development of standalone scripts. It provides an abstraction on top of Datadog's raw HTTP interface and agent's StatsD metrics aggregation server, to interact with Datadog and efficiently report events and metrics.

- Library Documentation: http://datadogpy.readthedocs.org/en/latest/
- DatadogHQ: http://datadoghq.com

Installation
------------
To install from source, run:

    python setup.py install


Quick Start Guide
-----------------
``` python
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

statsd.increment('whatever')
statsd.gauge('foo')

# Or ThreadStats, an alternative tool to collect and flush metrics, using Datadog REST API
from datadog import ThreadStats
stats = ThreadStats()
stats.start()
stats.increment('home.page.hits')

```


Change Log
----------
- 0.2.dev
    - Release date: 2015.02.17
    - Split DogStats to DogStatsd and ThreadStats
    - Merge last changes from Dogapi and statsd repositories
    - A lot of renaming
- 0.1.dev
    - Release date: 2015.01.27
    - Datadogpy beta release
