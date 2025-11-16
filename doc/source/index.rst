#########################################
:mod:`datadog` --- Datadog Python library
#########################################

.. module:: datadog

The :mod:`datadog` module provides
  - :mod:`datadog.api`: A client for Datadog's HTTP API.
  - :mod:`datadog.dogstatsd`: A UDP/UDS DogStatsd client.
  - :mod:`datadog.threadstats`: A client for Datadog’s HTTP API that submits metrics in a
    worker thread.


Installation
============

Install from PyPI::

    pip install datadog


Initialization
==============

:mod:`datadog` must be initialized with :meth:`datadog.initialize`. An
API key and an app key are required unless you intend to use only the
:class:`~datadog.dogstatsd.base.DogStatsd` client. The keys can be passed
explicitly to :meth:`datadog.initialize` or defined as environment variables
``DATADOG_API_KEY`` and ``DATADOG_APP_KEY`` respectively.

Here's an example where the statsd host and port are configured as well::

    from datadog import initialize

    initialize(
        api_key="<your api key>",
        app_key="<your app key>",
        statsd_host="127.0.0.1",
        statsd_port=8125
    )


If statsd_host and statsd_port are left at their default values and no socket_path alternative is supplied, 
the DD_DOGSTATSD_URL environment variable, if it exists, will be used to determine the connection
information. This must be a URL that start with either `udp://` (to connect using UDP) or with `unix://` 
(to use a Unix Domain Socket).

* Example for UDP url: `DD_DOGSTATSD_URL=udp://localhost:8125`
* Example for UDS: `DD_DOGSTATSD_URL=unix:///var/run/datadog/dsd.socket`


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
:mod:`datadog.threadstats` is a tool for collecting application metrics without hindering
performance. It collects metrics in the application thread with very little overhead
and allows flushing metrics in process, in a thread, or in a greenlet, depending
on your application's needs. Submission is done through the HTTP API.

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
:mod:`datadog.dogstatsd` is a Python client for DogStatsd that submits metrics
to the Agent.


Usage
~~~~~

::

    from datadog.dogstatsd import DogStatsd
    
    client = DogStatsd()
    client.increment("home.page.hits")


.. autoclass::  datadog.dogstatsd.base.DogStatsd
    :members:
    :inherited-members:


.. data:: statsd

    A global :class:`~datadog.dogstatsd.base.DogStatsd` instance that can be
    used across an application::

    >>> from datadog import initialize, statsd
    >>> initialize(statsd_host="localhost", statsd_port=8125)
    >>> statsd.increment("home.page.hits")

.. data:: datadog.dogstatsd.base.SUPPORTS_FORKING

    Indicates whether the Python runtime supports os.register_at_fork(). When
    true, buffering and background sender can be safely used in applications
    that use os.fork().

.. autofunction:: datadog.dogstatsd.base.pre_fork
.. autofunction:: datadog.dogstatsd.base.post_fork


Get in Touch
============

If you'd like to suggest a feature or report a bug, please submit an issue
`here <https://github.com/DataDog/datadogpy/issues>`_. If you have questions
about Datadog in general, reach out to support@datadoghq.com.
