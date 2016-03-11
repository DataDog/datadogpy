# stdlib
from collections import defaultdict

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


class MetricClient(object):

    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser('metric', help="Post metrics.")
        verb_parsers = parser.add_subparsers(title='Verbs', dest='verb')
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser('post', help="Post metrics")
        post_parser.add_argument('name', help="metric name")
        post_parser.add_argument('value', help="metric value (integer or decimal value)",
                                 type=float)
        post_parser.add_argument('--host', help="scopes your metric to a specific host "
                                 "(default to the local host name)",
                                 default="")
        post_parser.add_argument('--no_host', help="no host is associated with the metric"
                                 " (overrides --host))", action='store_true')
        post_parser.add_argument('--device', help="scopes your metric to a specific device",
                                 default=None)
        post_parser.add_argument('--tags', help="comma-separated list of tags", default=None)
        post_parser.add_argument('--localhostname', help="deprecated, used to force `--host`"
                                 " to the local hostname "
                                 "(now default when no `--host` is specified)", action='store_true')
        post_parser.add_argument('--type', help="type of the metric - gauge(32bit float)"
                                 " or counter(64bit integer)", default=None)
        parser.set_defaults(func=cls._post)

    @classmethod
    def _post(cls, args):
        """
        Post a metric.
        """
        # Format parameters
        api._timeout = args.timeout

        host = None if args.no_host else args.host

        if args.tags:
            tags = sorted(set([t.strip() for t in
                               args.tags.split(',') if t]))
        else:
            tags = None

        # Submit metric
        res = api.Metric.send(
            metric=args.name, points=args.value, host=host,
            device=args.device, tags=tags, metric_type=args.type)

        # Report
        res = defaultdict(list, res)

        if args.localhostname:
            # Warn about`--localhostname` command line flag deprecation
            res['warnings'].append(
                u"`--localhostname` command line flag is deprecated, made default when no `--host` "
                u"is specified. See the `--host` option for more information."
            )
        report_warnings(res)
        report_errors(res)
