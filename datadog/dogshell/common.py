# stdlib
import os
import sys
import configparser
from collections import UserDict


def print_err(msg):
    print(f'{msg}\n', file=sys.stderr)


def report_errors(res):
    if 'errors' in res:
        errors = res['errors']
        if isinstance(errors, list):
            for error in errors:
                print_err(f"ERROR: {error}")
        else:
            print_err(f"ERROR: {errors}")
        sys.exit(1)
    return False


def report_warnings(res):
    if 'warnings' in res:
        warnings = res['warnings']
        if isinstance(warnings, list):
            for warning in warnings:
                print_err(f"WARNING: {warning}")
        else:
            print_err(f"WARNING: {warnings}")
        return True
    return False


class DogshellConfig(UserDict):

    def load(self, config_file, api_key, app_key):
        config = configparser.ConfigParser()

        if api_key is not None and app_key is not None:
            self['api_key'] = api_key
            self['app_key'] = app_key
        else:
            if os.access(config_file, os.F_OK):
                config.read(config_file)
                if not config.has_section('Connection'):
                    report_errors({'errors': ['%s has no [Connection] section' % config_file]})
            else:
                try:
                    response = ''
                    while response.strip().lower() not in ['y', 'n']:
                        response = input(f'{config_file} does not exist. Would you like to create it? [Y/n] ')
                        if response.strip().lower() in ['', 'y', 'yes']:
                            # Read the api and app keys from stdin
                            api_key = input("What is your api key? (Get it here: "
                                            "https://app.datadoghq.com/account/settings#api) ")
                            app_key = input("What is your application key? (Generate one here: "
                                            "https://app.datadoghq.com/account/settings#api) ")

                            # Write the config file
                            config.add_section('Connection')
                            config.set('Connection', 'apikey', api_key)
                            config.set('Connection', 'appkey', app_key)

                            f = open(config_file, 'w')
                            config.write(f)
                            f.close()
                            print('Wrote %s' % config_file)
                        elif response.strip().lower() == 'n':
                            # Abort
                            print_err('Exiting\n')
                            sys.exit(1)
                except KeyboardInterrupt:
                    # Abort
                    print_err('\nExiting')
                    sys.exit(1)

            self['api_key'] = config.get('Connection', 'apikey')
            self['app_key'] = config.get('Connection', 'appkey')
            if config.has_section('Proxy'):
                self['proxies'] = dict(config.items('Proxy'))
            if config.has_option('Connection', 'host_name'):
                self['host_name'] = config.get('Connection', 'host_name')
            if config.has_option('Connection', 'api_host'):
                self['api_host'] = config.get('Connection', 'api_host')
        assert self['api_key'] is not None and self['app_key'] is not None
