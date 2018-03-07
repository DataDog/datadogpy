# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings
from datadog.util.compat import json


class DashboardListClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser(
            'dashboard_list', help="Create, edit, and delete dashboard lists"
        )
        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        # Create Dashboard List parser
        post_parser = verb_parsers.add_parser('post', help="Create a dashboard list")
        post_parser.add_argument('name', help="Name for the dashboard list")
        post_parser.set_defaults(func=cls._post)

        # Update Dashboard List parser
        update_parser = verb_parsers.add_parser('update', help="Update existing dashboard list")
        update_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to replace with the new definition"
        )
        update_parser.add_argument('name', help="Name for the dashboard list")
        update_parser.set_defaults(func=cls._update)

        # Show Dashboard List parser
        show_parser = verb_parsers.add_parser('show', help="Show a dashboard list definition")
        show_parser.add_argument('dashboard_list_id', help="Dashboard list to show")
        show_parser.set_defaults(func=cls._show)

        # Show All Dashboard Lists parser
        show_all_parser = verb_parsers.add_parser(
            'show_all', help="Show a list of all dashboard lists"
        )
        show_all_parser.set_defaults(func=cls._show_all)

        # Delete Dashboard List parser
        delete_parser = verb_parsers.add_parser('delete', help="Delete existing dashboard list")
        delete_parser.add_argument('dashboard_list_id', help="Dashboard list to delete")
        delete_parser.set_defaults(func=cls._delete)

        # Get Dashboards for Dashboard List parser
        get_dashboards_parser = verb_parsers.add_parser(
            'show_dashboards', help="Show a list of all dashboards for an existing dashboard list"
        )
        get_dashboards_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to show dashboards from"
        )
        get_dashboards_parser.set_defaults(func=cls._show_dashboards)

        # Add Dashboards to Dashboard List parser
        add_dashboards_parser = verb_parsers.add_parser(
            'add_dashboards', help="Add dashboards to an existing dashboard list"
        )
        add_dashboards_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to add dashboards to"
        )
        add_dashboards_parser.add_argument(
            'dashboards',
            help='A JSON list of dashboard dicts, e.g. ' +
                 '[{"type": "custom_timeboard", "id": 1234}, ' +
                 '{"type": "custom_screenboard", "id": 123}]'
        )
        add_dashboards_parser.set_defaults(func=cls._add_dashboards)

        # Update Dashboards of Dashboard List parser
        update_dashboards_parser = verb_parsers.add_parser(
            'update_dashboards', help="Update dashboards of an existing dashboard list"
        )
        update_dashboards_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to update with dashboards"
        )
        update_dashboards_parser.add_argument(
            'dashboards',
            help='A JSON list of dashboard dicts, e.g. ' +
                 '[{"type": "custom_timeboard", "id": 1234}, ' +
                 '{"type": "custom_screenboard", "id": 123}]'
        )
        update_dashboards_parser.set_defaults(func=cls._update_dashboards)

        # Delete Dashboards from Dashboard List parser
        delete_dashboards_parser = verb_parsers.add_parser(
            'delete_dashboards', help="Delete dashboards from an existing dashboard list"
        )
        delete_dashboards_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to delete dashboards from"
        )
        delete_dashboards_parser.add_argument(
            'dashboards',
            help='A JSON list of dashboard dicts, e.g. ' +
                 '[{"type": "custom_timeboard", "id": 1234}, ' +
                 '{"type": "custom_screenboard", "id": 123}]'
        )
        delete_dashboards_parser.set_defaults(func=cls._delete_dashboards)

    @classmethod
    def _post(cls, args):
        api._timeout = args.timeout
        format = args.format
        name = args.name

        res = api.DashboardList.create(name=name)
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
        dashboard_list_id = args.dashboard_list_id
        name = args.name

        res = api.DashboardList.update(dashboard_list_id, name=name)
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
        dashboard_list_id = args.dashboard_list_id

        res = api.DashboardList.get(dashboard_list_id)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show_all(cls, args):
        api._timeout = args.timeout
        format = args.format

        res = api.DashboardList.get_all()
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _delete(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id

        res = api.DashboardList.delete(dashboard_list_id)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _show_dashboards(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id

        res = api.DashboardList.get_items(dashboard_list_id)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _add_dashboards(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id
        dashboards = json.loads(args.dashboards)

        res = api.DashboardList.add_items(dashboard_list_id, dashboards=dashboards)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _update_dashboards(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id
        dashboards = json.loads(args.dashboards)

        res = api.DashboardList.update_items(dashboard_list_id, dashboards=dashboards)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))

    @classmethod
    def _delete_dashboards(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id
        dashboards = json.loads(args.dashboards)

        res = api.DashboardList.delete_items(dashboard_list_id, dashboards=dashboards)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))
