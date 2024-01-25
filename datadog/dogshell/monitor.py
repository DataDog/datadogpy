# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import argparse
import json

# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings, print_err


class MonitorClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("monitor", help="Create, edit, and delete monitors")
        parser.add_argument(
            "--string_ids",
            action="store_true",
            dest="string_ids",
            help="Represent monitor IDs as strings instead of ints in JSON",
        )

        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser("post", help="Create a monitor")
        post_parser.add_argument("type", help="type of the monitor, e.g." "'metric alert' 'service check'")
        post_parser.add_argument(
            "query", help="query to notify on with syntax varying " "depending on what type of monitor you are creating"
        )
        post_parser.add_argument("--name", help="name of the alert", default=None)
        post_parser.add_argument(
            "--message", help="message to include with notifications" " for this monitor", default=None
        )
        post_parser.add_argument(
            "--restricted_roles", help="comma-separated list of unique role identifiers allowed to edit the monitor",
            default=None
        )
        post_parser.add_argument("--tags", help="comma-separated list of tags", default=None)
        post_parser.add_argument(
            "--priority",
            help="Integer from 1 (high) to 5 (low) indicating alert severity.",
            default=None
        )
        post_parser.add_argument("--options", help="json options for the monitor", default=None)
        post_parser.set_defaults(func=cls._post)

        file_post_parser = verb_parsers.add_parser("fpost", help="Create a monitor from file")
        file_post_parser.add_argument("file", help="json file holding all details", type=argparse.FileType("r"))
        file_post_parser.set_defaults(func=cls._file_post)

        update_parser = verb_parsers.add_parser("update", help="Update existing monitor")
        update_parser.add_argument("monitor_id", help="monitor to replace with the new definition")
        update_parser.add_argument(
            "type",
            nargs="?",
            help="[Deprecated] optional argument preferred" "type of the monitor, e.g. 'metric alert' 'service check'",
            default=None,
        )
        update_parser.add_argument(
            "query",
            nargs="?",
            help="[Deprecated] optional argument preferred"
            "query to notify on with syntax varying depending on monitor type",
            default=None,
        )
        update_parser.add_argument(
            "--type", help="type of the monitor, e.g. " "'metric alert' 'service check'", default=None, dest="type_opt"
        )
        update_parser.add_argument(
            "--query",
            help="query to notify on with syntax varying" " depending on monitor type",
            default=None,
            dest="query_opt",
        )
        update_parser.add_argument("--name", help="name of the alert", default=None)
        update_parser.add_argument(
            "--restricted_roles", help="comma-separated list of unique role identifiers allowed to edit the monitor",
            default=None
        )
        update_parser.add_argument("--tags", help="comma-separated list of tags", default=None)
        update_parser.add_argument(
            "--message", help="message to include with " "notifications for this monitor", default=None
        )
        update_parser.add_argument(
            "--priority",
            help="Integer from 1 (high) to 5 (low) indicating alert severity.",
            default=None
        )
        update_parser.add_argument("--options", help="json options for the monitor", default=None)
        update_parser.set_defaults(func=cls._update)

        file_update_parser = verb_parsers.add_parser("fupdate", help="Update existing" " monitor from file")
        file_update_parser.add_argument("file", help="json file holding all details", type=argparse.FileType("r"))
        file_update_parser.set_defaults(func=cls._file_update)

        show_parser = verb_parsers.add_parser("show", help="Show a monitor definition")
        show_parser.add_argument("monitor_id", help="monitor to show")
        show_parser.set_defaults(func=cls._show)

        show_all_parser = verb_parsers.add_parser("show_all", help="Show a list of all monitors")
        show_all_parser.add_argument(
            "--group_states",
            help="comma separated list of group states to filter by"
            "(choose one or more from 'all', 'alert', 'warn', or 'no data')",
        )
        show_all_parser.add_argument("--name", help="string to filter monitors by name")
        show_all_parser.add_argument(
            "--tags",
            help="comma separated list indicating what tags, if any, "
            "should be used to filter the list of monitors by scope (e.g. 'host:host0')",
        )
        show_all_parser.add_argument(
            "--monitor_tags",
            help="comma separated list indicating what service "
            "and/or custom tags, if any, should be used to filter the list of monitors",
        )

        show_all_parser.set_defaults(func=cls._show_all)

        delete_parser = verb_parsers.add_parser("delete", help="Delete a monitor")
        delete_parser.add_argument("monitor_id", help="monitor to delete")
        delete_parser.set_defaults(func=cls._delete)

        mute_all_parser = verb_parsers.add_parser("mute_all", help="Globally mute " "monitors (downtime over *)")
        mute_all_parser.set_defaults(func=cls._mute_all)

        unmute_all_parser = verb_parsers.add_parser(
            "unmute_all", help="Globally unmute " "monitors (cancel downtime over *)"
        )
        unmute_all_parser.set_defaults(func=cls._unmute_all)

        mute_parser = verb_parsers.add_parser("mute", help="Mute a monitor")
        mute_parser.add_argument("monitor_id", help="monitor to mute")
        mute_parser.add_argument("--scope", help="scope to apply the mute to," " e.g. role:db (optional)", default=[])
        mute_parser.add_argument(
            "--end", help="POSIX timestamp for when" " the mute should end (optional)", default=None
        )
        mute_parser.set_defaults(func=cls._mute)

        unmute_parser = verb_parsers.add_parser("unmute", help="Unmute a monitor")
        unmute_parser.add_argument("monitor_id", help="monitor to unmute")
        unmute_parser.add_argument("--scope", help="scope to unmute (must be muted), " "e.g. role:db", default=[])
        unmute_parser.add_argument("--all_scopes", help="clear muting across all scopes", action="store_true")
        unmute_parser.set_defaults(func=cls._unmute)

        can_delete_parser = verb_parsers.add_parser("can_delete", help="Check if you can delete some monitors")
        can_delete_parser.add_argument("monitor_ids", help="monitors to check if they can be deleted")
        can_delete_parser.set_defaults(func=cls._can_delete)

        validate_parser = verb_parsers.add_parser("validate", help="Validates if a monitor definition is correct")
        validate_parser.add_argument("type", help="type of the monitor, e.g." "'metric alert' 'service check'")
        validate_parser.add_argument("query", help="the monitor query")
        validate_parser.add_argument("--name", help="name of the alert", default=None)
        validate_parser.add_argument(
            "--message", help="message to include with notifications" " for this monitor", default=None
        )
        validate_parser.add_argument(
            "--restricted_roles", help="comma-separated list of unique role identifiers allowed to edit the monitor",
            default=None
        )
        validate_parser.add_argument("--tags", help="comma-separated list of tags", default=None)
        validate_parser.add_argument("--options", help="json options for the monitor", default=None)
        validate_parser.set_defaults(func=cls._validate)

    @classmethod
    def _post(cls, args):
        api._timeout = args.timeout
        format = args.format
        options = None
        if args.options is not None:
            options = json.loads(args.options)

        if args.tags:
            tags = sorted(set([t.strip() for t in args.tags.split(",") if t.strip()]))
        else:
            tags = None

        if args.restricted_roles:
            restricted_roles = sorted(set([rr.strip() for rr in args.restricted_roles.split(",") if rr.strip()]))
        else:
            restricted_roles = None

        body = {
            "type": args.type,
            "query": args.query,
            "name": args.name,
            "message": args.message,
            "options": options
        }
        if tags:
            body["tags"] = tags
        if restricted_roles:
            body["restricted_roles"] = restricted_roles
        if args.priority:
            body["priority"] = args.priority

        res = api.Monitor.create(**body)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _file_post(cls, args):
        api._timeout = args.timeout
        format = args.format
        monitor = json.load(args.file)
        body = {
            "type": monitor["type"],
            "query": monitor["query"],
            "name": monitor["name"],
            "message": monitor["message"],
            "options": monitor["options"]
        }
        restricted_roles = monitor.get("restricted_roles", None)
        if restricted_roles:
            body["restricted_roles"] = restricted_roles
        tags = monitor.get("tags", None)
        if tags:
            body["tags"] = tags
        priority = monitor.get("priority", None)
        if priority:
            body["priority"] = priority

        res = api.Monitor.create(**body)
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

        to_update = {}
        if args.type:
            if args.type_opt:
                msg = "Duplicate arguments for `type`. Using optional value --type"
                print_err("WARNING: {}".format(msg))
            else:
                to_update["type"] = args.type
            msg = "[DEPRECATION] `type` is no longer required to `update` and may be omitted"
            print_err("WARNING: {}".format(msg))
        if args.query:
            if args.query_opt:
                msg = "Duplicate arguments for `query`. Using optional value --query"
                print_err("WARNING: {}".format(msg))
            else:
                to_update["query"] = args.query
            msg = "[DEPRECATION] `query` is no longer required to `update` and may be omitted"
            print_err("WARNING: {}".format(msg))
        if args.name:
            to_update["name"] = args.name
        if args.message:
            to_update["message"] = args.message
        if args.type_opt:
            to_update["type"] = args.type_opt
        if args.query_opt:
            to_update["query"] = args.query_opt
        if args.restricted_roles is not None:
            if args.restricted_roles == "":
                to_update["restricted_roles"] = None
            else:
                to_update["restricted_roles"] = sorted(
                    set([rr.strip() for rr in args.restricted_roles.split(",") if rr.strip()]))
        if args.tags:
            to_update["tags"] = sorted(set([t.strip() for t in args.tags.split(",") if t.strip()]))
        if args.priority:
            to_update["priority"] = args.priority

        if args.options is not None:
            to_update["options"] = json.loads(args.options)

        res = api.Monitor.update(args.monitor_id, **to_update)

        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _file_update(cls, args):
        api._timeout = args.timeout
        format = args.format
        monitor = json.load(args.file)
        body = {
            "type": monitor["type"],
            "query": monitor["query"],
            "name": monitor["name"],
            "message": monitor["message"],
            "options": monitor["options"]
        }
        # Default value is False to defferentiate between explicit None and not set
        restricted_roles = monitor.get("restricted_roles", False)
        if restricted_roles is not False:
            body["restricted_roles"] = restricted_roles
        tags = monitor.get("tags", None)
        if tags:
            body["tags"] = tags
        priority = monitor.get("priority", None)
        if priority:
            body["priority"] = priority

        res = api.Monitor.update(monitor["id"], **body)

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
        res = api.Monitor.get(args.monitor_id)
        report_warnings(res)
        report_errors(res)

        if args.string_ids:
            res["id"] = str(res["id"])

        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show_all(cls, args):
        api._timeout = args.timeout
        format = args.format

        res = api.Monitor.get_all(
            group_states=args.group_states, name=args.name, tags=args.tags, monitor_tags=args.monitor_tags
        )
        report_warnings(res)
        report_errors(res)

        if args.string_ids:
            for d in res:
                d["id"] = str(d["id"])

        if format == "pretty":
            print(pretty_json(res))
        elif format == "raw":
            print(json.dumps(res))
        else:
            for d in res:
                print(
                    "\t".join(
                        [
                            (str(d["id"])),
                            (cls._escape(d["message"])),
                            (cls._escape(d["name"])),
                            (str(d["options"])),
                            (str(d["org_id"])),
                            (d["query"]),
                            (d["type"]),
                        ]
                    )
                )

    @classmethod
    def _delete(cls, args):
        api._timeout = args.timeout
        # TODO CHECK
        res = api.Monitor.delete(args.monitor_id)
        if res is not None:
            report_warnings(res)
            report_errors(res)

    @classmethod
    def _escape(cls, s):
        return s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")

    @classmethod
    def _mute_all(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Monitor.mute_all()
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _unmute_all(cls, args):
        api._timeout = args.timeout
        res = api.Monitor.unmute_all()
        if res is not None:
            report_warnings(res)
            report_errors(res)

    @classmethod
    def _mute(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Monitor.mute(args.monitor_id, scope=args.scope, end=args.end)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _unmute(cls, args):
        api._timeout = args.timeout
        res = api.Monitor.unmute(args.monitor_id, scope=args.scope, all_scopes=args.all_scopes)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _can_delete(cls, args):
        api._timeout = args.timeout
        monitor_ids = [i.strip() for i in args.monitor_ids.split(",") if i.strip()]
        res = api.Monitor.can_delete(monitor_ids=monitor_ids)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _validate(cls, args):
        api._timeout = args.timeout
        format = args.format
        options = None
        if args.options is not None:
            options = json.loads(args.options)

        if args.tags:
            tags = sorted(set([t.strip() for t in args.tags.split(",") if t.strip()]))
        else:
            tags = None

        if args.restricted_roles:
            restricted_roles = sorted(set([rr.strip() for rr in args.restricted_roles.split(",") if rr.strip()]))
        else:
            restricted_roles = None

        res = api.Monitor.validate(
            type=args.type,
            query=args.query,
            name=args.name,
            message=args.message,
            tags=tags,
            restricted_roles=restricted_roles,
            options=options
        )
        # report_warnings(res)
        # report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))
