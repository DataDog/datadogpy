# stdlib
import os.path

# 3p
import argparse

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings, print_err
from datadog.util.compat import json
from datadog.util.format import pretty_json


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
        show_all_parser.add_argument(
            '--group_states', help="comma separated list of group states to filter by"
            "(choose one or more from 'all', 'alert', 'warn', or 'no data')"
        )
        show_all_parser.add_argument('--name', help="string to filter monitors by name")
        show_all_parser.add_argument(
            '--tags', help="comma separated list indicating what tags, if any, "
            "should be used to filter the list of monitors by scope (e.g. 'host:host0')"
        )
        show_all_parser.add_argument(
            '--monitor_tags', help="comma separated list indicating what service "
            "and/or custom tags, if any, should be used to filter the list of monitors"
        )

        show_all_parser.set_defaults(func=cls._show_all)

        pull_parser = verb_parsers.add_parser('pull', help="Pull a monitor on the server"
                                              " into a local file")
        pull_parser.add_argument('monitor_id', help="ID of monitor to pull")
        pull_parser.add_argument('filename', help="file to pull monitor into")
        pull_parser.set_defaults(func=cls._pull)

        pull_all_parser = verb_parsers.add_parser('pull_all', help="Pull all monitors"
                                                  " into files in a directory")
        pull_all_parser.add_argument('pull_dir', help="directory to pull monitors into")
        pull_all_parser.add_argument(
            '--group_states', help="comma separated list of group states to filter by",
            choices=['all', 'alert', 'warn', 'no data']
        )
        pull_all_parser.add_argument('--name', help="string to filter monitors by name")
        pull_all_parser.add_argument(
            '--tags', help="comma separated list indicating what tags, if any, "
            "should be used to filter the list of monitors by scope (e.g. 'host:host0')"
        )
        pull_all_parser.add_argument(
            '--monitor_tags', help="comma separated list indicating what service "
            "and/or custom tags, if any, should be used to filter the list of monitors"
        )
        pull_all_parser.set_defaults(func=cls._pull_all)

        push_parser = verb_parsers.add_parser('push', help="Push updates to monitors"
                                              " from local files to the server")
        push_parser.add_argument('file', help="monitor files to push to the server",
                                 nargs='+', type=argparse.FileType('r'))
        push_parser.set_defaults(func=cls._push)

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

        res = api.Monitor.get_all(
            group_states=args.group_states, name=args.name,
            tags=args.tags, monitor_tags=args.monitor_tags
        )
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
    def _pull(cls, args):
        api._timeout = args.timeout
        res = api.Monitor.get(args.monitor_id)
        report_warnings(res)
        report_errors(res)

        cls._write_monitor_to_file(
            res, args.filename,
            args.format, args.string_ids)

    @classmethod
    def _pull_all(cls, args):
        api._timeout = args.timeout

        def _name_to_filename(name):
            # Get a lowercased version with most punctuation stripped out...
            no_punct = ''.join([c for c in name.lower() if c.isalnum() or c in [" ", "_", "-"]])
            # Now replace all -'s, _'s and spaces with "_", and strip trailing _
            return no_punct.replace(" ", "_").replace("-", "_").strip("_")

        format = args.format
        res = api.Monitor.get_all(
            group_states=args.group_states, name=args.name,
            tags=args.tags, monitor_tags=args.monitor_tags
        )
        report_warnings(res)
        report_errors(res)

        if not os.path.exists(args.pull_dir):
            os.mkdir(args.pull_dir, 0o755)

        used_filenames = set()
        for monitor_summary in res:
            filename = _name_to_filename(monitor_summary['name'])
            if filename in used_filenames:
                filename = "{0}-{1}".format(filename, monitor_summary['id'])
            used_filenames.add(filename)

            cls._write_monitor_to_file(
                monitor_summary, os.path.join(args.pull_dir, filename + ".json"),
                format, args.string_ids)
        if format == 'pretty':
            print(("\n### Total: {0} monitors to {1} ###"
                  .format(len(used_filenames), os.path.realpath(args.pull_dir))))

    @classmethod
    def _push(cls, args):
        api._timeout = args.timeout
        for f in args.file:
            try:
                monitor_obj = json.load(f)
            except Exception as err:
                raise Exception("Could not parse {0}: {1}".format(f.name, err))

            if 'id' in monitor_obj:
                # Always convert to int, in case it was originally a string.
                monitor_obj["id"] = int(monitor_obj["id"])
                res = api.Monitor.update(**monitor_obj)
            else:
                res = api.Monitor.create(**monitor_obj)

            if 'errors' in res:
                print_err('Upload of monitor {0} from file {1} failed.'
                          .format(monitor_obj["id"], f.name))

            report_warnings(res)
            report_errors(res)

            if format == 'pretty':
                print(pretty_json(res))
            else:
                print(json.dumps(res))

            if args.format == 'pretty':
                print("Uploaded file {0} (monitor {1})".format(f.name, monitor_obj["id"]))

    @classmethod
    def _write_monitor_to_file(cls, monitor, filename, format='raw', string_ids=False):
        with open(filename, "w") as f:
            keys = ('id', 'message', 'query', 'options', 'type', 'tags', 'name')
            monitor_obj = {k: v for k, v in monitor.items() if k in keys}
            monitor_id = monitor_obj['id']

            if string_ids:
                monitor_obj['id'] = str(monitor_id)

            json.dump(monitor_obj, f, indent=2)

            if format == 'pretty':
                print("Downloaded monitor {0} to file {1}".format(monitor_id, filename))
            else:
                print("{0} {1}".format(monitor_id, filename))

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
