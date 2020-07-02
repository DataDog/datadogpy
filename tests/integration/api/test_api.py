# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# python
import datetime
import json
import mock
import os
import re
import time

import requests
import pytest

# datadog
from datadog import initialize

from .constants import MONITOR_REFERENCED_IN_SLO_MESSAGE

WAIT_TIME = 10


class TestDatadog:
    host_name = "test.host.integration"

    @pytest.fixture(autouse=True)  # TODO , scope="class"
    def cleanup_roles(self, dog):
        """Prepare Azure Integration."""
        self.cleanup_role_uuids = []

        yield

        # Ensure we cleanup any resources we created during tests
        # These should be removed during tests, but here as well in case of test failures
        for uuid in self.cleanup_role_uuids:
            dog.Roles.delete(uuid)

    def test_tags(self, dog, get_with_retry, freezer):
        with freezer:
            hostname = "test.tags.host" + str(int(time.time()))

        # post a metric to make sure the test host context exists
        dog.Metric.send(metric="test.tag.metric", points=1, host=hostname)
        # Wait for host to appear
        get_with_retry("Tag", hostname)

        # Ready to test
        dog.Tag.create(hostname, tags=["test_tag:1", "test_tag:2"], source="datadog")
        get_with_retry(
            "Tag",
            hostname,
            retry_condition=lambda r: "test_tag:1" not in r["tags"]
            or "test_tag:2" not in r["tags"],
            retry_limit=30,
            source="datadog",
        )

        # The response from `update` can be flaky, so let's test that it work by getting the tags
        dog.Tag.update(hostname, tags=["test_tag:3"], source="datadog")
        get_with_retry(
            "Tag",
            hostname,
            retry_condition=lambda r: r["tags"] != ["test_tag:3"],
            retry_limit=30,
            source="datadog",
        )

        all_tags = dog.Tag.get_all()
        assert "tags" in all_tags

        assert (
            dog.Tag.delete(hostname, source="datadog") is None
        )  # Expect no response body on success

    @pytest.mark.vcr(match_on=("method", "scheme", "host", "port", "path", "query", "body"))
    def test_events(self, dog, get_with_retry, freezer):
        with freezer:
            now_ts = int(time.time())
            before_ts = now_ts - datetime.timedelta(minutes=5).total_seconds()

        now_title = "end test title " + str(now_ts)
        now_message = "test message " + str(now_ts)

        before_title = "start test title " + str(before_ts)
        before_message = "test message " + str(before_ts)

        now_event = dog.Event.create(
            title=now_title, text=now_message, date_happened=now_ts
        )
        before_event = dog.Event.create(
            title=before_title, text=before_message, date_happened=before_ts
        )

        assert now_event["event"]["title"] == now_title
        assert now_event["event"]["text"] == now_message
        assert now_event["event"]["date_happened"] == now_ts
        assert before_event["event"]["title"] == before_title
        assert before_event["event"]["text"] == before_message
        assert before_event["event"]["date_happened"] == before_ts

        # The returned event doesn"t contain host information, we need to get it separately
        event_id = dog.Event.create(
            title="test host", text="test host", host=self.host_name
        )["event"]["id"]
        event = get_with_retry("Event", event_id)
        assert event["event"]["host"] == self.host_name

        event_id = dog.Event.create(
            title="test no hostname",
            text="test no hostname",
            attach_host_name=False,
            alert_type="success",
        )["event"]["id"]
        event = get_with_retry("Event", event_id)
        assert not event["event"]["host"]
        assert event["event"]["alert_type"] == "success"

        event = dog.Event.create(
            title="test tags", text="test tags", tags=["test_tag:1", "test_tag:2"]
        )
        assert "test_tag:1" in event["event"]["tags"]
        assert "test_tag:2" in event["event"]["tags"]

        event = dog.Event.create(
            title="test source",
            text="test source",
            source_type_name="vsphere",
            priority="low",
        )
        event_id = event["event"]["id"]
        now_ts = event["event"]["date_happened"]
        get_with_retry("Event", event_id)
        events = dog.Event.query(
            start=now_ts - 100, end=now_ts + 100, priority="low", sources="vsphere"
        )
        assert events["events"], "No events found in stream"
        assert event_id in [event["id"] for event in events["events"]]

    def test_comments(self, dog, get_with_retry, freezer, user_handle):
        with freezer:
            now_ts = int(time.time())

        message = "test message " + str(now_ts)

        comment = dog.Comment.create(handle=user_handle, message=message)
        comment_id = comment["comment"]["id"]
        assert comment["comment"]["message"] == message

        get_with_retry("Event", comment_id)
        comment = dog.Comment.update(
            comment_id, handle=user_handle, message=message + " updated"
        )
        assert comment["comment"]["message"] == message + " updated"
        reply = dog.Comment.create(
            handle=user_handle, message=message + " reply", related_event_id=comment_id
        )
        assert reply["comment"]["message"] == message + " reply"

    def test_timeboard(self, dog, get_with_retry):
        graph = {
            "title": "test metric graph",
            "definition": {
                "requests": [{"q": "testing.metric.1{host:blah.host.1}"}],
                "viz": "timeseries",
            },
        }

        timeboard = dog.Timeboard.create(
            title="api timeboard", description="my api timeboard", graphs=[graph]
        )
        assert "api timeboard" == timeboard["dash"]["title"]
        assert "my api timeboard" == timeboard["dash"]["description"]
        assert timeboard["dash"]["graphs"][0] == graph

        timeboard = get_with_retry("Timeboard", timeboard["dash"]["id"])
        assert "api timeboard" == timeboard["dash"]["title"]
        assert "my api timeboard" == timeboard["dash"]["description"]
        assert timeboard["dash"]["graphs"][0] == graph

        graph = {
            "title": "updated test metric graph",
            "definition": {
                "requests": [{"q": "testing.metric.1{host:blah.host.1}"}],
                "viz": "timeseries",
            },
        }

        timeboard = dog.Timeboard.update(
            timeboard["dash"]["id"],
            title="updated api timeboard",
            description="my updated api timeboard",
            graphs=[graph],
        )

        assert "updated api timeboard" == timeboard["dash"]["title"]
        assert "my updated api timeboard" == timeboard["dash"]["description"]
        assert timeboard["dash"]["graphs"][0] == graph

        # Query all dashboards and make sure it"s in there.
        timeboards = dog.Timeboard.get_all()["dashes"]
        ids = [str(timeboard["id"]) for timeboard in timeboards]
        assert str(timeboard["dash"]["id"]) in ids

        assert dog.Timeboard.delete(timeboard["dash"]["id"]) is None

    def test_search(self, dog):
        results = dog.Infrastructure.search(q="")
        assert len(results["results"]["hosts"]) > 0
        assert len(results["results"]["metrics"]) > 0

    def test_metrics_simple(self, dog, get_with_retry, freezer):
        with freezer:
            now_ts = int(time.time())

            metric_name_single = "test.metric_single." + str(now_ts)
            host_name = "test.host." + str(now_ts)

            def retry_condition(r):
                return not r["series"]

            # Send metrics with single and multi points, and with compression
            assert (
                dog.Metric.send(metric=metric_name_single, points=1, host=host_name)[
                    "status"
                ]
                == "ok"
            )

        metric_query_single = get_with_retry(
            "Metric",
            operation="query",
            retry_condition=retry_condition,
            retry_limit=60,
            start=now_ts - 600,
            end=now_ts + 600,
            query="{}{{host:{}}}".format(metric_name_single, host_name),
        )
        assert len(metric_query_single["series"]) == 1
        assert metric_query_single["series"][0]["metric"] == metric_name_single
        assert metric_query_single["series"][0]["scope"] == "host:{}".format(host_name)
        assert len(metric_query_single["series"][0]["pointlist"]) == 1
        assert metric_query_single["series"][0]["pointlist"][0][1] == 1

    def test_metrics_list(self, dog, get_with_retry, freezer):
        with freezer:
            now_ts = int(time.time())

        metric_name_list = "test.metric_list." + str(now_ts)
        host_name = "test.host." + str(now_ts)

        def retry_condition(r):
            return not r["series"]

        points = [(now_ts - 60, 1), (now_ts, 2)]
        assert (
            dog.Metric.send(metric=metric_name_list, points=points, host=host_name)[
                "status"
            ]
            == "ok"
        )
        metric_query_list = get_with_retry(
            "Metric",
            operation="query",
            retry_condition=retry_condition,
            retry_limit=60,
            start=now_ts - 600,
            end=now_ts + 600,
            query="{}{{host:{}}}".format(metric_name_list, host_name),
        )
        assert len(metric_query_list["series"]) == 1
        assert metric_query_list["series"][0]["metric"] == metric_name_list
        assert metric_query_list["series"][0]["scope"] == "host:{}".format(host_name)
        assert len(metric_query_list["series"][0]["pointlist"]) == 2
        assert metric_query_list["series"][0]["pointlist"][0][1] == 1
        assert metric_query_list["series"][0]["pointlist"][1][1] == 2

    def test_metrics_tuple(self, dog, get_with_retry, freezer):
        with freezer:
            now_ts = int(time.time())

        metric_name_tuple = "test.metric_tuple." + str(now_ts)
        host_name = "test.host." + str(now_ts)

        def retry_condition(r):
            return not r["series"]

        points = (now_ts - 60, 1)
        assert (
            dog.Metric.send(
                metric=metric_name_tuple,
                points=points,
                host=host_name,
                compress_payload=False,
            )["status"]
            == "ok"
        )
        metric_query_tuple = get_with_retry(
            "Metric",
            operation="query",
            retry_condition=retry_condition,
            retry_limit=60,
            start=now_ts - 600,
            end=now_ts + 600,
            query="{}{{host:{}}}".format(metric_name_tuple, host_name),
        )
        assert len(metric_query_tuple["series"]) == 1
        assert metric_query_tuple["series"][0]["metric"] == metric_name_tuple
        assert metric_query_tuple["series"][0]["scope"] == "host:{}".format(host_name)
        assert len(metric_query_tuple["series"][0]["pointlist"]) == 1
        assert metric_query_tuple["series"][0]["pointlist"][0][1] == 1

    def test_distribution_metrics(self, dog, freezer):
        with freezer:
            now_ts = int(time.time())

        metric_name = "test.distribution_metric." + str(now_ts)
        host_name = "test.host." + str(now_ts)

        # Submit a distribution metric
        assert dog.Distribution.send(
            distributions=[{
                'metric': metric_name,
                'points': [(now_ts - 60, [1.0])],
                'type': 'distribution',
                'host': host_name,
            }]
        )["status"] == "ok"

        # FIXME: Query and verify the test metric result. Currently, it takes
        # too long for a new distribution metric to become available for query.

    def test_graph_snapshot(self, dog, get_with_retry, freezer):
        metric_query = "system.load.1{*}"
        event_query = "*"
        with freezer:
            end = int(time.time())
            start = end - 60 * 60  # go back 1 hour

        # Test without an event query
        snap = dog.Graph.create(metric_query=metric_query, start=start, end=end)
        assert "event_query" not in snap
        assert snap["metric_query"] == metric_query
        snapshot_url = snap["snapshot_url"]

        # Test with an event query
        snap = dog.Graph.create(
            metric_query=metric_query, start=start, end=end, event_query=event_query
        )
        assert snap["metric_query"] == metric_query
        assert snap["event_query"] == event_query
        snapshot_url = snap["snapshot_url"]

        # Test with a graph def
        graph_def = {
            "viz": "toplist",
            "requests": [
                {
                    "q": "top(system.disk.free{*} by {device}, 10, 'mean', 'desc')",
                    "style": {"palette": "dog_classic"},
                    "conditional_formats": [
                        {"palette": "red", "comparator": ">", "value": 50000000000},
                        {"palette": "green", "comparator": ">", "value": 30000000000},
                    ],
                }
            ],
        }
        graph_def = json.dumps(graph_def, sort_keys=True)
        snap = dog.Graph.create(graph_def=graph_def, start=start, end=end)
        assert "metric_query" not in snap
        assert "event_query" not in snap
        assert snap["graph_def"] == graph_def
        snapshot_url = snap["snapshot_url"]

        # Test snapshot status endpoint
        get_with_retry(
            "Graph",
            snapshot_url,
            operation="status",
            retry_condition=lambda r: r["status_code"] != 200,
            retry_limit=20,
        )

    def test_screenboard(self, vcr_cassette, dog, get_with_retry):
        def _compare_screenboard(apiBoard, expectedBoard):
            compare_keys = ["board_title", "height", "width", "widgets"]
            for key in compare_keys:
                assert apiBoard[key] == expectedBoard[key]

        board = {
            "width": 1024,
            "height": 768,
            "board_title": "datadog test",
            "widgets": [
                {
                    "type": "event_stream",
                    "title": False,
                    "height": 57,
                    "width": 59,
                    "y": 18,
                    "x": 84,
                    "query": "tags:release",
                    "time": {"live_span": "1w"},
                },
                {
                    "type": "image",
                    "height": 20,
                    "width": 32,
                    "y": 7,
                    "x": 32,
                    "url": "http://path/to/image.jpg",
                },
            ],
        }

        updated_board = {
            "width": 1024,
            "height": 768,
            "board_title": "datadog test",
            "widgets": [
                {
                    "type": "image",
                    "height": 20,
                    "width": 32,
                    "y": 7,
                    "x": 32,
                    "url": "http://path/to/image.jpg",
                }
            ],
        }

        create_res = dog.Screenboard.create(**board)
        _compare_screenboard(board, create_res)

        get_res = get_with_retry("Screenboard", create_res["id"])
        _compare_screenboard(get_res, create_res)
        assert get_res["id"] == create_res["id"]

        get_all_res = dog.Screenboard.get_all()["screenboards"]
        created = [s for s in get_all_res if s["id"] == create_res["id"]]
        assert len(created) == 1

        update_res = dog.Screenboard.update(get_res["id"], **updated_board)
        _compare_screenboard(update_res, updated_board)
        assert get_res["id"] == update_res["id"]

        share_res = dog.Screenboard.share(get_res["id"])
        assert share_res["board_id"] == get_res["id"]
        public_url = share_res["public_url"]

        if vcr_cassette.record_mode != "none":
            time.sleep(WAIT_TIME)
        response = requests.get(public_url)
        assert response.status_code == 200

        dog.Screenboard.revoke(get_res["id"])
        if vcr_cassette.record_mode != "none":
            time.sleep(WAIT_TIME)
        response = requests.get(public_url)
        assert response.status_code == 404

        delete_res = dog.Screenboard.delete(update_res["id"])
        assert delete_res["id"] == update_res["id"]

    def test_monitor_crud(self, dog, get_with_retry, freezer):
        # Metric alerts
        query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"

        with freezer:
            options = {
                "silenced": {"*": int(time.time()) + 60 * 60},
                "notify_no_data": False,
            }
        monitor = dog.Monitor.create(type="metric alert", query=query, options=options)
        assert monitor["query"] == query
        assert monitor["options"]["notify_no_data"] == options["notify_no_data"]
        assert monitor["options"]["silenced"] == options["silenced"]

        monitor = get_with_retry("Monitor", monitor["id"])
        assert monitor["query"] == query
        assert monitor["options"]["notify_no_data"] == options["notify_no_data"]
        assert monitor["options"]["silenced"] == options["silenced"]

        query2 = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 200"
        monitor = dog.Monitor.update(monitor["id"], query=query2, options=options)
        assert monitor["query"] == query2
        assert monitor["options"]["notify_no_data"] == options["notify_no_data"]
        assert monitor["options"]["silenced"] == options["silenced"]

        name = "test_monitors"
        monitor = dog.Monitor.update(
            monitor["id"], query=query2, name=name, options={"notify_no_data": True}
        )
        assert monitor["name"] == name
        assert monitor["query"] == query2
        assert monitor["options"]["notify_no_data"] is True

        monitors = [m for m in dog.Monitor.get_all() if m["id"] == monitor["id"]]
        assert len(monitors) == 1

        assert dog.Monitor.delete(monitor["id"]) == {
            "deleted_monitor_id": monitor["id"]
        }

    def test_monitor_validate(self, dog, get_with_retry):
        monitor_type = "metric alert"
        valid_options = {"thresholds": {"critical": 200.0}}
        invalid_options = {"thresholds": {"critical": 90.0}}

        # Check with an invalid query.
        invalid_query = "THIS IS A BAD QUERY"
        res = dog.Monitor.validate(type=monitor_type, query=invalid_query, options=valid_options)
        assert res == {"errors": ["The value provided for parameter 'query' is invalid"]}

        # Check with a valid query, invalid options.
        valid_query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 200"
        res = dog.Monitor.validate(type=monitor_type, query=valid_query, options=invalid_options)
        assert res == {"errors": ["Alert threshold (90.0) does not match that used in the query (200.0)."]}

        # Check with a valid query, valid options.
        res = dog.Monitor.validate(type=monitor_type, query=valid_query, options=valid_options)
        assert res == {}

    def test_monitor_can_delete(self, dog, freezer):
        # Create a monitor.
        query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"
        with freezer:
            options = {
                "silenced": {"*": int(time.time()) + 60 * 60},
                "notify_no_data": False,
            }
        monitor = dog.Monitor.create(type="metric alert", query=query, options=options)

        # Check if you can delete the monitor.
        monitor_ids = [monitor["id"]]
        assert dog.Monitor.can_delete(monitor_ids=monitor_ids) == {
            "data": {"ok": monitor_ids},
            "errors": None,
        }

        # Create a monitor-based SLO.
        with freezer as dt:
            name = "test SLO {}".format(int(time.time()))

        thresholds = [{"timeframe": "7d", "target": 90}]
        slo = dog.ServiceLevelObjective.create(
            type="monitor",
            monitor_ids=monitor_ids,
            thresholds=thresholds,
            name=name,
        )["data"][0]

        # Check if you can delete the monitor.
        monitor_ids = [monitor["id"]]
        resp = dog.Monitor.can_delete(monitor_ids=monitor_ids)
        assert "errors" in resp
        assert str(monitor["id"]) in resp["errors"]
        assert len(resp["errors"][str(monitor["id"])])
        assert "is referenced in slos" in resp["errors"][str(monitor["id"])][0]

        # Delete the SLO.
        dog.ServiceLevelObjective.delete(slo["id"])

        # Check if you can delete the monitor.
        monitor_ids = [monitor["id"]]
        assert dog.Monitor.can_delete(monitor_ids=monitor_ids) == {
            "data": {"ok": monitor_ids},
            "errors": None,
        }

        # Delete the monitor to clean up the test.
        assert dog.Monitor.delete(monitor["id"]) == {
            "deleted_monitor_id": monitor["id"]
        }

    def test_monitor_can_delete_with_force(self, dog, freezer):
        # Create a monitor.
        query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"
        with freezer:
            options = {
                "silenced": {"*": int(time.time()) + 60 * 60},
                "notify_no_data": False,
            }
        monitor = dog.Monitor.create(type="metric alert", query=query, options=options)
        monitor_ids = [monitor["id"]]

        # Create a monitor-based SLO.
        with freezer:
            name = "test SLO {}".format(int(time.time()))
        thresholds = [{"timeframe": "7d", "target": 90}]
        slo = dog.ServiceLevelObjective.create(
            type="monitor",
            monitor_ids=monitor_ids,
            thresholds=thresholds,
            name=name,
        )["data"][0]

        # Check if you can delete the monitor with force option
        assert dog.Monitor.delete(monitor["id"], force=True) == {
            "deleted_monitor_id": monitor["id"]
        }

        # Delete the SLO.
        dog.ServiceLevelObjective.delete(slo["id"])

    def test_service_level_objective_crud(self, dog, freezer):
        numerator = "sum:my.custom.metric{type:good}.as_count()"
        denominator = "sum:my.custom.metric{*}.as_count()"
        query = {"numerator": numerator, "denominator": denominator}
        thresholds = [{"timeframe": "7d", "target": 90}]
        with freezer:
            name = "test SLO {}".format(int(time.time()))
        slo = dog.ServiceLevelObjective.create(
            type="metric",
            query=query,
            thresholds=thresholds,
            name=name,
            tags=["type:test"],
        )["data"][0]
        assert slo["name"] == name

        numerator2 = "sum:my.custom.metric{type:good,!type:ignored}.as_count()"
        denominator2 = "sum:my.custom.metric{!type:ignored}.as_count()"
        query = {"numerator": numerator2, "denominator": denominator2}
        slo = dog.ServiceLevelObjective.update(
            id=slo["id"],
            type="metric",
            query=query,
            thresholds=thresholds,
            name=name,
            tags=["type:test"],
        )["data"][0]
        assert slo["name"] == name
        slos = [
            s
            for s in dog.ServiceLevelObjective.get_all()["data"]
            if s["id"] == slo["id"]
        ]
        assert len(slos) == 1

        assert dog.ServiceLevelObjective.get(slo["id"])["data"]["id"] == slo["id"]
        dog.ServiceLevelObjective.delete(slo["id"])

    @pytest.mark.admin_needed
    def test_monitor_muting(self, dog, get_with_retry):
        query1 = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"
        query2 = "avg(last_1h):sum:system.net.bytes_rcvd{*} by {host} > 100"
        monitor1 = dog.Monitor.create(type="metric alert", query=query1)
        monitor2 = dog.Monitor.create(type="metric alert", query=query2)

        dt = dog.Monitor.mute_all()
        assert dt["active"] is True
        assert dt["scope"] == ["*"]

        assert dog.Monitor.unmute_all() is None  # No response expected

        monitor1 = dog.Monitor.mute(monitor1["id"])
        assert monitor1["options"]["silenced"] == {"*": None}

        monitor2 = dog.Monitor.mute(monitor2["id"], scope="host:foo")
        assert monitor2["options"]["silenced"] == {"host:foo": None}

        get_with_retry(
            "Monitor",
            monitor2["id"],
            retry_condition=lambda r: r["options"]["silenced"] != {"host:foo": None},
        )
        monitor2 = dog.Monitor.unmute(monitor2["id"], scope="host:foo")
        assert monitor2["options"]["silenced"] == {}

        dog.Monitor.delete(monitor1["id"])
        dog.Monitor.delete(monitor2["id"])

    def test_downtime(self, dog, get_with_retry, freezer):
        with freezer:
            start = int(time.time())
            end = start + 1000

        # Create downtime
        downtime = dog.Downtime.create(scope="test_tag:1", start=start, end=end)
        assert downtime["start"] == start
        assert downtime["end"] == end
        assert downtime["scope"] == ["test_tag:1"]
        assert downtime["disabled"] is False

        get_with_retry("Downtime", downtime["id"])

        # Update downtime
        message = "Doing some testing on staging."
        with freezer as dt:
            dt.tick()
            end = int(time.time()) + 60000

        downtime = dog.Downtime.update(
            downtime["id"], scope="test_tag:2", end=end, message=message
        )
        assert downtime["end"] == end
        assert downtime["message"] == message
        assert downtime["scope"] == ["test_tag:2"]
        assert downtime["disabled"] is False

        # Delete downtime
        assert dog.Downtime.delete(downtime["id"]) is None
        downtime = get_with_retry(
            "Downtime", downtime["id"], retry_condition=lambda r: r["disabled"] is False
        )

    def test_downtime_cancel_by_scope(self, dog, get_with_retry, freezer):
        scope_one = "test:integration_one"
        scope_two = "test:integration_two"
        with freezer:
            start = int(time.time())

        # Create downtime with scope_one
        end = start + 1000
        downtime_one = dog.Downtime.create(scope=scope_one, start=start, end=end)
        assert downtime_one["scope"] == [scope_one]
        assert downtime_one["disabled"] is False

        # Create downtime with scope_one
        with freezer as dt:
            dt.tick()
            end = int(time.time()) + 60000
        downtime_two = dog.Downtime.create(scope=scope_one, start=start, end=end)
        assert downtime_two["scope"] == [scope_one]
        assert downtime_two["disabled"] is False

        with freezer as dt:
            dt.tick()
            end = int(time.time()) + 120000
        downtime_three = dog.Downtime.create(scope=scope_two, start=start, end=end)
        assert downtime_three["scope"] == [scope_two]
        assert downtime_three["disabled"] is False

        downtimes_with_scope_one = [downtime_one, downtime_two]
        downtimes_with_scope_two = [downtime_three]

        # Cancel downtimes with scope `scope_one`
        dog.Downtime.cancel_downtime_by_scope(scope=scope_one)

        # Verify only the downtimes with scope `scope_one` were canceled
        for downtime in downtimes_with_scope_one:
            get_with_retry(
                "Downtime", downtime["id"], retry_condition=lambda r: r["disabled"] is False
            )
        for downtime in downtimes_with_scope_two:
            d = get_with_retry("Downtime", downtime["id"])
            assert d["disabled"] is False

        # Cancel downtimes with scope `scope_two`
        dog.Downtime.cancel_downtime_by_scope(scope=scope_two)

        # Verify downtimes with scope `scope_two` were canceled
        for downtime in downtimes_with_scope_two:
            get_with_retry(
                "Downtime", downtime["id"], retry_condition=lambda r: r["disabled"] is False
            )

    def test_service_check(self, dog):
        assert dog.ServiceCheck.check(
            check="check_pg",
            host_name="host0",
            status=1,
            message="PG is WARNING",
            tags=["db:prod_data"],
        ) == {"status": "ok"}

    def test_host_muting(self, dog, get_with_retry, freezer):
        with freezer:
            end = int(time.time()) + 60 * 60
        hostname = "my.test.host" + str(end)
        message = "Muting this host for a test."

        # post a metric to make sure the test host context exists
        dog.Metric.send(metric="test.muting.host", points=1, host=hostname)
        # Wait for host to appear
        get_with_retry("Tag", hostname)

        # Mute a host
        mute = dog.Host.mute(hostname, end=end, message=message)
        assert mute["hostname"] == hostname
        assert mute["action"] == "Muted"
        assert mute["message"] == message
        assert mute["end"] == end

        # We shouldn"t be able to mute a host that"s already muted, unless we include
        # the override param.
        end2 = end + 60 * 15
        get_with_retry(
            "Host",
            hostname,
            operation="mute",
            retry_condition=lambda r: "errors" not in r,
            end=end2,
        )
        mute = dog.Host.mute(hostname, end=end2, override=True)
        assert mute["hostname"] == hostname
        assert mute["action"] == "Muted"
        assert mute["end"] == end2

        unmute = dog.Host.unmute(hostname)
        assert unmute["hostname"] == hostname
        assert unmute["action"] == "Unmuted"

    def test_get_all_embeds(self, dog):
        all_embeds = dog.Embed.get_all()
        # Check all embeds is a valid response
        assert "embedded_graphs" in all_embeds

    def test_embed_crud(self, dog, get_with_retry):
        # Initialize a graph definition
        graph_def = {
            "viz": "toplist",
            "requests": [
                {
                    "q": "top(system.disk.free{$var} by {device}, 10, 'mean', 'desc')",
                    "style": {"palette": "dog_classic"},
                    "conditional_formats": [
                        {"palette": "red", "comparator": ">", "value": 50000000000},
                        {"palette": "green", "comparator": ">", "value": 30000000000},
                    ],
                }
            ],
        }
        timeframe = "1_hour"
        size = "medium"
        legend = "no"
        title = "Custom titles!"
        # Dump the dictionary to a JSON string and make an API call
        graph_json = json.dumps(graph_def, sort_keys=True)
        embed = dog.Embed.create(
            graph_json=graph_json,
            timeframe=timeframe,
            size=size,
            legend=legend,
            title=title,
        )
        # Check various embed attributes
        assert "embed_id" in embed
        assert embed["revoked"] is False
        assert len(embed["template_variables"]) == 1
        assert embed["template_variables"][0] == "var"
        assert "html" in embed
        assert embed["graph_title"] == title

        var = "asdfasdfasdf"
        response_graph = get_with_retry("Embed", embed["embed_id"], var=var)
        # Check the graph has the same embed_id and the template_var is added to the url
        assert "embed_id" in response_graph
        assert response_graph["embed_id"] == embed["embed_id"]
        assert len(response_graph["html"]) > len(embed["html"])
        assert var in response_graph["html"]

        assert "success" in dog.Embed.enable(embed["embed_id"])

        assert "success" in dog.Embed.revoke(embed["embed_id"])

    @pytest.mark.admin_needed
    def test_user_crud(self, dog, get_with_retry, freezer):
        with freezer:
            now = int(time.time())
        handle = "user{}@test.com".format(now)
        name = "Test User"
        alternate_name = "Test User Alt"

        # test create user
        user = dog.User.create(handle=handle, name=name, access_role="ro")
        assert "user" in user
        assert user["user"]["handle"] == handle
        assert user["user"]["name"] == name
        assert user["user"]["disabled"] is False
        assert user["user"]["access_role"] == "ro"

        # test get user
        user = get_with_retry("User", handle)
        assert "user" in user
        assert user["user"]["handle"] == handle
        assert user["user"]["name"] == name

        # test update user
        user = dog.User.update(handle, name=alternate_name, access_role="st")
        assert user["user"]["handle"] == handle
        assert user["user"]["name"] == alternate_name
        assert user["user"]["disabled"] is False
        assert user["user"]["access_role"] == "st"

        # test disable user
        dog.User.delete(handle)
        u = dog.User.get(handle)
        assert "user" in u
        assert u["user"]["disabled"] is True

        # test get all users
        u = dog.User.get_all()
        assert "users" in u
        assert len(u["users"]) >= 1

    @pytest.mark.admin_needed
    def test_roles_crud(self, dog):
        role_name = "test_role"

        data = {
                "type": "roles",
                "attributes": {
                    "name": role_name
                }
            }

        # test create role
        role = dog.Roles.create(data=data)
        self.cleanup_role_uuids.append(role["data"]["id"])
        assert "roles" in role["data"]["type"]
        assert role["data"]["id"] is not None
        assert role["data"]["attributes"]["name"] == role_name

        role_uuid = role["data"]["id"]

        # test update role
        new_role_name = "test_role_2"
        data = {
                "type": "roles",
                "attributes": {
                    "name": new_role_name,
                    "id": role_uuid,
                }
            }

        role = dog.Roles.update(role_uuid, data=data)
        assert "roles" in role["data"]["type"]
        assert role["data"]["id"] is not None
        assert role["data"]["attributes"]["name"] == new_role_name

        # test assign permission

        permissions = dog.Permissions.get_all()
        assert "permissions" in permissions["data"][0]["type"]
        assert len(permissions["data"]) > 0

        permission_uuid = permissions["data"][0]["id"]
        data = {
                    "type": "permissions",
                    "id": permission_uuid
                }

        role = dog.Roles.assign_permission(role_uuid, data=data)
        assert "permissions" in role["data"][0]["type"]

        # test unassign permission
        data = {
            "type": "permissions",
            "id": permission_uuid
        }

        role = dog.Roles.unassign_permission(role_uuid, data=data)
        assert "permissions" in role["data"][0]["type"]
        assert len(permissions["data"]) > 0


        # test delete role
        dog.Roles.delete(role_uuid)

        # check if new role is deleted successfully
        res = dog.Roles.get(role_uuid)
        assert "errors" in res

    @mock.patch('datadog.api._return_raw_response', True)
    def test_user_agent(self, dog):
        _, resp = dog.api_client.APIClient.submit('GET', 'validate')
        assert re.match(r'^datadogpy\/[^\s]+ \(python [^\s]+; os [^\s]+; arch [^\s]+\)$', resp.request.headers['User-Agent'])
