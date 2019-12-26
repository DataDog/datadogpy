# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# flake8: noqa
"""
Imports for compatibility with Python 2, Python 3 and Google App Engine.
"""
from functools import wraps
import logging
import socket
import sys

try:
    from urllib.parse import urljoin
except ImportError:
    from urlparse import urljoin


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
    return '__pypy__' in sys.builtin_module_names


get_input = input

# Python 3.x
if is_p3k():
    from io import StringIO
    import builtins
    import configparser
    import urllib.request as url_lib, urllib.error, urllib.parse

    imap = map
    text = str

    def iteritems(d):
        return iter(d.items())

    def iternext(iter):
        return next(iter)


# Python 2.x
else:
    import __builtin__ as builtins
    from cStringIO import StringIO
    from itertools import imap
    import ConfigParser as configparser
    import urllib2 as url_lib

    get_input = raw_input
    text = unicode

    def iteritems(d):
        return d.iteritems()

    def iternext(iter):
        return iter.next()


# Python > 3.5
if is_higher_py35():
    from asyncio import iscoroutinefunction

# Others
else:
    def iscoroutinefunction(*args, **kwargs):
        return False

# Optional requirements
try:
    from UserDict import IterableUserDict
except ImportError:
    from collections import UserDict as IterableUserDict

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

try:
    import pkg_resources as pkg
except ImportError:
    pkg = None

#Python 2.6.x
try:
    from logging import NullHandler
except ImportError:
    from logging import Handler

    class NullHandler(Handler):
        def emit(self, record):
            pass
