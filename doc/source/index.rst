#########################################
:mod:`datadog` --- Datadog Python library
#########################################

.. module:: datadog

The :mod:`datadog` module provides
  - :mod:`datadog.api`: a client for Datadog's HTTP API.
  - :mod:`datadog.dogstatsd`: a DogStatsd client.
  - :mod:`datadog.threadstats`: a DogStatsd client that submits metrics in a
    worker thread.


Installation
============

Install from PyPI::

    pip install datadog


Initialization
==============

:mod:`datadog` must be initialized with :meth:`datadog.initialize`. An API key
and an app key are required. These can be passed explicitly to
:meth:`datadog.initialize` or defined as environment variables
``DATADOG_API_KEY`` and ``DATADOG_APP_KEY`` respectively.

Here's an example where the statsd host and port are configured as well::

    from datadog import initialize

    initialize(
        api_key="<your api key>",
        app_key="<your app key>",
        statsd_host: "127.0.0.1",
        statsd_port: 8125
    )


.. autofunction:: datadog.initialize


datadog.api
===========
:mod:`datadog.api` is a Python client library for Datadog's `HTTP API
<http://api.datadoghq.com>`_.


Usage
~~~~~

Be sure to initialize the client using :meth:`datadog.initialize` and then use
:mod:`datadog.api`::

    from datadog import api

    api.Event.create(
        title="Something big happened!",
        text="And let me tell you all about it here!",
        tags=["version:1", "application:web"],
    )


.. autoclass:: datadog.api.Comment
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Downtime
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Event
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Graph
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Host
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Hosts
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Infrastructure
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Metric
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Monitor
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Screenboard
    :members:
    :inherited-members:

.. autoclass:: datadog.api.ServiceCheck
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Tag
    :members:
    :inherited-members:

.. autoclass:: datadog.api.Timeboard
    :members:
    :inherited-members:

.. autoclass:: datadog.api.User
    :members:
    :inherited-members:
    :exclude-members: invite

.. autoclass:: datadog.api.Dashboard
    :members:
    :inherited-members:

.. autoclass:: datadog.api.DashboardList
    :members:
    :inherited-members:


datadog.threadstats
===================
:mod:`datadog.threadstats` is a DogStatsd client that aggregates metrics when
possible and submits them asynchronously in order to minimize the performance
impact on the application. Submitting metrics can be done with a worker thread
or in a greenlet.


Usage
~~~~~

Be sure to initialize the library with :meth:`datadog.initialize`. Then create
an instance of :class:`datadog.threadstats.ThreadStats`::

    from datadog.threadstats import ThreadStats

    statsd = ThreadStats()
    statsd.start()  # Creates a worker thread used to submit metrics.

    # Use statsd just like any other DatadogStatsd client.
    statsd.increment("home.page.hits")


.. autoclass::  datadog.threadstats.base.ThreadStats
    :members:
    :inherited-members:


datadog.dogstatsd
=================

.. autoclass::  datadog.dogstatsd.base.DogStatsd
    :members:
    :inherited-members:


.. data:: statsd

    A global :class:`~datadog.dogstatsd.base.DogStatsd` instance that can be
    used across an application::

    >>> from datadog import initialize, statsd
    >>> initialize(statsd_host="localhost", statsd_port=8125)
    >>> statsd.increment("home.page.hits")


Get in Touch
============

If you'd like to suggest a feature or report a bug, please submit an issue
`here <https://github.com/DataDog/datadogpy/issues>`_. If you have questions
about Datadog in general, reach out to support@datadoghq.com.
