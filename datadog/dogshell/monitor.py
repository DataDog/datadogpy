# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings
from datadog.util.compat import json


class MonitorClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('monitor', help="Create, edit, and delete monitors")
        parser.add_argument('--string_ids', action='store_true', dest='string_ids',
                            help="Represent monitor IDs as strings instead of ints in JSON")

        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser('post', help="Create a monitor")
        post_parser.add_argument('type', help="type of the monitor, e.g."
                                 "'metric alert' 'service check'")
        post_parser.add_argument('query', help="query to notify on with syntax varying "
                                 "depending on what type of monitor you are creating")
        post_parser.add_argument('--name', help="name of the alert", default=None)
        post_parser.add_argument('--message', help="message to include with notifications"
                                 " for this monitor", default=None)
        post_parser.add_argument('--options', help="json options for the monitor", default=None)
        post_parser.set_defaults(func=cls._post)

        update_parser = verb_parsers.add_parser('update', help="Update existing monitor")
        update_parser.add_argument('monitor_id', help="monitor to replace with the new definition")
        update_parser.add_argument('type', help="type of the monitor, e.g. "
                                   "'metric alert' 'service check'")
        update_parser.add_argument('query', help="query to notify on with syntax varying"
                                   " depending on what type of monitor you are creating")
        update_parser.add_argument('--name', help="name of the alert", default=None)
        update_parser.add_argument('--message', help="message to include with "
                                   "notifications for this monitor", default=None)
        update_parser.add_argument('--options', help="json options for the monitor", default=None)
        update_parser.set_defaults(func=cls._update)

        show_parser = verb_parsers.add_parser('show', help="Show a monitor definition")
        show_parser.add_argument('monitor_id', help="monitor to show")
        show_parser.set_defaults(func=cls._show)

        show_all_parser = verb_parsers.add_parser('show_all', help="Show a list of all monitors")
        show_all_parser.set_defaults(func=cls._show_all)

        delete_parser = verb_parsers.add_parser('delete', help="Delete a monitor")
        delete_parser.add_argument('monitor_id', help="monitor to delete")
        delete_parser.set_defaults(func=cls._delete)

        mute_all_parser = verb_parsers.add_parser('mute_all', help="Globally mute "
                                                  "monitors (downtime over *)")
        mute_all_parser.set_defaults(func=cls._mute_all)

        unmute_all_parser = verb_parsers.add_parser('unmute_all', help="Globally unmute "
                                                    "monitors (cancel downtime over *)")
        unmute_all_parser.set_defaults(func=cls._unmute_all)

        mute_parser = verb_parsers.add_parser('mute', help="Mute a monitor")
        mute_parser.add_argument('monitor_id', help="monitor to mute")
        mute_parser.add_argument('--scope', help="scope to apply the mute to,"
                                 " e.g. role:db (optional)", default=[])
        mute_parser.add_argument('--end', help="POSIX timestamp for when"
                                 " the mute should end (optional)", default=None)
        mute_parser.set_defaults(func=cls._mute)

        unmute_parser = verb_parsers.add_parser('unmute', help="Unmute a monitor")
        unmute_parser.add_argument('monitor_id', help="monitor to unmute")
        unmute_parser.add_argument('--scope', help="scope to unmute (must be muted), "
                                   "e.g. role:db", default=[])
        unmute_parser.add_argument('--all_scopes', help="clear muting across all scopes",
                                   action='store_true')
        unmute_parser.set_defaults(func=cls._unmute)

    @classmethod
    def _post(cls, args):
        api._timeout = args.timeout
        format = args.format
        options = None
        if args.options is not None:
            try:
                options = json.loads(args.options)
            except:
                raise Exception('bad json parameter')
        res = api.Monitor.create(type=args.type, query=args.query, name=args.name,
                                 message=args.message, options=options)
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
        options = None
        if args.options is not None:
            try:
                options = json.loads(args.options)
            except:
                raise Exception('bad json parameter')
        res = api.Monitor.update(args.monitor_id, type=args.type, query=args.query,
                                 name=args.name, message=args.message, options=options)
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
        res = api.Monitor.get(args.monitor_id)
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
        res = api.Monitor.get_all()
        report_warnings(res)
        report_errors(res)

        if args.string_ids:
            for d in res:
                d["id"] = str(d["id"])

        if format == 'pretty':
            print(pretty_json(res))
        elif format == 'raw':
            print(json.dumps(res))
        else:
            for d in res:
                print("\t".join([(str(d["id"])),
                                 (cls._escape(d["message"])),
                                 (cls._escape(d["name"])),
                                 (str(d["options"])),
                                 (str(d["org_id"])),
                                 (d["query"]),
                                 (d["type"])]))

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
        if format == 'pretty':
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
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _unmute(cls, args):
        api._timeout = args.timeout
        res = api.Monitor.unmute(args.monitor_id, scope=args.scope, all_scopes=args.all_scopes)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))
