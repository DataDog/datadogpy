import os
import logging
import string
import sys

from datadog.util.compat import configparser, StringIO, is_p3k

# CONSTANTS
DATADOG_CONF = "datadog.conf"

log = logging.getLogger('dd.datadogpy')


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

    path_buf = wintypes.create_unicode_buffer(wintypes.MAX_PATH)
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
    try:
        if os_name == 'windows':
            return _windows_config_path()
        elif os_name == 'mac':
            return _mac_config_path()
        else:
            return _unix_config_path()
    except PathNotFound:
        pass

    # If all searches fail, exit the agent with an error
    raise CfgNotFound


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

    except configparser.NoSectionError as e:
        sys.stderr.write('Config file not found or incorrectly formatted.\n')
        sys.exit(2)

    except configparser.ParsingError as e:
        sys.stderr.write('Config file not found or incorrectly formatted.\n')
        sys.exit(2)

    except configparser.NoOptionError as e:
        sys.stderr.write('There are some items missing from your config file'
                         ', but nothing fatal [%s]' % e)

    return agentConfig
