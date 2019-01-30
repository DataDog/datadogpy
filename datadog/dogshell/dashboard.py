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
        # Required arguments:
        post_parser.add_argument('title', help="title for the new dashboard")
        post_parser.add_argument('widgets', help="widget definitions as a JSON string. If unset,"
                                 " reads from stdin.", nargs="?")
        # Optional arguments:
        post_parser.add_argument('--description', help="Short description of the dashboard")
        post_parser.add_argument('--read_only', help="Whether this dashboard is read-only. "
                                 "If True, only the author and admins can make changes to it.",
                                 action='store_true')
        post_parser.add_argument('--notify_list', type=_json_string,
                                 help="A json list of user handles, e.g. "
                                 "'[\"user1@domain.com\", \"user2@domain.com\"]'")
        post_parser.add_argument('--template_variables', type=_json_string,
                                 help="A json list of template variable dicts, e.g. "
                                 "'[{\"name\": \"host\", \"prefix\": \"host\", "
                                 "\"default\": \"my-host\"}]'")
        post_parser.set_defaults(func=cls._post)

        update_parser = verb_parsers.add_parser('update', help="Update existing dashboards")
        # Required arguments:
        update_parser.add_argument('dashboard_id', help="Dashboard to replace"
                                   " with the new definition")
        update_parser.add_argument('title', help="New title for the dashboard")
        update_parser.add_argument('widgets', help="Widget definitions as a JSON string."
                                   " If unset, reads from stdin", nargs="?")
        # Optional arguments:
        update_parser.add_argument('--description', help="Short description of the dashboard")
        update_parser.add_argument('--read_only', help="Whether this dashboard is read-only. "
                                   "If True, only the author and admins can make changes to it.",
                                   action='store_true')
        update_parser.add_argument('--notify_list', type=_json_string,
                                   help="A json list of user handles, e.g. "
                                   "'[\"user1@domain.com\", \"user2@domain.com\"]'")
        update_parser.add_argument('--template_variables', type=_json_string,
                                   help="A json list of template variable dicts, e.g. "
                                   "'[{\"name\": \"host\", \"prefix\": \"host\", "
                                   "\"default\": \"my-host\"}]'")
        update_parser.set_defaults(func=cls._update)

        show_parser = verb_parsers.add_parser('show', help="Show a dashboard definition")
        show_parser.add_argument('dashboard_id', help="Dashboard to show")
        show_parser.set_defaults(func=cls._show)

        pull_parser = verb_parsers.add_parser('pull', help="Pull a dashboard on the server"
                                              " into a local file")
        pull_parser.add_argument('dashboard_id', help="ID of dashboard to pull")
        pull_parser.add_argument('filename', help="File to pull dashboard into")
        pull_parser.set_defaults(func=cls._pull)

        push_parser = verb_parsers.add_parser('push', help="Push updates to dashboards"
                                              " from local files to the server")
        push_parser.add_argument('--append_auto_text', action='store_true', dest='append_auto_text',
                                 help="When pushing to the server, appends filename"
                                 " and timestamp to the end of the dashboard description")
        push_parser.add_argument('file', help="Dashboard files to push to the server",
                                 nargs='+', type=argparse.FileType('r'))
        push_parser.set_defaults(func=cls._push)

        new_file_parser = verb_parsers.add_parser('new_file', help="Create a new dashboard"
                                                  " and put its contents in a file")
        new_file_parser.add_argument('filename', help="Name of file to create with empty dashboard")
        new_file_parser.add_argument('widgets', help="Widget definitions as a JSON string."
                                     " If unset, reads from stdin.", nargs="?")
        new_file_parser.set_defaults(func=cls._new_file)

        web_view_parser = verb_parsers.add_parser('web_view',
                                                  help="View the dashboard in a web browser")
        web_view_parser.add_argument('file', help="Dashboard file", type=argparse.FileType('r'))
        web_view_parser.set_defaults(func=cls._web_view)

        delete_parser = verb_parsers.add_parser('delete', help="Delete dashboards")
        delete_parser.add_argument('dashboard_id', help="Dashboard to delete")
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
                payload = json.load(f)
            except Exception as err:
                raise Exception("Could not parse {0}: {1}".format(f.name, err))

            if args.append_auto_text:
                if 'description' not in payload or payload['description'] is None:
                    payload["description"] = ""

                datetime_str = datetime.now().strftime('%x %X')
                auto_text = ("\nUpdated at {0} from {1} ({2}) on {3}"
                             .format(datetime_str, f.name, payload["id"], platform.node()))
                payload["description"] += auto_text
            tpl_vars = payload.get("template_variables", [])

            if 'id' in payload:
                res = api.Dashboard.update(
                    payload["id"],
                    title=payload["title"],
                    description=payload["description"],
                    widgets=payload["widgets"],
                    layout_type="ordered",
                    template_variables=tpl_vars)
            else:
                res = api.Dashboard.create(
                    title=payload["title"],
                    description=payload["description"],
                    widgets=payload["widgets"],
                    layout_type="ordered",
                    template_variables=tpl_vars)
            if 'errors' in res:
                print_err('Upload of dashboard {0} from file {1} failed.'
                          .format(payload["id"], f.name))

            report_warnings(res)
            report_errors(res)

            if format == 'pretty':
                print(pretty_json(res))
            else:
                print(json.dumps(res))

            if args.format == 'pretty':
                print("Uploaded file {0} (dashboard {1})".format(f.name, payload["id"]))

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

        # Required arguments
        payload = {
            "title": args.title,
            "widgets": widgets,
            "layout_type": "ordered"
        }
        # Optional arguments
        if(args.description):
            payload["description"] = args.description
        if(args.read_only):
            payload["is_read_only"] = args.read_only
        if(args.notify_list):
            payload["notify_list"] = args.notify_list
        if(args.template_variables):
            payload["template_variables"] = args.template_variables

        res = api.Dashboard.create(**payload)
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

        # Required arguments
        payload = {
            "title": args.title,
            "widgets": widgets,
            "layout_type": "ordered"
        }
        # Optional arguments
        if(args.description):
            payload["description"] = args.description
        if(args.read_only):
            payload["is_read_only"] = args.read_only
        if(args.notify_list):
            payload["notify_list"] = args.notify_list
        if(args.template_variables):
            payload["template_variables"] = args.template_variables

        res = api.Dashboard.update(
            args.dashboard_id, **payload)
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


def _json_string(str):
    try:
        return json.loads(str)
    except Exception:
        raise argparse.ArgumentTypeError('bad json parameter')
