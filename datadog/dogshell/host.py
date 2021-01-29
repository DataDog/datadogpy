# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import json

# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


class HostClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("host", help="Mute, unmute hosts")
        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        mute_parser = verb_parsers.add_parser("mute", help="Mute a host")
        mute_parser.add_argument("host_name", help="host to mute")
        mute_parser.add_argument(
            "--end", help="POSIX timestamp, if omitted," " host will be muted until explicitly unmuted", default=None
        )
        mute_parser.add_argument("--message", help="string to associate with the" " muting of this host", default=None)
        mute_parser.add_argument(
            "--override",
            help="true/false, if true and the host is already" " muted, will overwrite existing end on the host",
            action="store_true",
        )
        mute_parser.set_defaults(func=cls._mute)

        unmute_parser = verb_parsers.add_parser("unmute", help="Unmute a host")
        unmute_parser.add_argument("host_name", help="host to mute")
        unmute_parser.set_defaults(func=cls._unmute)

    @classmethod
    def _mute(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Host.mute(args.host_name, end=args.end, message=args.message, override=args.override)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _unmute(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Host.unmute(args.host_name)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))
