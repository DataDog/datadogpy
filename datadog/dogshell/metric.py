# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import argparse
from collections import defaultdict

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


class MetricClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        # type: (argparse._SubParsersAction[argparse.ArgumentParser]) -> None
        parser = subparsers.add_parser("metric", help="Post metrics.")
        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser("post", help="Post metrics")
        post_parser.add_argument("name", help="metric name")
        post_parser.add_argument("value", help="metric value (integer or decimal value)", type=float)
        post_parser.add_argument(
            "--host", help="scopes your metric to a specific host " "(default to the local host name)", default=""
        )
        post_parser.add_argument(
            "--no_host", help="no host is associated with the metric" " (overrides --host))", action="store_true"
        )
        post_parser.add_argument("--device", help="scopes your metric to a specific device", default=None)
        post_parser.add_argument("--tags", help="comma-separated list of tags", default=None)
        post_parser.add_argument(
            "--localhostname",
            help="deprecated, used to force `--host`"
            " to the local hostname "
            "(now default when no `--host` is specified)",
            action="store_true",
        )
        post_parser.add_argument(
            "--type",
            help="type of the metric: gauge, count or rate (`counter` is deprecated and is sent as `count`)",
            # "" is accepted by the API too, and `counter` is kept for existing scripts
            choices=["gauge", "count", "rate", "", "counter"],
            metavar="{gauge,count,rate}",
            default=None,
        )
        parser.set_defaults(func=cls._post)

    @classmethod
    def _post(cls, args):
        # type: (argparse.Namespace) -> None
        """
        Post a metric.
        """
        # Format parameters
        api._timeout = args.timeout

        host = None if args.no_host else args.host

        if args.tags:
            tags = sorted({t.strip() for t in args.tags.split(",") if t})
        else:
            tags = None

        # `counter` is a legacy type, send it as the documented `count` type.
        metric_type = "count" if args.type == "counter" else args.type

        # Submit metric
        res = api.Metric.send(
            metric=args.name, points=args.value, host=host, device=args.device, tags=tags, metric_type=metric_type
        )

        # Report
        res = defaultdict(list, res)

        if args.localhostname:
            # Warn about`--localhostname` command line flag deprecation
            res["warnings"].append(
                u"`--localhostname` command line flag is deprecated, made default when no `--host` "
                u"is specified. See the `--host` option for more information."
            )
        if args.type == "counter":
            # Warn about `--type counter` deprecation
            res["warnings"].append(
                u"`--type counter` is deprecated and was sent as `count`. Use `--type count` instead."
            )
        report_warnings(res)
        report_errors(res)
