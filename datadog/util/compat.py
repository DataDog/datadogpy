# flake8: noqa

""" Imports for compatibility with Py2 and Py3
"""
import sys
import logging
import socket


def is_p3k():
    value = sys.version_info[0] == 3
    return value

get_input = input

if is_p3k():
    import configparser
    import urllib.request as url_lib, urllib.error, urllib.parse
    from io import StringIO

    def iteritems(d):
        return iter(d.items())

    def iternext(iter):
        return next(iter)

else:
    get_input = raw_input
    import ConfigParser as configparser
    import urllib2 as url_lib
    from cStringIO import StringIO

    def iteritems(d):
        return d.iteritems()

    def iternext(iter):
        return iter.next()


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

# prefer simplejson but fall back to stdlib python
try:
    import simplejson as json
except ImportError:
    import json
