# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import datetime
import time
import re
import sys
import json

# datadog
from datadog import api
from datadog.dogshell.common import report_errors, report_warnings


time_pat = re.compile(r"(?P<delta>[0-9]*\.?[0-9]+)(?P<unit>[mhd])")


def prettyprint_event(event):
    title = event["title"] or ""
    text = event.get("text", "") or ""
    handle = event.get("handle", "") or ""
    date = event["date_happened"]
    dt = datetime.datetime.fromtimestamp(date)
    link = event["url"]

    # Print
    print((title + " " + text + " " + " (" + handle + ")").strip())
    print(dt.isoformat(" ") + " | " + link)


def print_event(event):
    prettyprint_event(event)


def prettyprint_event_details(event):
    prettyprint_event(event)


def print_event_details(event):
    prettyprint_event(event)


def parse_time(timestring):
    now = time.mktime(datetime.datetime.now().timetuple())
    if timestring is None:
        t = now
    else:
        try:
            t = int(timestring)
        except Exception:
            match = time_pat.match(timestring)
            if match is None:
                raise Exception
            delta = float(match.group("delta"))
            unit = match.group("unit")
            if unit == "m":
                delta = delta * 60
            if unit == "h":
                delta = delta * 60 * 60
            if unit == "d":
                delta = delta * 60 * 60 * 24
            t = now - int(delta)
    return int(t)


class EventClient(object):
    @classmethod
    def setup_parser(cls, subparsers):
        parser = subparsers.add_parser("event", help="Post events, get event details," " and view the event stream.")
        verb_parsers = parser.add_subparsers(title="Verbs", dest="verb")
        verb_parsers.required = True

        post_parser = verb_parsers.add_parser("post", help="Post events.")
        post_parser.add_argument("title", help="event title")
        post_parser.add_argument(
            "--date_happened",
            type=int,
            help="POSIX timestamp" " when the event occurred. if unset defaults to the current time.",
        )
        post_parser.add_argument("--handle", help="user to post as. if unset, submits " "as the generic API user.")
        post_parser.add_argument("--priority", help='"normal" or "low". defaults to "normal"', default="normal")
        post_parser.add_argument(
            "--related_event_id", help="event to post as a child of." " if unset, posts a top-level event"
        )
        post_parser.add_argument("--tags", help="comma separated list of tags")
        post_parser.add_argument("--host", help="related host (default to the local host name)", default="")
        post_parser.add_argument(
            "--no_host", help="no host is associated with the event" " (overrides --host))", action="store_true"
        )
        post_parser.add_argument("--device", help="related device (e.g. eth0, /dev/sda1)")
        post_parser.add_argument("--aggregation_key", help="key to aggregate the event with")
        post_parser.add_argument("--type", help="type of event, e.g. nagios, jenkins, etc.")
        post_parser.add_argument("--alert_type", help='"error", "warning", "info" or "success". defaults to "info"')
        post_parser.add_argument("message", help="event message body. " "if unset, reads from stdin.", nargs="?")
        post_parser.set_defaults(func=cls._post)

        show_parser = verb_parsers.add_parser("show", help="Show event details.")
        show_parser.add_argument("event_id", help="event to show")
        show_parser.set_defaults(func=cls._show)

        stream_parser = verb_parsers.add_parser(
            "stream",
            help="Retrieve events from the Event Stream",
            description="Stream start and end times can be specified as either a POSIX"
            " timestamp (e.g. the output of `date +%s`) or as a period of"
            " time in the past (e.g. '5m', '6h', '3d').",
        )
        stream_parser.add_argument("start", help="start date for the stream request")
        stream_parser.add_argument("end", help="end date for the stream request " "(defaults to 'now')", nargs="?")
        stream_parser.add_argument("--priority", help="filter by priority." " 'normal' or 'low'. defaults to 'normal'")
        stream_parser.add_argument("--sources", help="comma separated list of sources to filter by")
        stream_parser.add_argument("--tags", help="comma separated list of tags to filter by")
        stream_parser.set_defaults(func=cls._stream)

    @classmethod
    def _post(cls, args):
        """
        Post an event.
        """
        api._timeout = args.timeout
        format = args.format
        message = args.message
        if message is None:
            message = sys.stdin.read()
        if args.tags is not None:
            tags = [t.strip() for t in args.tags.split(",")]
        else:
            tags = None

        host = None if args.no_host else args.host

        # Submit event
        res = api.Event.create(
            title=args.title,
            text=message,
            date_happened=args.date_happened,
            handle=args.handle,
            priority=args.priority,
            related_event_id=args.related_event_id,
            tags=tags,
            host=host,
            device=args.device,
            aggregation_key=args.aggregation_key,
            source_type_name=args.type,
            alert_type=args.alert_type,
        )

        # Report
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            prettyprint_event(res["event"])
        elif format == "raw":
            print(json.dumps(res))
        else:
            print_event(res["event"])

    @classmethod
    def _show(cls, args):
        api._timeout = args.timeout
        format = args.format
        res = api.Event.get(args.event_id)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            prettyprint_event_details(res["event"])
        elif format == "raw":
            print(json.dumps(res))
        else:
            print_event_details(res["event"])

    @classmethod
    def _stream(cls, args):
        api._timeout = args.timeout
        format = args.format
        if args.sources is not None:
            sources = [s.strip() for s in args.sources.split(",")]
        else:
            sources = None
        if args.tags is not None:
            tags = [t.strip() for t in args.tags.split(",")]
        else:
            tags = None
        start = parse_time(args.start)
        end = parse_time(args.end)
        # res = api.Event.query(start=start, end=end)
        # TODO FIXME
        res = api.Event.query(start=start, end=end, priority=args.priority, sources=sources, tags=tags)
        report_warnings(res)
        report_errors(res)
        if format == "pretty":
            for event in res["events"]:
                prettyprint_event(event)
                print()
        elif format == "raw":
            print(json.dumps(res))
        else:
            for event in res["events"]:
                print_event(event)
                print()
