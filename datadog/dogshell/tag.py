# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


class TagClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("tag", help="View and modify host tags.")
        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        add_parser = verb_parsers.add_parser(
            "add", help="Add a host to one or more tags.", description="Hosts can be specified by name or id."
        )
        add_parser.add_argument("host", help="host to add")
        add_parser.add_argument("tag", help="tag to add host to (one or more, space separated)", nargs="+")
        add_parser.set_defaults(func=cls._add)

        replace_parser = verb_parsers.add_parser(
            "replace",
            help="Replace all tags with one or more new tags.",
            description="Hosts can be specified by name or id.",
        )
        replace_parser.add_argument("host", help="host to modify")
        replace_parser.add_argument("tag", help="list of tags to add host to", nargs="+")
        replace_parser.set_defaults(func=cls._replace)

        show_parser = verb_parsers.add_parser(
            "show", help="Show host tags.", description="Hosts can be specified by name or id."
        )
        show_parser.add_argument("host", help="host to show (or 'all' to show all tags)")
        show_parser.set_defaults(func=cls._show)

        detach_parser = verb_parsers.add_parser(
            "detach", help="Remove a host from all tags.", description="Hosts can be specified by name or id."
        )
        detach_parser.add_argument("host", help="host to detach")
        detach_parser.set_defaults(func=cls._detach)

    @classmethod
    def _add(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Tag.create(args.host, tags=args.tag)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print("Tags for '%s':" % res["host"])
            for c in res["tags"]:
                print("  " + c)
        elif format == "raw":
            print(json.dumps(res))
        else:
            for c in res["tags"]:
                print(c)

    @classmethod
    def _replace(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Tag.update(args.host, tags=args.tag)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print("Tags for '%s':" % res["host"])
            for c in res["tags"]:
                print("  " + c)
        elif format == "raw":
            print(json.dumps(res))
        else:
            for c in res["tags"]:
                print(c)

    @classmethod
    def _show(cls, args):
        api._timeout = args.timeout
        format = args.format
        if args.host == "all":
            res = api.Tag.get_all()
        else:
            res = api.Tag.get(args.host)
        report_warnings(res)
        report_errors(res)
        if args.host == "all":
            if format == "pretty":
                for tag, hosts in list(res["tags"].items()):
                    for host in hosts:
                        print(tag)
                        print("  " + host)
                    print()
            elif format == "raw":
                print(json.dumps(res))
            else:
                for tag, hosts in list(res["tags"].items()):
                    for host in hosts:
                        print(tag + "\t" + host)
        else:
            if format == "pretty":
                for tag in res["tags"]:
                    print(tag)
            elif format == "raw":
                print(json.dumps(res))
            else:
                for tag in res["tags"]:
                    print(tag)

    @classmethod
    def _detach(cls, args):
        api._timeout = args.timeout
        res = api.Tag.delete(args.host)
        if res is not None:
            report_warnings(res)
            report_errors(res)
