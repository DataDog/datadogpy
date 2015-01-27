from datadog.dogshell.common import report_errors, report_warnings, find_localhost
from datadog import api


class MetricClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('metric', help="Post metrics.")
        verb_parsers = parser.add_subparsers(title='Verbs')

        post_parser = verb_parsers.add_parser('post', help="Post metrics")
        post_parser.add_argument('name', help="metric name")
        post_parser.add_argument('value', help="metric value (integer or decimal value)",
                                 type=float)
        post_parser.add_argument('--host', help="scopes your metric to a specific host",
                                 default=None)
        post_parser.add_argument('--device', help="scopes your metric to a specific device",
                                 default=None)
        post_parser.add_argument('--tags', help="comma-separated list of tags", default=None)
        post_parser.add_argument('--localhostname', help="same as --host=`hostname`"
                                 " (overrides --host)", action='store_true')
        post_parser.add_argument('--type', help="type of the metric - gauge(32bit float)"
                                 " or counter(64bit integer)", default=None)
        parser.set_defaults(func=cls._post)

    @classmethod
    def _post(cls, args):
        api._timeout = args.timeout
        if args.localhostname:
            host = find_localhost()
        else:
            host = args.host
        if args.tags:
            tags = sorted(set([t.strip() for t in
                               args.tags.split(',') if t]))
        else:
            tags = None
        res = api.Metric.send(
            metric=args.name, points=args.value, host=host,
            device=args.device, tags=tags, metric_type=args.type)
        report_warnings(res)
        report_errors(res)
