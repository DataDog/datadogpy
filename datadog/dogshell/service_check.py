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


class ServiceCheckClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("service_check", help="Perform service checks")
        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        check_parser = verb_parsers.add_parser("check", help="text for the message")
        check_parser.add_argument("check", help="text for the message")
        check_parser.add_argument("host_name", help="name of the host submitting the check")
        check_parser.add_argument(
            "status",
            help="integer for the status of the check." " i.e: '0': OK, '1': WARNING, '2': CRITICAL, '3': UNKNOWN",
        )
        check_parser.add_argument("--timestamp", help="POSIX timestamp of the event", default=None)
        check_parser.add_argument("--message", help="description of why this status occurred", default=None)
        check_parser.add_argument("--tags", help="comma separated list of tags", default=None)
        check_parser.set_defaults(func=cls._check)

    @classmethod
    def _check(cls, args):
        api._timeout = args.timeout
        format = args.format
        if args.tags:
            tags = sorted(set([t.strip() for t in args.tags.split(",") if t.strip()]))
        else:
            tags = None
        res = api.ServiceCheck.check(
            check=args.check,
            host_name=args.host_name,
            status=int(args.status),
            timestamp=args.timestamp,
            message=args.message,
            tags=tags,
        )
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))
