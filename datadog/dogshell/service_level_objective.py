# stdlib
import argparse
import json

# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


class MonitorClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('service_level_objective', help="Create, edit, and delete service level objectives")

        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        create_parser = verb_parsers.add_parser('create', help="Create a SLO")
        create_parser.add_argument('--type', required=True, help="type of the SLO, e.g.", choices=["metric", "monitor"])
        create_parser.add_argument('--name', help="name of the SLO", default=None)
        create_parser.add_argument('--description', help="description of the SLO", default=None)
        create_parser.add_argument('--tags', help="comma-separated list of tags", default=None)
        create_parser.add_argument('--thresholds', help="comma separated list of <timeframe>:<target>[:<warning>]",
                                   required=True)
        create_parser.add_argument('--numerator', help='numerator metric query (sum of good events)', default=None)
        create_parser.add_argument('--denominator', help='denominator metric query (sum of total events)', default=None)
        create_parser.add_argument('--monitor_ids', help='explicit monitor_ids to use (CSV)', default=None)
        create_parser.add_argument('--monitor_search', help='monitor search terms to use', default=None)
        create_parser.set_defaults(func=cls._create)

        file_create_parser = verb_parsers.add_parser('fcreate', help="Create a SLO from file")
        file_create_parser.add_argument('file', help='json file holding all details',
                                      type=argparse.FileType('r'))
        file_create_parser.set_defaults(func=cls._file_create)

        update_parser = verb_parsers.add_parser('update', help="Update existing SLO")
        update_parser.add_argument('slo_id', help="SLO to replace with the new definition")
        update_parser.add_argument('--type', required=True, help="type of the SLO (must specify it's original type)", choices=["metric", "monitor"])
        update_parser.add_argument('--name', help="name of the SLO", default=None)
        update_parser.add_argument('--description', help="description of the SLO",
                                   default=None)
        create_parser.add_argument('--thresholds', help="comma separated list of <timeframe>:<target>[:<warning>]",
                                   required=True)
        update_parser.add_argument('--tags', help="comma-separated list of tags", default=None)
        update_parser.add_argument('--numerator', help='numerator metric query (sum of good events)', default=None)
        update_parser.add_argument('--denominator', help='denominator metric query (sum of total events)', default=None)
        update_parser.add_argument('--monitor_ids', help='explicit monitor_ids to use (CSV)', default=None)
        update_parser.add_argument('--monitor_search', help='monitor search terms to use', default=None)
        update_parser.set_defaults(func=cls._update)

        file_update_parser = verb_parsers.add_parser('fupdate', help="Update existing SLO from file")
        file_update_parser.add_argument('file', help='json file holding all details',
                                        type=argparse.FileType('r'))
        file_update_parser.set_defaults(func=cls._file_update)

        show_parser = verb_parsers.add_parser('show', help="Show a SLO definition")
        show_parser.add_argument('slo_id', help="SLO to show")
        show_parser.set_defaults(func=cls._show)

        show_all_parser = verb_parsers.add_parser('show_all', help="Show a list of all SLOs")
        show_all_parser.add_argument('--query', help="string to filter SLOs by query (see UI or documentation)")
        show_all_parser.add_argument('--slo_ids', help="comma separated list indicating what SLO IDs to get at once")
        show_all_parser.add_argument('--offset', help="offset of query pagination", default=0)
        show_all_parser.add_argument('--limit', help="limit of query pagination", default=100)
        show_all_parser.set_defaults(func=cls._show_all)

        delete_parser = verb_parsers.add_parser('delete', help="Delete a SLO")
        delete_parser.add_argument('slo_id', help="SLO to delete")
        delete_parser.set_defaults(func=cls._delete)

        delete_many_parser = verb_parsers.add_parser('delete_many', help="Delete a SLO")
        delete_many_parser.add_argument('slo_ids', help="comma separated list of SLO IDs to delete")
        delete_many_parser.set_defaults(func=cls._delete_many)

        delete_timeframe_parser = verb_parsers.add_parser('delete_many', help="Delete a SLO timeframe")
        delete_timeframe_parser.add_argument('slo_id', help="SLO ID to update")
        delete_timeframe_parser.add_argument('timeframes', help="CSV of timeframes to delete, e.g. 7d,30d,90d", required=True)
        delete_timeframe_parser.set_defaults(func=cls._delete_timeframe)

    @classmethod
    def _create(cls, args):
        api._timeout = args.timeout
        format = args.format

        if args.tags:
            tags = sorted(set([t.strip() for t in args.tags.split(',') if t.strip()]))
        else:
            tags = None

        params = {
            "type": args.type,
            "name": args.name,
        }

        thresholds = []
        for threshold_str in args.thresholds.split(","):
            parts = threshold_str.split(":")
            timeframe = parts[0]
            target = parts[1]
            warning = None
            if len(parts) > 2:
                warning = parts[2]
            thresholds.append({"timeframe": timeframe, "target": target, "warning": warning})
        params["thresholds"] = thresholds

        if args.description:
            params["description"] = args.description

        if args.type == "metric":
            params["query"] = {
                "numerator": args.numerator,
                "denominator": args.denominator
            }
        elif args.monitor_search:
            params["monitor_search"] = args.monitor_search
        else:
            params["monitor_ids"] = args.monitor_ids

        if args.tags:
            params["tags"] = args.tags.split(",")

        res = api.ServiceLevelObjective.create(**params)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _file_create(cls, args):
        api._timeout = args.timeout
        format = args.format
        slo = json.load(args.file)

        params = {
            "type": slo["type"],
            "name": slo["name"],
            "thresholds": slo["thresholds"]
        }

        if slo.get("description"):
            params["description"] = slo["description"]

        if slo["type"] == "metric":
            params["query"] = {
                "numerator":  slo["numerator"],
                "denominator": slo["denominator"]
            }
        elif slo.get("monitor_search"):
            params["monitor_search"] = slo["monitor_search"]
        else:
            params["monitor_ids"] = slo["monitor_ids"]

        if slo.get("tags"):
            tags = slo["tags"]
            if isinstance(tags, str):
                tags = tags.split(",")
            params["tags"] = tags

        res = api.ServiceLevelObjective.create(**params)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _update(cls, args):
        api._timeout = args.timeout
        format = args.format

        params = {
            "type": args.type
        }

        if args.thresholds:
            thresholds = []
            for threshold_str in args.thresholds.split(","):
                parts = threshold_str.split(":")
                timeframe = parts[0]
                target = parts[1]
                warning = None
                if len(parts) > 2:
                    warning = parts[2]
                thresholds.append({"timeframe": timeframe, "target": target, "warning": warning})
            params["thresholds"] = thresholds

        if args.description:
            params["description"] = args.description

        if args.type == "metric":
            if args.numerator and args.denominator:
                params["query"] = {
                    "numerator":  args.numerator,
                    "denominator": args.denominator
                }
        elif args.monitor_search:
            params["monitor_search"] = args.monitor_search
        else:
            params["monitor_ids"] = args.monitor_ids

        if args.tags:
            tags = args.tags
            if isinstance(tags, str):
                tags = tags.split(",")
            params["tags"] = tags
        res = api.ServiceLevelObjective.update(args.slo_id, **params)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _file_update(cls, args):
        api._timeout = args.timeout
        format = args.format
        slo = json.load(args.file)

        params = {
            "type": slo["type"],
            "name": slo["name"],
        }

        if slo.get("thresholds"):
            thresholds = []
            for threshold_str in args.thresholds.split(","):
                parts = threshold_str.split(":")
                timeframe = parts[0]
                target = parts[1]
                warning = None
                if len(parts) > 2:
                    warning = parts[2]
                thresholds.append({"timeframe": timeframe, "target": target, "warning": warning})
            params["thresholds"] = thresholds

        if slo.get("description"):
            params["description"] = slo["description"]

        if slo["type"] == "metric":
            params["query"] = {
                "numerator": slo["numerator"],
                "denominator": slo["denominator"]
            }
        elif slo.get("monitor_search"):
            params["monitor_search"] = slo["monitor_search"]
        else:
            params["monitor_ids"] = slo["monitor_ids"]

        if slo.get("tags"):
            tags = slo["tags"]
            if isinstance(tags, str):
                tags = tags.split(",")
            params["tags"] = tags

        res = api.ServiceLevelObjective.update(slo['id'], **params)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.ServiceLevelObjective.get(args.slo_id)
        report_warnings(res)
        report_errors(res)

        if args.string_ids:
            res["id"] = str(res["id"])

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show_all(cls, args):
        api._timeout = args.timeout
        format = args.format

        params = {
            "offset": args.offset,
            "limit": args.limit,
        }
        if args.query:
            params["query"] = args.query
        else:
            params["ids"] = args.slo_ids

        res = api.ServiceLevelObjective.get_all(**params)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _delete(cls, args):
        api._timeout = args.timeout
        res = api.ServiceLevelObjective.delete(args.slo_id)
        if res is not None:
            report_warnings(res)
            report_errors(res)

            if format == 'pretty':
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

            if format == 'pretty':
                print(pretty_json(res))
            else:
                print(json.dumps(res))

    @classmethod
    def _delete_timeframe(cls, args):
        api._timeout = args.timeout

        ops = {
            args.slo_id: args.timeframes.split(","),
        }


        res = api.ServiceLevelObjective.bulk_delete(ops)
        if res is not None:
            report_warnings(res)
            report_errors(res)

            if format == 'pretty':
                print(pretty_json(res))
            else:
                print(json.dumps(res))

    @classmethod
    def _escape(cls, s):
        return s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
