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


class DowntimeClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("downtime", help="Create, edit, and delete downtimes")
        parser.add_argument(
            "--string_ids",
            action="store_true",
            dest="string_ids",
            help="Represent downtime IDs as strings instead of ints in JSON",
        )

        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser("post", help="Create a downtime")
        post_parser.add_argument("scope", help="scope to apply downtime to")
        post_parser.add_argument("start", help="POSIX timestamp to start the downtime", default=None)
        post_parser.add_argument("--end", help="POSIX timestamp to end the downtime", default=None)
        post_parser.add_argument(
            "--message", help="message to include with notifications" " for this downtime", default=None
        )
        post_parser.set_defaults(func=cls._schedule_downtime)

        update_parser = verb_parsers.add_parser("update", help="Update existing downtime")
        update_parser.add_argument("downtime_id", help="downtime to replace" " with the new definition")
        update_parser.add_argument("--scope", help="scope to apply downtime to")
        update_parser.add_argument("--start", help="POSIX timestamp to start" " the downtime", default=None)
        update_parser.add_argument("--end", help="POSIX timestamp to" " end the downtime", default=None)
        update_parser.add_argument(
            "--message", help="message to include with notifications" " for this downtime", default=None
        )
        update_parser.set_defaults(func=cls._update_downtime)

        show_parser = verb_parsers.add_parser("show", help="Show a downtime definition")
        show_parser.add_argument("downtime_id", help="downtime to show")
        show_parser.set_defaults(func=cls._show_downtime)

        show_all_parser = verb_parsers.add_parser("show_all", help="Show a list of all downtimes")
        show_all_parser.add_argument(
            "--current_only", help="only return downtimes that" " are active when the request is made", default=None
        )
        show_all_parser.set_defaults(func=cls._show_all_downtime)

        delete_parser = verb_parsers.add_parser("delete", help="Delete a downtime")
        delete_parser.add_argument("downtime_id", help="downtime to delete")
        delete_parser.set_defaults(func=cls._cancel_downtime)

        cancel_parser = verb_parsers.add_parser("cancel_by_scope", help="Cancel all downtimes with a given scope")
        cancel_parser.add_argument("scope", help="The scope of the downtimes to cancel")
        cancel_parser.set_defaults(func=cls._cancel_downtime_by_scope)

    @classmethod
    def _schedule_downtime(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Downtime.create(scope=args.scope, start=args.start, end=args.end, message=args.message)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _update_downtime(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Downtime.update(
            args.downtime_id, scope=args.scope, start=args.start, end=args.end, message=args.message
        )
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _cancel_downtime(cls, args):
        api._timeout = args.timeout
        res = api.Downtime.delete(args.downtime_id)
        if res is not None:
            report_warnings(res)
            report_errors(res)

    @classmethod
    def _show_downtime(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Downtime.get(args.downtime_id)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show_all_downtime(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Downtime.get_all(current_only=args.current_only)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _cancel_downtime_by_scope(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Downtime.cancel_downtime_by_scope(scope=args.scope)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))
