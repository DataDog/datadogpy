import os
import string
import sys

# datadog
from datadog.util.compat import configparser, StringIO, is_p3k, pkg

# CONSTANTS
DATADOG_CONF = "datadog.conf"


class CfgNotFound(Exception):
    pass


class PathNotFound(Exception):
    pass


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


def skip_leading_wsp(f):
    "Works on a file, returns a file-like object"
    if is_p3k():
        return StringIO("\n".join(x.strip(" ") for x in f.readlines()))
    else:
        return StringIO("\n".join(map(string.strip, f.readlines())))


def _windows_commondata_path():
    """Return the common appdata path, using ctypes
    From http://stackoverflow.com/questions/626796/\
    how-do-i-find-the-windows-common-application-data-folder-using-python
    """
    import ctypes
    from ctypes import wintypes, windll

    CSIDL_COMMON_APPDATA = 35

    _SHGetFolderPath = windll.shell32.SHGetFolderPathW
    _SHGetFolderPath.argtypes = [wintypes.HWND,
                                 ctypes.c_int,
                                 wintypes.HANDLE,
                                 wintypes.DWORD, wintypes.LPCWSTR]

    path_buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    _SHGetFolderPath(0, CSIDL_COMMON_APPDATA, 0, 0, path_buf)
    return path_buf.value


def _windows_config_path():
    common_data = _windows_commondata_path()
    path = os.path.join(common_data, 'Datadog', DATADOG_CONF)
    if os.path.exists(path):
        return path
    raise PathNotFound(path)


def _unix_config_path():
    path = os.path.join('/etc/dd-agent', DATADOG_CONF)
    if os.path.exists(path):
        return path
    raise PathNotFound(path)


def _mac_config_path():
    path = os.path.join('~/.datadog-agent/agent', DATADOG_CONF)
    path = os.path.expanduser(path)
    if os.path.exists(path):
        return path
    raise PathNotFound(path)


def get_config_path(cfg_path=None, os_name=None):
    # Check if there's an override and if it exists
    if cfg_path is not None and os.path.exists(cfg_path):
        return cfg_path

    if os_name is None:
        os_name = get_os()

    # Check for an OS-specific path, continue on not-found exceptions
    if os_name == 'windows':
        return _windows_config_path()
    elif os_name == 'mac':
        return _mac_config_path()
    else:
        return _unix_config_path()


def get_config(cfg_path=None, options=None):
    agentConfig = {}

    # Config handling
    try:
        # Find the right config file
        path = os.path.realpath(__file__)
        path = os.path.dirname(path)

        config_path = get_config_path(cfg_path, os_name=get_os())
        config = configparser.ConfigParser()
        config.readfp(skip_leading_wsp(open(config_path)))

        # bulk import
        for option in config.options('Main'):
            agentConfig[option] = config.get('Main', option)

    except Exception:
        raise CfgNotFound

    return agentConfig


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
