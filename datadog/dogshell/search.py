# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings
from datadog.util.compat import json


# TODO IS there a test ?
class SearchClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('search', help="search datadog")
        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        query_parser = verb_parsers.add_parser('query', help="Search datadog.")
        query_parser.add_argument('query', help="optionally faceted search query")
        query_parser.set_defaults(func=cls._query)

    @classmethod
    def _query(cls, args):
        api._timeout = args.timeout
        res = api.Infrastructure.search(q=args.query)
        report_warnings(res)
        report_errors(res)
        if format == 'pretty':
            for facet, results in list(res['results'].items()):
                for idx, result in enumerate(results):
                    if idx == 0:
                        print('\n')
                        print("%s\t%s" % (facet, result))
                    else:
                        print("%s\t%s" % (' ' * len(facet), result))
        elif format == 'raw':
            print(json.dumps(res))
        else:
            for facet, results in list(res['results'].items()):
                for result in results:
                    print("%s\t%s" % (facet, result))
