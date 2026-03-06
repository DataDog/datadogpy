# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


# TODO IS there a test ?
class SearchClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("search", help="search datadog")
        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        query_parser = verb_parsers.add_parser("query", help="Search datadog.")
        query_parser.add_argument("query", help="optionally faceted search query")
        query_parser.set_defaults(func=cls._query)

    @classmethod
    def _query(cls, args):
        api._timeout = args.timeout
        res = api.Infrastructure.search(q=args.query)
        report_warnings(res)
        report_errors(res)
        print(json.dumps(res))
