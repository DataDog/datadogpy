# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Security Monitoring client - dogshell implementation.
"""
from __future__ import print_function

import json
import sys
from functools import wraps

from datadog.dogshell.common import report_errors, report_warnings, print_err
from datadog.api.security_monitoring_rules import SecurityMonitoringRule
from datadog.api.security_monitoring_signals import SecurityMonitoringSignal
from datadog.util.format import pretty_json
from datadog import api


def api_cmd(f):
    """
    Decorator for security monitoring commands.
    """
    @wraps(f)
    def wrapper(args):
        """
        A decorator that reports errors and warnings.
        """
        api._timeout = args.timeout
        format = args.format
        try:
            res = f(args)
            if res is None:
                return 0
            if report_errors(res) or report_warnings(res):
                return 1
            if format == "pretty":
                print(pretty_json(res))
            else:
                print(json.dumps(res))
            return 0
        except Exception as e:
            print_err("ERROR: {}".format(str(e)))
            return 1
    return wrapper


class SecurityMonitoringClient(object):
    """
    SecurityMonitoring client implementing the dogshell interface.
    """

    @classmethod
    def setup_parser(cls, subparsers):
        """
        Set up the command line parser for security monitoring commands.
        """
        parser = subparsers.add_parser(
            "security-monitoring", help="Manage security monitoring rules and signals"
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=None,
            help="Timeout in seconds",
        )

        sub_parsers = parser.add_subparsers(title="Commands", dest="sub_command")
        sub_parsers.required = True

        # Rules commands
        rule_parser = sub_parsers.add_parser("rules", help="Manage security monitoring rules")
        rule_sub_parsers = rule_parser.add_subparsers(title="Commands", dest="rule_command")
        rule_sub_parsers.required = True

        # Rules list
        rule_list_parser = rule_sub_parsers.add_parser("list", help="List all security monitoring rules")
        rule_list_parser.add_argument(
            "--page-size", dest="page_size", type=int, help="Size for a given page. The maximum allowed value is 100"
        )
        rule_list_parser.add_argument(
            "--page-number", dest="page_number", help="Specific page number to return"
        )
        rule_list_parser.set_defaults(func=cls._show_all_rules)

        # Rules get
        rule_get_parser = rule_sub_parsers.add_parser("get", help="Get a security monitoring rule")
        rule_get_parser.add_argument("rule_id", help="Rule ID")
        rule_get_parser.set_defaults(func=cls._show_rule)

        # Rules create
        rule_create_parser = rule_sub_parsers.add_parser("create", help="Create a security monitoring rule")
        rule_create_parser.add_argument(
            "--file", "-f", dest="file", required=True, help="JSON file with rule definition"
        )
        rule_create_parser.set_defaults(func=cls._create_rule)

        # Rules update
        rule_update_parser = rule_sub_parsers.add_parser("update", help="Update a security monitoring rule")
        rule_update_parser.add_argument("rule_id", help="Rule ID")
        rule_update_parser.add_argument(
            "--file", "-f", dest="file", required=True, help="JSON file with rule definition"
        )
        rule_update_parser.set_defaults(func=cls._update_rule)

        # Rules delete
        rule_delete_parser = rule_sub_parsers.add_parser("delete", help="Delete a security monitoring rule")
        rule_delete_parser.add_argument("rule_id", help="Rule ID")
        rule_delete_parser.set_defaults(func=cls._delete_rule)

        # Signals commands
        signal_parser = sub_parsers.add_parser("signals", help="Manage security monitoring signals")
        signal_sub_parsers = signal_parser.add_subparsers(title="Commands", dest="signal_command")
        signal_sub_parsers.required = True

        # Signals list
        signal_list_parser = signal_sub_parsers.add_parser("list", help="List security monitoring signals")
        signal_list_parser.add_argument(
            "--query", dest="query", help="Query to filter signals"
        )
        signal_list_parser.add_argument(
            "--from", dest="from_time", help="From timestamp (e.g., 'now-1h', timestamp)"
        )
        signal_list_parser.add_argument(
            "--to", dest="to_time", help="To timestamp (e.g., 'now', timestamp)"
        )
        signal_list_parser.add_argument(
            "--sort", dest="sort", help="Sort order (e.g., '-timestamp')"
        )
        signal_list_parser.add_argument(
            "--page-size", dest="page_size", type=int, help="Number of results per page"
        )
        signal_list_parser.add_argument(
            "--page-cursor", dest="page_cursor", help="Cursor for pagination"
        )
        signal_list_parser.set_defaults(func=cls._list_signals)

        # Signals get
        signal_get_parser = signal_sub_parsers.add_parser("get", help="Get a security monitoring signal")
        signal_get_parser.add_argument("signal_id", help="Signal ID")
        signal_get_parser.set_defaults(func=cls._get_signal)

        # Signals change triage state
        signal_triage_parser = signal_sub_parsers.add_parser(
            "triage", help="Change triage state of security signals"
        )
        signal_triage_parser.add_argument(
            "signal_id", help="Signal ID"
        )
        signal_triage_parser.add_argument(
            "--state", dest="state", required=True, choices=["open", "archived", "under_review"],
            help="New triage state (open, archived, under_review)"
        )
        signal_triage_parser.set_defaults(func=cls._change_triage_state)

    @classmethod
    def _show_rule(cls, args):
        @api_cmd
        def show_rule_cmd(args):
            return SecurityMonitoringRule.get(args.rule_id)
        return show_rule_cmd(args)

    @classmethod
    def _show_all_rules(cls, args):
        @api_cmd
        def show_all_rules_cmd(args):
            params = {}

            if args.page_size:
                params["page[size]"] = args.page_size
            if args.page_number:
                params["page[number]"] = args.page_number

            return SecurityMonitoringRule.get_all(**params)
        return show_all_rules_cmd(args)

    @classmethod
    def _create_rule(cls, args):
        """
        Create a security monitoring rule.
        """
        @api_cmd
        def create_rule_cmd(args):
            try:
                with open(args.file, "r") as f:
                    rule_data = json.load(f)
            except Exception as e:
                print("Error reading rule file: {}".format(str(e)), file=sys.stderr)
                return {}

            return SecurityMonitoringRule.create(**rule_data)
        return create_rule_cmd(args)

    @classmethod
    def _update_rule(cls, args):
        """
        Update a security monitoring rule.
        """
        @api_cmd
        def update_rule_cmd(args):
            try:
                with open(args.file, "r") as f:
                    rule_data = json.load(f)
            except Exception as e:
                print("Error reading rule file: {}".format(str(e)), file=sys.stderr)
                return {}

            return SecurityMonitoringRule.update(args.rule_id, **rule_data)
        return update_rule_cmd(args)

    @classmethod
    def _delete_rule(cls, args):
        """
        Delete a security monitoring rule.
        """
        @api_cmd
        def delete_rule_cmd(args):
            return SecurityMonitoringRule.delete(args.rule_id)
        return delete_rule_cmd(args)

    @classmethod
    def _list_signals(cls, args):
        """
        List security monitoring signals.
        """
        @api_cmd
        def list_signals_cmd(args):
            params = {}

            if args.query:
                params["filter[query]"] = args.query
            if args.from_time:
                params["filter[from]"] = args.from_time
            if args.to_time:
                params["filter[to]"] = args.to_time
            if args.sort:
                params["sort"] = args.sort
            if args.page_size:
                params["page[size]"] = args.page_size
            if args.page_cursor:
                params["page[cursor]"] = args.page_cursor

            return SecurityMonitoringSignal.get_all(**params)
        return list_signals_cmd(args)

    @classmethod
    def _get_signal(cls, args):
        """
        Get a security monitoring signal.
        """
        @api_cmd
        def get_signal_cmd(args):
            return SecurityMonitoringSignal.get(args.signal_id)
        return get_signal_cmd(args)

    @classmethod
    def _change_triage_state(cls, args):
        """
        Change triage state of security signals.
        """
        @api_cmd
        def change_triage_state_cmd(args):
            return SecurityMonitoringSignal.change_triage_state(args.signal_id, args.state)
        return change_triage_state_cmd(args)
