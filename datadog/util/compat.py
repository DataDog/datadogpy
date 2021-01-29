# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# flake8: noqa
"""
Imports for compatibility with Python 2, Python 3 and Google App Engine.
"""
from functools import wraps
import logging
import socket
import sys

# Note: using `sys.version_info` instead of the helper functions defined here
# so that mypy detects version-specific code paths. Currently, mypy doesn't
# support try/except imports for version-specific code paths either.
#
# https://mypy.readthedocs.io/en/stable/common_issues.html#python-version-and-system-platform-checks

# Python 3.x
if sys.version_info[0] >= 3:
    import builtins
    from collections import UserDict as IterableUserDict
    import configparser
    from configparser import ConfigParser
    from io import StringIO
    from urllib.parse import urljoin, urlparse
    import urllib.request as url_lib, urllib.error, urllib.parse

    imap = map
    get_input = input
    text = str

    def iteritems(d):
        return iter(d.items())

    def iternext(iter):
        return next(iter)


# Python 2.x
else:
    import __builtin__ as builtins
    import ConfigParser as configparser
    from configparser import ConfigParser
    from cStringIO import StringIO
    from itertools import imap
    import urllib2 as url_lib
    from urlparse import urljoin, urlparse
    from UserDict import IterableUserDict

    get_input = raw_input
    text = unicode

    def iteritems(d):
        return d.iteritems()

    def iternext(iter):
        return iter.next()


# Python >= 3.5
if sys.version_info >= (3, 5):
    from asyncio import iscoroutinefunction
# Others
else:

    def iscoroutinefunction(*args, **kwargs):
        return False


# Python >= 2.7
if sys.version_info >= (2, 7):
    from logging import NullHandler
# Python 2.6.x
else:
    from logging import Handler

    class NullHandler(Handler):
        def emit(self, record):
            pass


def _is_py_version_higher_than(major, minor=0):
    """
    Assert that the Python version is higher than `$maj.$min`.
    """
    return sys.version_info >= (major, minor)


def is_p3k():
    """
    Assert that Python is version 3 or higher.
    """
    return _is_py_version_higher_than(3)


def is_higher_py35():
    """
    Assert that Python is version 3.5 or higher.
    """
    return _is_py_version_higher_than(3, 5)


def is_pypy():
    """
    Assert that PyPy is being used (regardless of 2 or 3)
    """
    return "__pypy__" in sys.builtin_module_names
