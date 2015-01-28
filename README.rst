###############################################
:mod:`datadog` --- The Datadog's Python library
###############################################

.. module:: datadog

The :mod:`datadog` module provides :mod:`datadog.api` - a simple wrapper around Datadog's HTTP API - and :mod:`datadog.stats` - a tool for collecting metrics in high performance applications.

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


.. automodule:: datadog.stats.dog_stats_api

.. autoclass::  datadog.stats.dog_stats_api.DogStatsApi

    .. automethod:: configure

    .. automethod:: event

    .. automethod:: gauge

    .. automethod:: increment

    .. automethod:: decrement

    .. automethod:: set

    .. automethod:: histogram

    .. automethod:: timed

    .. automethod:: flush


.. module:: datadog
.. data:: stats

    A global :class:`~datadog.stats.DogStatsApi` instance that is easily shared
    across an application's modules. Initialize this once in your application's
    set-up code and then other modules can import and use it without further
    configuration.

    >>> from datadog import initialize, stats
    >>> initialize(api_key='my_api_key')
    >>> stats.increment('home.page.hits')


Here's an example that put's it all together. ::

    # Import the dog stats instance.
    from datadog import initialize, stats

    # Begin flushing asynchronously with the given api key. After this is done
    # once in your application, other modules can import and use stats
    # without any further configuration.
    initialize(api_key='my_api_key', statsd=False)


    @stats.timed('home_page.render.time')
    def render_home_page(user_id):
        """ Render the home page for the given user. """

        # Fetch the user from the cache or the database
        # and record metrics on our cache hits and misses.
        user = user_cache.get(user_id)
        if user:
            stats.increment('user_cache.hit')
        else:
            stats.increment('user_cache.miss')
            user = user_database.get(user_id)

        return render('home.html', user_id)


Source
======

The Datadog's Python library source is freely available on Github. Check it out `here
<https://github.com/DataDog/datadogpy>`_.

Get in Touch
============

If you'd like to suggest a feature or report a bug, please add an issue `here <https://github.com/DataDog/datadogpy/issues>`_. If you want to talk about Datadog in general, reach out at `datadoghq.com <http://datadoghq.com>`_.




