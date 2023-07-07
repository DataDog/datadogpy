# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import argparse
import json

# 3p
from datadog.util.cli import (
    set_of_ints,
    comma_set,
    comma_list_or_empty,
    parse_date_as_epoch_timestamp,
)
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


class ServiceLevelObjectiveClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser(
            "service_level_objective",
            help="Create, edit, and delete service level objectives",
        )

        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        create_parser = verb_parsers.add_parser("create", help="Create a SLO")
        create_parser.add_argument(
            "--type",
            help="type of the SLO, e.g.",
            choices=["metric", "monitor"],
        )
        create_parser.add_argument("--name", help="name of the SLO", default=None)
        create_parser.add_argument("--description", help="description of the SLO", default=None)
        create_parser.add_argument(
            "--tags",
            help="comma-separated list of tags",
            default=None,
            type=comma_list_or_empty,
        )
        create_parser.add_argument(
            "--thresholds",
            help="comma separated list of <timeframe>:<target>[:<warning>[:<target_display>[:<warning_display>]]",
        )
        create_parser.add_argument(
            "--numerator",
            help="numerator metric query (sum of good events)",
            default=None,
        )
        create_parser.add_argument(
            "--denominator",
            help="denominator metric query (sum of total events)",
            default=None,
        )
        create_parser.add_argument(
            "--monitor_ids",
            help="explicit monitor_ids to use (CSV)",
            default=None,
            type=set_of_ints,
        )
        create_parser.add_argument("--monitor_search", help="monitor search terms to use", default=None)
        create_parser.add_argument(
            "--groups",
            help="for a single monitor you can specify the specific groups as a pipe (|) delimited string",
            default=None,
            type=comma_list_or_empty,
        )
        create_parser.set_defaults(func=cls._create)

        file_create_parser = verb_parsers.add_parser("fcreate", help="Create a SLO from file")
        file_create_parser.add_argument("file", help="json file holding all details", type=argparse.FileType("r"))
        file_create_parser.set_defaults(func=cls._file_create)

        update_parser = verb_parsers.add_parser("update", help="Update existing SLO")
        update_parser.add_argument("slo_id", help="SLO to replace with the new definition")
        update_parser.add_argument(
            "--type",
            help="type of the SLO (must specify it's original type)",
            choices=["metric", "monitor"],
        )
        update_parser.add_argument("--name", help="name of the SLO", default=None)
        update_parser.add_argument("--description", help="description of the SLO", default=None)
        update_parser.add_argument(
            "--thresholds",
            help="comma separated list of <timeframe>:<target>[:<warning>[:<target_display>[:<warning_display>]]",
        )
        update_parser.add_argument(
            "--tags",
            help="comma-separated list of tags",
            default=None,
            type=comma_list_or_empty,
        )
        update_parser.add_argument(
            "--numerator",
            help="numerator metric query (sum of good events)",
            default=None,
        )
        update_parser.add_argument(
            "--denominator",
            help="denominator metric query (sum of total events)",
            default=None,
        )
        update_parser.add_argument(
            "--monitor_ids",
            help="explicit monitor_ids to use (CSV)",
            default=[],
            type=list,
        )
        update_parser.add_argument("--monitor_search", help="monitor search terms to use", default=None)
        update_parser.add_argument(
            "--groups",
            help="for a single monitor you can specify the specific groups as a pipe (|) delimited string",
            default=None,
        )
        update_parser.set_defaults(func=cls._update)

        file_update_parser = verb_parsers.add_parser("fupdate", help="Update existing SLO from file")
        file_update_parser.add_argument("file", help="json file holding all details", type=argparse.FileType("r"))
        file_update_parser.set_defaults(func=cls._file_update)

        show_parser = verb_parsers.add_parser("show", help="Show a SLO definition")
        show_parser.add_argument("slo_id", help="SLO to show")
        show_parser.set_defaults(func=cls._show)

        show_all_parser = verb_parsers.add_parser("show_all", help="Show a list of all SLOs")
        show_all_parser.add_argument("--query", help="string to filter SLOs by query (see UI or documentation)")
        show_all_parser.add_argument(
            "--slo_ids",
            help="comma separated list indicating what SLO IDs to get at once",
            type=comma_set,
        )
        show_all_parser.add_argument("--offset", help="offset of query pagination", default=0)
        show_all_parser.add_argument("--limit", help="limit of query pagination", default=100)
        show_all_parser.set_defaults(func=cls._show_all)

        delete_parser = verb_parsers.add_parser("delete", help="Delete a SLO")
        delete_parser.add_argument("slo_id", help="SLO to delete")
        delete_parser.set_defaults(func=cls._delete)

        delete_many_parser = verb_parsers.add_parser("delete_many", help="Delete a SLO")
        delete_many_parser.add_argument("slo_ids", help="comma separated list of SLO IDs to delete", type=comma_set)
        delete_many_parser.set_defaults(func=cls._delete_many)

        delete_timeframe_parser = verb_parsers.add_parser("delete_many_timeframe", help="Delete a SLO timeframe")
        delete_timeframe_parser.add_argument("slo_id", help="SLO ID to update")
        delete_timeframe_parser.add_argument(
            "timeframes",
            help="CSV of timeframes to delete, e.g. 7d,30d,90d",
            type=comma_set,
        )
        delete_timeframe_parser.set_defaults(func=cls._delete_timeframe)

        can_delete_parser = verb_parsers.add_parser("can_delete", help="Check if can delete SLOs")
        can_delete_parser.add_argument("slo_ids", help="comma separated list of SLO IDs to delete", type=comma_set)
        can_delete_parser.set_defaults(func=cls._can_delete)

        history_parser = verb_parsers.add_parser("history", help="Get the SLO history")
        history_parser.add_argument("slo_id", help="SLO to query the history")
        history_parser.add_argument(
            "from_ts",
            type=parse_date_as_epoch_timestamp,
            help="`from` date or timestamp",
        )
        history_parser.add_argument(
            "to_ts",
            type=parse_date_as_epoch_timestamp,
            help="`to` date or timestamp",
        )
        history_parser.set_defaults(func=cls._history)

    @classmethod
    def _create(cls, args):
        api._timeout = args.timeout
        format = args.format

        params = {"type": args.type, "name": args.name}

        if args.tags:
            tags = sorted(set([t.strip() for t in args.tags.split(",") if t.strip()]))
            params["tags"] = tags

        thresholds = []
        for threshold_str in args.thresholds.split(","):
            parts = threshold_str.split(":")
            timeframe = parts[0]
            target = float(parts[1])

            threshold = {"timeframe": timeframe, "target": target}

            if len(parts) > 2:
                threshold["warning"] = float(parts[2])

            if len(parts) > 3 and parts[3]:
                threshold["target_display"] = parts[3]

            if len(parts) > 4 and parts[4]:
                threshold["warning_display"] = parts[4]

            thresholds.append(threshold)
        params["thresholds"] = thresholds

        if args.description:
            params["description"] = args.description

        if args.type == "metric":
            params["query"] = {
                "numerator": args.numerator,
                "denominator": args.denominator,
            }
        elif args.monitor_search:
            params["monitor_search"] = args.monitor_search
        else:
            params["monitor_ids"] = list(args.monitor_ids)
            if args.groups and len(args.monitor_ids) == 1:
                groups = args.groups.split("|")
                params["groups"] = groups

        if args.tags:
            params["tags"] = args.tags

        res = api.ServiceLevelObjective.create(**params)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _file_create(cls, args):
        api._timeout = args.timeout
        format = args.format
        slo = json.load(args.file)
        res = api.ServiceLevelObjective.create(return_raw=True, **slo)
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

        params = {"type": args.type}

        if args.thresholds:
            thresholds = []
            for threshold_str in args.thresholds.split(","):
                parts = threshold_str.split(":")
                timeframe = parts[0]
                target = parts[1]

                threshold = {"timeframe": timeframe, "target": target}

                if len(parts) > 2:
                    threshold["warning"] = float(parts[2])

                if len(parts) > 3 and parts[3]:
                    threshold["target_display"] = parts[3]

                if len(parts) > 4 and parts[4]:
                    threshold["warning_display"] = parts[4]

                thresholds.append(threshold)
            params["thresholds"] = thresholds

        if args.description:
            params["description"] = args.description

        if args.type == "metric":
            if args.numerator and args.denominator:
                params["query"] = {
                    "numerator": args.numerator,
                    "denominator": args.denominator,
                }
        elif args.monitor_search:
            params["monitor_search"] = args.monitor_search
        else:
            params["monitor_ids"] = args.monitor_ids
            if args.groups and len(args.monitor_ids) == 1:
                groups = args.groups.split("|")
                params["groups"] = groups

        if args.tags:
            tags = sorted(set([t.strip() for t in args.tags if t.strip()]))
            params["tags"] = tags
        res = api.ServiceLevelObjective.update(args.slo_id, return_raw=True, **params)
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
        slo = json.load(args.file)

        res = api.ServiceLevelObjective.update(slo["id"], return_raw=True, **slo)
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
        res = api.ServiceLevelObjective.get(args.slo_id, return_raw=True)
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

        params = {"offset": args.offset, "limit": args.limit}
        if args.query:
            params["query"] = args.query
        else:
            params["ids"] = args.slo_ids

        res = api.ServiceLevelObjective.get_all(return_raw=True, **params)
        report_warnings(res)
        report_errors(res)

        if format == "pretty":
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _delete(cls, args):
        api._timeout = args.timeout
        res = api.ServiceLevelObjective.delete(args.slo_id, return_raw=True)
        if res is not None:
            report_warnings(res)
            report_errors(res)

            if format == "pretty":
                print(pretty_json(res))
            else:
                print(json.dumps(res))

    @classmethod
    def _delete_many(cls, args):
        api._timeout = args.timeout
        res = api.ServiceLevelObjective.delete_many(args.slo_ids)
        if res is not None:
            report_warnings(res)
            report_errors(res)

            if format == "pretty":
                print(pretty_json(res))
            else:
                print(json.dumps(res))

    @classmethod
    def _delete_timeframe(cls, args):
        api._timeout = args.timeout

        ops = {args.slo_id: args.timeframes}

        res = api.ServiceLevelObjective.bulk_delete(ops)
        if res is not None:
            report_warnings(res)
            report_errors(res)

            if format == "pretty":
                print(pretty_json(res))
            else:
                print(json.dumps(res))

    @classmethod
    def _can_delete(cls, args):
        api._timeout = args.timeout

        res = api.ServiceLevelObjective.can_delete(args.slo_ids)
        if res is not None:
            report_warnings(res)
            report_errors(res)

            if format == "pretty":
                print(pretty_json(res))
            else:
                print(json.dumps(res))

    @classmethod
    def _history(cls, args):
        api._timeout = args.timeout

        res = api.ServiceLevelObjective.history(args.slo_id)
        if res is not None:
            report_warnings(res)
            report_errors(res)

            if format == "pretty":
                print(pretty_json(res))
            else:
                print(json.dumps(res))

    @classmethod
    def _escape(cls, s):
        return s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
