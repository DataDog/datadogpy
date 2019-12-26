# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import json

# 3p
from datadog.util.format import pretty_json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


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

        # Get Dashboards for Dashboard List parser (v2)
        get_dashboards_v2_parser = verb_parsers.add_parser(
            'show_dashboards_v2',
            help="Show a list of all dashboards for an existing dashboard list"
        )
        get_dashboards_v2_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to show dashboards from"
        )
        get_dashboards_v2_parser.set_defaults(func=cls._show_dashboards_v2)

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

        # Add Dashboards to Dashboard List parser (v2)
        add_dashboards_v2_parser = verb_parsers.add_parser(
            'add_dashboards_v2', help="Add dashboards to an existing dashboard list"
        )
        add_dashboards_v2_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to add dashboards to"
        )
        add_dashboards_v2_parser.add_argument(
            'dashboards',
            help='A JSON list of dashboard dicts, e.g. ' +
            '[{"type": "custom_timeboard", "id": "ewc-a4f-8ps"}, ' +
            '{"type": "custom_screenboard", "id": "kwj-3t3-d3m"}]'
        )
        add_dashboards_v2_parser.set_defaults(func=cls._add_dashboards_v2)

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

        # Update Dashboards of Dashboard List parser (v2)
        update_dashboards_v2_parser = verb_parsers.add_parser(
            'update_dashboards_v2', help="Update dashboards of an existing dashboard list"
        )
        update_dashboards_v2_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to update with dashboards"
        )
        update_dashboards_v2_parser.add_argument(
            'dashboards',
            help='A JSON list of dashboard dicts, e.g. ' +
            '[{"type": "custom_timeboard", "id": "ewc-a4f-8ps"}, ' +
            '{"type": "custom_screenboard", "id": "kwj-3t3-d3m"}]'
        )
        update_dashboards_v2_parser.set_defaults(func=cls._update_dashboards_v2)

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

        # Delete Dashboards from Dashboard List parser
        delete_dashboards_v2_parser = verb_parsers.add_parser(
            'delete_dashboards', help="Delete dashboards from an existing dashboard list"
        )
        delete_dashboards_v2_parser.add_argument(
            'dashboard_list_id', help="Dashboard list to delete dashboards from"
        )
        delete_dashboards_v2_parser.add_argument(
            'dashboards',
            help='A JSON list of dashboard dicts, e.g. ' +
            '[{"type": "custom_timeboard", "id": "ewc-a4f-8ps"}, ' +
            '{"type": "custom_screenboard", "id": "kwj-3t3-d3m"}]'
        )
        delete_dashboards_v2_parser.set_defaults(func=cls._delete_dashboards_v2)

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
    def _show_dashboards_v2(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id

        res = api.DashboardList.v2.get_items(dashboard_list_id)
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
    def _add_dashboards_v2(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id
        dashboards = json.loads(args.dashboards)

        res = api.DashboardList.v2.add_items(dashboard_list_id, dashboards=dashboards)
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
    def _update_dashboards_v2(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id
        dashboards = json.loads(args.dashboards)

        res = api.DashboardList.v2.update_items(dashboard_list_id, dashboards=dashboards)
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

    @classmethod
    def _delete_dashboards_v2(cls, args):
        api._timeout = args.timeout
        format = args.format
        dashboard_list_id = args.dashboard_list_id
        dashboards = json.loads(args.dashboards)

        res = api.DashboardList.v2.delete_items(dashboard_list_id, dashboards=dashboards)
        report_warnings(res)
        report_errors(res)

        if format == 'pretty':
            print(pretty_json(res))
        else:
            print(json.dumps(res))
