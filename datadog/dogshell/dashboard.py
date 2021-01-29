# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import json
import sys

# 3p
import argparse

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings
from datadog.util.format import pretty_json


class DashboardClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("dashboard", help="Create, edit, and delete dashboards")

        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser("post", help="Create dashboards")
        # Required arguments:
        post_parser.add_argument("title", help="title for the new dashboard")
        post_parser.add_argument(
            "widgets", help="widget definitions as a JSON string. If unset," " reads from stdin.", nargs="?"
        )
        post_parser.add_argument("layout_type", choices=["ordered", "free"], help="Layout type of the dashboard.")
        # Optional arguments:
        post_parser.add_argument("--description", help="Short description of the dashboard")
        post_parser.add_argument(
            "--read_only",
            help="Whether this dashboard is read-only. " "If True, only the author and admins can make changes to it.",
            action="store_true",
        )
        post_parser.add_argument(
            "--notify_list",
            type=_json_string,
            help="A json list of user handles, e.g. " '\'["user1@domain.com", "user2@domain.com"]\'',
        )
        post_parser.add_argument(
            "--template_variables",
            type=_json_string,
            help="A json list of template variable dicts, e.g. "
            '\'[{"name": "host", "prefix": "host", '
            '"default": "my-host"}]\'',
        )
        post_parser.set_defaults(func=cls._post)

        update_parser = verb_parsers.add_parser("update", help="Update existing dashboards")
        # Required arguments:
        update_parser.add_argument("dashboard_id", help="Dashboard to replace" " with the new definition")
        update_parser.add_argument("title", help="New title for the dashboard")
        update_parser.add_argument(
            "widgets", help="Widget definitions as a JSON string." " If unset, reads from stdin", nargs="?"
        )
        update_parser.add_argument("layout_type", choices=["ordered", "free"], help="Layout type of the dashboard.")
        # Optional arguments:
        update_parser.add_argument("--description", help="Short description of the dashboard")
        update_parser.add_argument(
            "--read_only",
            help="Whether this dashboard is read-only. " "If True, only the author and admins can make changes to it.",
            action="store_true",
        )
        update_parser.add_argument(
            "--notify_list",
            type=_json_string,
            help="A json list of user handles, e.g. " '\'["user1@domain.com", "user2@domain.com"]\'',
        )
        update_parser.add_argument(
            "--template_variables",
            type=_json_string,
            help="A json list of template variable dicts, e.g. "
            '\'[{"name": "host", "prefix": "host", '
            '"default": "my-host"}]\'',
        )
        update_parser.set_defaults(func=cls._update)

        show_parser = verb_parsers.add_parser("show", help="Show a dashboard definition")
        show_parser.add_argument("dashboard_id", help="Dashboard to show")
        show_parser.set_defaults(func=cls._show)

        delete_parser = verb_parsers.add_parser("delete", help="Delete dashboards")
        delete_parser.add_argument("dashboard_id", help="Dashboard to delete")
        delete_parser.set_defaults(func=cls._delete)

    @classmethod
    def _post(cls, args):
        api._timeout = args.timeout
        format = args.format
        widgets = args.widgets
        if args.widgets is None:
            widgets = sys.stdin.read()
        widgets = json.loads(widgets)

        # Required arguments
        payload = {"title": args.title, "widgets": widgets, "layout_type": args.layout_type}
        # Optional arguments
        if args.description:
            payload["description"] = args.description
        if args.read_only:
            payload["is_read_only"] = args.read_only
        if args.notify_list:
            payload["notify_list"] = args.notify_list
        if args.template_variables:
            payload["template_variables"] = args.template_variables

        res = api.Dashboard.create(**payload)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _update(cls, args):
        api._timeout = args.timeout
        format = args.format
        widgets = args.widgets
        if args.widgets is None:
            widgets = sys.stdin.read()
        widgets = json.loads(widgets)

        # Required arguments
        payload = {"title": args.title, "widgets": widgets, "layout_type": args.layout_type}
        # Optional arguments
        if args.description:
            payload["description"] = args.description
        if args.read_only:
            payload["is_read_only"] = args.read_only
        if args.notify_list:
            payload["notify_list"] = args.notify_list
        if args.template_variables:
            payload["template_variables"] = args.template_variables

        res = api.Dashboard.update(args.dashboard_id, **payload)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Dashboard.get(args.dashboard_id)
        report_warnings(res)
        report_errors(res)

        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _delete(cls, args):
        api._timeout = args.timeout
        res = api.Dashboard.delete(args.dashboard_id)
        if res is not None:
            report_warnings(res)
            report_errors(res)


def _json_string(str):
    try:
        return json.loads(str)
    except Exception:
        raise argparse.ArgumentTypeError("bad json parameter")
