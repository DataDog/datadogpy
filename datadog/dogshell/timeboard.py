# stdlib
import os.path
import platform
import sys
import webbrowser

# 3p
import argparse

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings, print_err
from datadog.util.compat import json
from datadog.util.format import pretty_json
from datetime import datetime


class TimeboardClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('timeboard', help="Create, edit, and delete timeboards")
        parser.add_argument('--string_ids', action='store_true', dest='string_ids',
                            help="Represent timeboard IDs as strings instead of ints in JSON")

        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser('post', help="Create timeboards")
        post_parser.add_argument('title', help="title for the new timeboard")
        post_parser.add_argument('description', help="short description of the timeboard")
        post_parser.add_argument('graphs', help="graph definitions as a JSON string. if unset,"
                                 " reads from stdin.", nargs="?")
        post_parser.add_argument('--template_variables', type=_template_variables, default=[],
                                 help="a json list of template variable dicts, e.g. "
                                 "[{'name': 'host', 'prefix': 'host', "
                                 "'default': 'host:my-host'}]\'")

        post_parser.set_defaults(func=cls._post)

        update_parser = verb_parsers.add_parser('update', help="Update existing timeboards")
        update_parser.add_argument('timeboard_id', help="timeboard to replace"
                                   " with the new definition")
        update_parser.add_argument('title', help="new title for the timeboard")
        update_parser.add_argument('description', help="short description of the timeboard")
        update_parser.add_argument('graphs', help="graph definitions as a JSON string."
                                   " if unset, reads from stdin", nargs="?")
        update_parser.add_argument('--template_variables', type=_template_variables, default=[],
                                   help="a json list of template variable dicts, e.g. "
                                   "[{'name': 'host', 'prefix': 'host', "
                                   "'default': 'host:my-host'}]\'")
        update_parser.set_defaults(func=cls._update)

        show_parser = verb_parsers.add_parser('show', help="Show a timeboard definition")
        show_parser.add_argument('timeboard_id', help="timeboard to show")
        show_parser.set_defaults(func=cls._show)

        show_all_parser = verb_parsers.add_parser('show_all', help="Show a list of all timeboards")
        show_all_parser.set_defaults(func=cls._show_all)

        pull_parser = verb_parsers.add_parser('pull', help="Pull a timeboard on the server"
                                              " into a local file")
        pull_parser.add_argument('timeboard_id', help="ID of timeboard to pull")
        pull_parser.add_argument('filename', help="file to pull timeboard into")
        pull_parser.set_defaults(func=cls._pull)

        pull_all_parser = verb_parsers.add_parser('pull_all', help="Pull all timeboards"
                                                  " into files in a directory")
        pull_all_parser.add_argument('pull_dir', help="directory to pull timeboards into")
        pull_all_parser.set_defaults(func=cls._pull_all)

        push_parser = verb_parsers.add_parser('push', help="Push updates to timeboards"
                                              " from local files to the server")
        push_parser.add_argument('--append_auto_text', action='store_true', dest='append_auto_text',
                                 help="When pushing to the server, appends filename"
                                 " and timestamp to the end of the timeboard description")
        push_parser.add_argument('file', help="timeboard files to push to the server",
                                 nargs='+', type=argparse.FileType('r'))
        push_parser.set_defaults(func=cls._push)

        new_file_parser = verb_parsers.add_parser('new_file', help="Create a new timeboard"
                                                  " and put its contents in a file")
        new_file_parser.add_argument('filename', help="name of file to create with empty timeboard")
        new_file_parser.add_argument('graphs', help="graph definitions as a JSON string."
                                     " if unset, reads from stdin.", nargs="?")
        new_file_parser.set_defaults(func=cls._new_file)

        web_view_parser = verb_parsers.add_parser('web_view',
                                                  help="View the timeboard in a web browser")
        web_view_parser.add_argument('file', help="timeboard file", type=argparse.FileType('r'))
        web_view_parser.set_defaults(func=cls._web_view)

        delete_parser = verb_parsers.add_parser('delete', help="Delete timeboards")
        delete_parser.add_argument('timeboard_id', help="timeboard to delete")
        delete_parser.set_defaults(func=cls._delete)

    @classmethod
    def _pull(cls, args):
        cls._write_dash_to_file(
            args.timeboard_id, args.filename,
            args.timeout, args.format, args.string_ids)

    @classmethod
    def _pull_all(cls, args):
        api._timeout = args.timeout

        def _title_to_filename(title):
            # Get a lowercased version with most punctuation stripped out...
            no_punct = ''.join([c for c in title.lower() if c.isalnum() or c in [" ", "_", "-"]])
            # Now replace all -'s, _'s and spaces with "_", and strip trailing _
            return no_punct.replace(" ", "_").replace("-", "_").strip("_")

        format = args.format
        res = api.Timeboard.get_all()
        report_warnings(res)
        report_errors(res)

        if not os.path.exists(args.pull_dir):
            os.mkdir(args.pull_dir, 0o755)

        used_filenames = set()
        for dash_summary in res['dashes']:
            filename = _title_to_filename(dash_summary['title'])
            if filename in used_filenames:
                filename = filename + "-" + dash_summary['id']
            used_filenames.add(filename)

            cls._write_dash_to_file(
                dash_summary['id'], os.path.join(args.pull_dir, filename + ".json"),
                args.timeout, format, args.string_ids)
        if format == 'pretty':
            print(("\n### Total: {0} dashboards to {1} ###"
                  .format(len(used_filenames), os.path.realpath(args.pull_dir))))

    @classmethod
    def _new_file(cls, args):
        api._timeout = args.timeout
        format = args.format
        graphs = args.graphs
        if args.graphs is None:
            graphs = sys.stdin.read()
        try:
            graphs = json.loads(graphs)
        except:
            raise Exception('bad json parameter')
        res = api.Timeboard.create(
            title=args.filename,
            description="Description for {0}".format(args.filename),
            graphs=[graphs])
        report_warnings(res)
        report_errors(res)

        cls._write_dash_to_file(res['dash']['id'], args.filename,
                                args.timeout, format, args.string_ids)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _write_dash_to_file(cls, dash_id, filename, timeout, format='raw', string_ids=False):
        with open(filename, "w") as f:
            res = api.Timeboard.get(dash_id)
            report_warnings(res)
            report_errors(res)

            dash_obj = res["dash"]
            if "resource" in dash_obj:
                del dash_obj["resource"]
            if "url" in dash_obj:
                del dash_obj["url"]

            if string_ids:
                dash_obj["id"] = str(dash_obj["id"])

            json.dump(dash_obj, f, indent=2)

            if format == 'pretty':
                print(u"Downloaded dashboard {0} to file {1}".format(dash_id, filename))
            else:
                print(u"{0} {1}".format(dash_id, filename))

    @classmethod
    def _push(cls, args):
        api._timeout = args.timeout
        for f in args.file:
            try:
                dash_obj = json.load(f)
            except Exception as err:
                raise Exception("Could not parse {0}: {1}".format(f.name, err))

            if args.append_auto_text:
                datetime_str = datetime.now().strftime('%x %X')
                auto_text = ("<br/>\nUpdated at {0} from {1} ({2}) on {3}"
                             .format(datetime_str, f.name, dash_obj["id"], platform.node()))
                dash_obj["description"] += auto_text
            tpl_vars = dash_obj.get("template_variables", [])

            if 'id' in dash_obj:
                # Always convert to int, in case it was originally a string.
                dash_obj["id"] = int(dash_obj["id"])
                res = api.Timeboard.update(dash_obj["id"], title=dash_obj["title"],
                                           description=dash_obj["description"],
                                           graphs=dash_obj["graphs"], template_variables=tpl_vars)
            else:
                res = api.Timeboard.create(title=dash_obj["title"],
                                           description=dash_obj["description"],
                                           graphs=dash_obj["graphs"], template_variables=tpl_vars)

            if 'errors' in res:
                print_err('Upload of dashboard {0} from file {1} failed.'
                          .format(dash_obj["id"], f.name))

            report_warnings(res)
            report_errors(res)

            if format == 'pretty':
                print(pretty_json(res))
            else:
                print(json.dumps(res))

            if args.format == 'pretty':
                print("Uploaded file {0} (dashboard {1})".format(f.name, dash_obj["id"]))

    @classmethod
    def _post(cls, args):
        api._timeout = args.timeout
        format = args.format
        graphs = args.graphs
        if args.graphs is None:
            graphs = sys.stdin.read()
        try:
            graphs = json.loads(graphs)
        except:
            raise Exception('bad json parameter')
        res = api.Timeboard.create(title=args.title, description=args.description, graphs=[graphs],
                                   template_variables=args.template_variables)
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
        graphs = args.graphs
        if args.graphs is None:
            graphs = sys.stdin.read()
        try:
            graphs = json.loads(graphs)
        except:
            raise Exception('bad json parameter')

        res = api.Timeboard.update(args.timeboard_id, title=args.title,
                                   description=args.description, graphs=graphs,
                                   template_variables=args.template_variables)
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
        res = api.Timeboard.get(args.timeboard_id)
        report_warnings(res)
        report_errors(res)

        if args.string_ids:
            res["dash"]["id"] = str(res["dash"]["id"])

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show_all(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Timeboard.get_all()
        report_warnings(res)
        report_errors(res)

        if args.string_ids:
            for d in res["dashes"]:
                d["id"] = str(d["id"])

        if format == 'pretty':
            print(pretty_json(res))
        elif format == 'raw':
            print(json.dumps(res))
        else:
            for d in res["dashes"]:
                print("\t".join([(d["id"]),
                                 (d["resource"]),
                                 (d["title"]),
                                 cls._escape(d["description"])]))

    @classmethod
    def _delete(cls, args):
        api._timeout = args.timeout
        res = api.Timeboard.delete(args.timeboard_id)
        if res is not None:
            report_warnings(res)
            report_errors(res)

    @classmethod
    def _web_view(cls, args):
        dash_id = json.load(args.file)['id']
        url = api._api_host + "/dash/dash/{0}".format(dash_id)
        webbrowser.open(url)

    @classmethod
    def _escape(cls, s):
        return s.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def _template_variables(tpl_var_input):
    if '[' not in tpl_var_input:
        return [v.strip() for v in tpl_var_input.split(',')]
    else:
        try:
            return json.loads(tpl_var_input)
        except Exception:
            raise argparse.ArgumentTypeError('bad template_variable json parameter')
