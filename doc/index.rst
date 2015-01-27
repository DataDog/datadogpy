%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
:mod:`datadog` --- Datadog's Python API
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

.. module:: datadog

The :mod:`datadog` module provides :mod:`datadog.api` - a simple wrapper around Datadog's HTTP API - and :mod:`datadog.statsd` - a tool for collecting metrics in high performance applications.

Installation
============

The module can be downloaded from PyPI and installed in one step with
easy_install:

    >>> sudo easy_install

Or with pip:

    >>> sudo pip install

To install from source, `download <https://github.com/DataDog/datadog.py>`_ a distribution and run:

   >>> sudo python setup.py install

If you use `virtualenv <http://pypi.python.org/pypi/virtualenv>`_ you do not need to use sudo.

Datadog.api module
==================
Datadog.api is a Python client library for Datadog's `HTTP API <http://api.datadoghq.com>`_.

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


Datadog.statsd module
==================

.. automodule:: datadog.statsd.statsd

.. autoclass::  datadog.statsd.DogStatsd

    .. automethod:: connect

    .. automethod:: gauge

    .. automethod:: increment

    .. automethod:: decrement

    .. automethod:: histogram

    .. automethod:: timing

    .. automethod:: timed

    .. automethod:: set

    .. automethod:: event

    .. automethod:: flush

.. data:: statsd

    A global :class:`datadog.statsd.DogStatsd` instance that is easily shared
    across an application's modules. Initialize this once in your application's
    set-up code and then other modules can import and use it without further
    configuration.

    >>> from datadog import initialize, statsd
    >>> initialize()

Source
======

The Datadog's Python API source is freely available on Github. Check it out `here
<https://github.com/DataDog/datadog.py>`_.

Get in Touch
============

If you'd like to suggest a feature or report a bug, please add an issue `here <https://github.com/DataDog/datadog.py/issues>`_. If you want to talk about Datadog in general, reach out at `datadoghq.com <http://datadoghq.com>`_.




