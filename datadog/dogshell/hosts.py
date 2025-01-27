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


class HostsClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("hosts", help="Get information about hosts")
        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        list_parser = verb_parsers.add_parser("list", help="List all hosts")
        list_parser.add_argument("--filter", help="String to filter search results", type=str)
        list_parser.add_argument("--sort_field", help="Sort hosts by this field", type=str)
        list_parser.add_argument(
            "--sort_dir",
            help="Direction of sort. 'asc' or 'desc'",
            choices=["asc", "desc"],
            default="asc"
        )
        list_parser.add_argument(
            "--start",
            help="Specify the starting point for the host search results. \
                                    For example, if you set count to 100 and the first 100 results  \
                                    have already been returned, \
                                    you can set start to 101 to get the next 100 results.",
            type=int,
        )
        list_parser.add_argument("--count", help="Number of hosts to return. Max 1000", type=int, default=100)
        list_parser.add_argument(
            "--from",
            help="Number of seconds since UNIX epoch from which you want to search your hosts.",
            type=int,
            dest="from_",
        )
        # list_parser.add_argument(
        #     "--include_muted_hosts_data",
        #     help="Include information on the muted status of hosts and when the mute expires.",
        #     action="store_true",
        # )
        list_parser.add_argument(
            "--include_hosts_metadata",
            help="Include metadata from the hosts \
                                    (agent_version, machine, platform, processor, etc.).",
            action="store_true",
        )
        list_parser.set_defaults(func=cls._list)

        totals_parser = verb_parsers.add_parser("totals", help="Get the total number of hosts")
        totals_parser.add_argument("--from",
                                   help="Number of seconds since UNIX epoch \
                                    from which you want to search your hosts.",
                                   type=int,
                                   dest="from_")
        totals_parser.set_defaults(func=cls._totals)

    @classmethod
    def _list(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Hosts.get_all(
            filter=args.filter,
            sort_field=args.sort_field,
            sort_dir=args.sort_dir,
            start=args.start,
            count=args.count,
            from_=args.from_,
            include_hosts_metadata=args.include_hosts_metadata,
            # this doesn't seem to actually filter and I don't need it for now.
            # include_muted_hosts_data=args.include_muted_hosts_data
        )
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _totals(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Hosts.totals(from_=args.from_)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))
