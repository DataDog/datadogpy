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

from __future__ import print_function
import os
import sys

# datadog
from datadog.util.compat import is_p3k, configparser, IterableUserDict,\
    get_input


def print_err(msg):
    if is_p3k():
        print(msg + '\n', file=sys.stderr)
    else:
        sys.stderr.write(msg + '\n')


def report_errors(res):
    if 'errors' in res:
        errors = res['errors']
        if isinstance(errors, list):
            for error in errors:
                print_err("ERROR: {}".format(error))
        else:
            print_err("ERROR: {}".format(errors))
        sys.exit(1)
    return False


def report_warnings(res):
    if 'warnings' in res:
        warnings = res['warnings']
        if isinstance(warnings, list):
            for warning in warnings:
                print_err("WARNING: {}".format(warning))
        else:
            print_err("WARNING: {}".format(warnings))
        return True
    return False


class DogshellConfig(IterableUserDict):

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
                        response = get_input('%s does not exist. Would you like to'
                                             ' create it? [Y/n] ' % config_file)
                        if response.strip().lower() in ['', 'y', 'yes']:
                            # Read the api and app keys from stdin
                            api_key = get_input("What is your api key? (Get it here: "
                                                "https://app.datadoghq.com/account/settings#api) ")
                            app_key = get_input("What is your application key? (Generate one here: "
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
