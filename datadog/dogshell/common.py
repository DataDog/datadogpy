# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
from __future__ import print_function
import os
import sys

# datadog
from datadog.util.compat import is_p3k, configparser, IterableUserDict, get_input


def print_err(msg):
    if is_p3k():
        print(msg + "\n", file=sys.stderr)
    else:
        sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def report_errors(res):
    if "errors" in res:
        errors = res["errors"]
        if isinstance(errors, list):
            for error in errors:
                print_err("ERROR: {}".format(error))
        else:
            print_err("ERROR: {}".format(errors))
        sys.exit(1)
    return False


def report_warnings(res):
    if "warnings" in res:
        warnings = res["warnings"]
        if isinstance(warnings, list):
            for warning in warnings:
                print_err("WARNING: {}".format(warning))
        else:
            print_err("WARNING: {}".format(warnings))
        return True
    return False


class DogshellConfig(IterableUserDict):
    def load(self, config_file, api_key, app_key, api_host):
        config = configparser.ConfigParser()

        if api_host is not None:
            if api_host in ("datadoghq.com", "us"):
                self["api_host"] = "https://api.datadoghq.com"
            elif api_host in ("datadoghq.eu", "eu"):
                self["api_host"] = "https://api.datadoghq.eu"
            elif api_host in ("us3.datadoghq.com", "us3"):
                self["api_host"] = "https://api.us3.datadoghq.com"
            elif api_host in ("us5.datadoghq.com", "us5"):
                self["api_host"] = "https://api.us5.datadoghq.com"
            elif api_host in ("ap1.datadoghq.com", "ap1"):
                self["api_host"] = "https://api.ap1.datadoghq.com"
            elif api_host in ("ddog-gov.com", "gov"):
                self["api_host"] = "https://api.ddog-gov.com"
            else:
                self["api_host"] = api_host
        if api_key is not None and app_key is not None:
            self["api_key"] = api_key
            self["app_key"] = app_key
        else:
            if os.access(config_file, os.F_OK):
                config.read(config_file)
                if not config.has_section("Connection"):
                    report_errors({"errors": ["%s has no [Connection] section" % config_file]})
            else:
                try:
                    response = None
                    while response is None or response.strip().lower() not in ["", "y", "n"]:
                        response = get_input("%s does not exist. Would you like to" " create it? [Y/n] " % config_file)
                        if response.strip().lower() in ["", "y"]:
                            # Read the api and app keys from stdin
                            while True:
                                api_key = get_input(
                                    "What is your api key? (Get it here: "
                                    "https://app.datadoghq.com/account/settings#api) "
                                )
                                if api_key.isalnum():
                                    break
                                print("Datadog api keys can only contain alphanumeric characters.")
                            while True:
                                app_key = get_input(
                                    "What is your app key? (Get it here: "
                                    "https://app.datadoghq.com/account/settings#api) "
                                )
                                if app_key.isalnum():
                                    break
                                print("Datadog app keys can only contain alphanumeric characters.")

                            # Write the config file
                            config.add_section("Connection")
                            config.set("Connection", "apikey", api_key)
                            config.set("Connection", "appkey", app_key)

                            f = open(config_file, "w")
                            config.write(f)
                            f.close()
                            print("Wrote %s" % config_file)
                        elif response.strip().lower() == "n":
                            # Abort
                            print_err("Exiting\n")
                            sys.exit(1)
                except (KeyboardInterrupt, EOFError):
                    # Abort
                    print_err("\nExiting")
                    sys.exit(1)

            self["api_key"] = config.get("Connection", "apikey")
            self["app_key"] = config.get("Connection", "appkey")
            if config.has_section("Proxy"):
                self["proxies"] = dict(config.items("Proxy"))
            if config.has_option("Connection", "host_name"):
                self["host_name"] = config.get("Connection", "host_name")
            if config.has_option("Connection", "api_host"):
                self["api_host"] = config.get("Connection", "api_host")
        assert self["api_key"] is not None and self["app_key"] is not None
