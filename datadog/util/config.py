import os
import sys

# datadog
from datadog.util.compat import pkg


def get_os():
    "Human-friendly OS name"
    if sys.platform == 'darwin':
        return 'mac'
    elif sys.platform.find('freebsd') != -1:
        return 'freebsd'
    elif sys.platform.find('linux') != -1:
        return 'linux'
    elif sys.platform.find('win32') != -1:
        return 'windows'
    elif sys.platform.find('sunos') != -1:
        return 'solaris'
    else:
        return sys.platform


def get_version():
    """
    Resolve `datadog` package version.
    """
    version = u"unknown"

    if not pkg:
        return version

    try:
        dist = pkg.get_distribution("datadog")
        # Normalize case for Windows systems
        dist_loc = os.path.normcase(dist.location)
        here = os.path.normcase(__file__)
        if not here.startswith(dist_loc):
            # not installed, but there is another version that *is*
            raise pkg.DistributionNotFound
        version = dist.version
    except pkg.DistributionNotFound:
        version = u"Please install `datadog` with setup.py"

    return version
