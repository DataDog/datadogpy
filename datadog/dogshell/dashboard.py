# stdlib
import json
import platform
import sys
import webbrowser

# 3p
import argparse

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings, print_err
from datadog.util.format import pretty_json
from datetime import datetime


class DashboardClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('dashboard', help="Create, edit, and delete dashboards")

        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser('post', help="Create dashboards")
        post_parser.add_argument('title', help="title for the new dashboard")
        post_parser.add_argument('description', help="short description of the dashboard")
        post_parser.add_argument('widgets', help="widget definitions as a JSON string. if unset,"
                                 " reads from stdin.", nargs="?")
        post_parser.add_argument('--template_variables', type=_template_variables, default=[],
                                 help="a json list of template variable dicts, e.g. "
                                 "[{'name': 'host', 'prefix': 'host', "
                                 "'default': 'host:my-host'}]\'")

        post_parser.set_defaults(func=cls._post)

        update_parser = verb_parsers.add_parser('update', help="Update existing dashboards")
        update_parser.add_argument('dashboard_id', help="dashboard to replace"
                                   " with the new definition")
        update_parser.add_argument('title', help="new title for the dashboard")
        update_parser.add_argument('description', help="short description of the dashboard")
        update_parser.add_argument('widgets', help="widget definitions as a JSON string."
                                   " if unset, reads from stdin", nargs="?")
        update_parser.add_argument('--template_variables', type=_template_variables, default=[],
                                   help="a json list of template variable dicts, e.g. "
                                   "[{'name': 'host', 'prefix': 'host', "
                                   "'default': 'host:my-host'}]\'")
        update_parser.set_defaults(func=cls._update)

        show_parser = verb_parsers.add_parser('show', help="Show a dashboard definition")
        show_parser.add_argument('dashboard_id', help="dashboard to show")
        show_parser.set_defaults(func=cls._show)

        pull_parser = verb_parsers.add_parser('pull', help="Pull a dashboard on the server"
                                              " into a local file")
        pull_parser.add_argument('dashboard_id', help="ID of dashboard to pull")
        pull_parser.add_argument('filename', help="file to pull dashboard into")
        pull_parser.set_defaults(func=cls._pull)

        push_parser = verb_parsers.add_parser('push', help="Push updates to dashboards"
                                              " from local files to the server")
        push_parser.add_argument('--append_auto_text', action='store_true', dest='append_auto_text',
                                 help="When pushing to the server, appends filename"
                                 " and timestamp to the end of the dashboard description")
        push_parser.add_argument('file', help="dashboard files to push to the server",
                                 nargs='+', type=argparse.FileType('r'))
        push_parser.set_defaults(func=cls._push)

        new_file_parser = verb_parsers.add_parser('new_file', help="Create a new dashboard"
                                                  " and put its contents in a file")
        new_file_parser.add_argument('filename', help="name of file to create with empty dashboard")
        new_file_parser.add_argument('widgets', help="widget definitions as a JSON string."
                                     " if unset, reads from stdin.", nargs="?")
        new_file_parser.set_defaults(func=cls._new_file)

        web_view_parser = verb_parsers.add_parser('web_view',
                                                  help="View the dashboard in a web browser")
        web_view_parser.add_argument('file', help="dashboard file", type=argparse.FileType('r'))
        web_view_parser.set_defaults(func=cls._web_view)

        delete_parser = verb_parsers.add_parser('delete', help="Delete dashboards")
        delete_parser.add_argument('dashboard_id', help="dashboard to delete")
        delete_parser.set_defaults(func=cls._delete)

    @classmethod
    def _pull(cls, args):
        cls._write_dash_to_file(
            args.dashboard_id, args.filename,
            args.timeout, args.format)

    @classmethod
    def _new_file(cls, args):
        api._timeout = args.timeout
        format = args.format
        widgets = args.widgets
        if args.widgets is None:
            widgets = sys.stdin.read()
        try:
            widgets = json.loads(widgets)
        except:
            raise Exception('bad json parameter')
        res = api.Dashboard.create(
            title=args.filename,
            description="Description for {0}".format(args.filename),
            widgets=widgets, layout_type="ordered")
        report_warnings(res)
        report_errors(res)

        cls._write_dash_to_file(res['id'], args.filename,
                                args.timeout, format)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _write_dash_to_file(cls, dash_id, filename, timeout, format='raw'):
        with open(filename, "w") as f:
            res = api.Dashboard.get(dash_id)
            report_warnings(res)
            report_errors(res)

            json.dump(res, f, indent=2)

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
                res = api.Dashboard.update(
                    dash_obj["id"],
                    title=dash_obj["title"],
                    description=dash_obj["description"],
                    widgets=dash_obj["widgets"],
                    layout_type="ordered",
                    template_variables=tpl_vars)
            else:
                res = api.Dashboard.create(
                    title=dash_obj["title"],
                    description=dash_obj["description"],
                    widgets=dash_obj["widgets"],
                    layout_type="ordered",
                    template_variables=tpl_vars)
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
        widgets = args.widgets
        if args.widgets is None:
            widgets = sys.stdin.read()
        try:
            widgets = json.loads(widgets)
        except:
            raise Exception('bad json parameter')
        res = api.Dashboard.create(
            title=args.title,
            description=args.description,
            widgets=widgets,
            layout_type="ordered",
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
        widgets = args.widgets
        if args.widgets is None:
            widgets = sys.stdin.read()
        try:
            widgets = json.loads(widgets)
        except:
            raise Exception('bad json parameter')

        res = api.Dashboard.update(
            args.dashboard_id,
            title=args.title,
            description=args.description,
            widgets=widgets,
            layout_type="ordered",
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
        res = api.Dashboard.get(args.dashboard_id)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
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

    @classmethod
    def _web_view(cls, args):
        dash_id = json.load(args.file)['id']
        # url = api._api_host + "/dashboard/{0}".format(dash_id)
        url = api._api_host + "/dashboard/{0}".format(dash_id)
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
