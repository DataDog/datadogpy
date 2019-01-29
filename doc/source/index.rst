###############################################
:mod:`datadog` --- The Datadog's Python library
###############################################

.. module:: datadog

The :mod:`datadog` module provides :mod:`datadog.api` - a simple wrapper around Datadog's HTTP API - :mod:`datadog.threadstats` - a tool for collecting metrics in high performance applications - and :mod:`datadog.dogstatsd` a DogStatsd Python client.

Installation
============

To install from source, `download <https://github.com/DataDog/datadogpy>`_ a distribution and run:

   >>> sudo python setup.py install

If you use `virtualenv <http://pypi.python.org/pypi/virtualenv>`_ you do not need to use sudo.

Datadog.api module
==================
Datadog.api is a Python client library for Datadog's `HTTP API <http://api.datadoghq.com>`_.

Datadog.api client requires to run :mod:`datadog` `initialize` method first.


.. autofunction:: datadog.initialize

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


Datadog.threadstats module
==========================
Datadog.threadstats is a tool for collecting application metrics without hindering performance.
It collects metrics in the application thread with very little overhead and allows flushing
metrics in process, in a thread or in a greenlet, depending on your application's needs.

To run properly Datadog.threadstats requires to run :mod:`datadog` `initialize` method first.

.. autofunction:: datadog.initialize

.. autoclass::  datadog.threadstats.base.ThreadStats
    :members:
    :inherited-members:

Datadog.dogstatsd module
==========================

.. autoclass::  datadog.dogstatsd.base.DogStatsd
    :members:
    :inherited-members:


.. data:: statsd

    A global :class:`~datadog.dogstatsd.base.DogStatsd` instance that is easily shared
    across an application's modules. Initialize this once in your application's
    set-up code and then other modules can import and use it without further
    configuration.

    >>> from datadog import initialize, statsd
    >>> initialize(statsd_host='localhost', statsd_port=8125)
    >>> statsd.increment('home.page.hits')



Source
======

The Datadog's Python library source is freely available on Github. Check it out `here
<https://github.com/DataDog/datadogpy>`_.

Get in Touch
============

If you'd like to suggest a feature or report a bug, please add an issue `here <https://github.com/DataDog/datadogpy/issues>`_. If you want to talk about Datadog in general, reach out at `datadoghq.com <http://datadoghq.com>`_.
