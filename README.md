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

# Use Datadog HTTP API client
from datadog import api

title = "Something big happened!"
text = 'And let me tell you all about it here!'
tags = ['version:1', 'application:web']

api.Event.create(title=title, text=text, tags=tags)


# Use Stats to efficiently collect metrics
from datadog import stats

stats.increment('whatever')
stats.gauge('foo')
```


Change Log
----------
- 0.1 RC
    - Release date: 2015.01.27
    - Datadogpy beta release
