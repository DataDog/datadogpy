# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from hashlib import md5
import json
import os
import random
import re
import subprocess
import time
import tempfile
import sys

import pytest
import requests

from datadog.util.compat import is_p3k, ConfigParser
from ..api.constants import API_KEY, APP_KEY, MONITOR_REFERENCED_IN_SLO_MESSAGE

WAIT_TIME = 11


def get_temp_file():
    """Return a (fn, fp) pair"""
    if is_p3k():
        fn = "/tmp/{0}-{1}".format(time.time(), random.random())
        return (fn, open(fn, "w+"))
    else:
        tf = tempfile.NamedTemporaryFile()
        return (tf.name, tf)


@pytest.fixture  # (scope="module")
def dogshell_config():
    config = ConfigParser()
    config.add_section("Connection")
    config.set("Connection", "apikey", API_KEY)
    config.set("Connection", "appkey", APP_KEY)
    config.set("Connection", "api_host", os.environ.get("DATADOG_HOST", "https://api.datadoghq.com"))
    return config


@pytest.fixture  # (scope="module")
def config_file(tmp_path, dogshell_config):
    """Generate a config file for the dog shell."""
    filename = tmp_path / ".test.dog.ini"
    with filename.open("w") as fp:
        dogshell_config.write(fp)
    return str(filename)


@pytest.fixture
def dogshell(capsys, config_file, dog):
    """Helper function to call the dog shell command."""
    import click
    from click.testing import CliRunner

    runner = CliRunner(mix_stderr=False)

    @click.command(context_settings={"ignore_unknown_options": True})
    @click.argument('args', nargs=-1, type=click.UNPROCESSED)
    def main(args):
        from datadog.dogshell import main as run
        orig = sys.argv
        try:
            sys.argv = list(args)
            run()
        finally:
            sys.argv = orig

    def run(args, stdin=None, check_return_code=True, use_cl_args=False):
        cmd = ["dogshell", "--config", config_file] + args
        if use_cl_args:
            cmd = [
                "dogshell",
                "--api-key={0}".format(dog._api_key),
                "--application-key={0}".format(dog._application_key),
            ] + args

        with capsys.disabled():
            result = runner.invoke(main, cmd, input=stdin, prog_name=cmd[0])
        return_code = result.exit_code
        out = result.stdout_bytes
        err = result.stderr_bytes
        if check_return_code:
            assert return_code == 0, err
            assert err == b""
        return out.decode("utf-8"), err.decode("utf-8"), return_code
    return run


@pytest.fixture
def dogshell_with_retry(vcr_cassette, dogshell):
    def run(cmd, retry_limit=10, retry_condition=lambda o, r: r != 0):
        number_of_interactions = len(vcr_cassette.data) if vcr_cassette.record_mode == "all" else -1

        out, err, return_code = dogshell(cmd, check_return_code=False)
        retry_count = 0
        while retry_count < retry_limit and retry_condition(out, return_code):
            time.sleep(WAIT_TIME)

            if vcr_cassette.record_mode == "all":
                # remove failed interactions
                vcr_cassette.data = vcr_cassette.data[:number_of_interactions]

            out, err, return_code = dogshell(cmd, check_return_code=False)
            retry_count += 1
        if retry_condition(out, return_code):
            raise Exception(
                "Retry limit reached for command {}:\nSTDOUT: {}\nSTDERR: {}\nSTATUS_CODE: {}".format(
                    cmd, out, err, return_code
                )
            )
        return out, err, return_code
    return run


@pytest.fixture
def get_unique(freezer, vcr_cassette_name, vcr_cassette, vcr):
    if vcr_cassette.record_mode == "all":
        seed = int(random.random() * 100000)

        with open(
            os.path.join(
                vcr.cassette_library_dir, vcr_cassette_name + ".seed"
            ),
            "w",
        ) as f:
            f.write(str(seed))
    else:
        with open(
            os.path.join(
                vcr.cassette_library_dir, vcr_cassette_name + ".seed"
            ),
            "r",
        ) as f:
            seed = int(f.readline().strip())

    random.seed(seed)

    def generate():
        with freezer:
            return md5(str(time.time() + random.random()).encode("utf-8")).hexdigest()
    return generate


class TestDogshell:
    host_name = "test.host.dogshell5"

    # Tests
    def test_config_args(self, dogshell):
        out, err, return_code = dogshell(["--help"], use_cl_args=True)
        assert 0 == return_code

    def test_comment(self, dogshell, dogshell_with_retry, user_handle):
        # Post a new comment
        cmd = ["comment", "post", user_handle]
        comment_msg = "yo dudes"
        post_data = {}
        out, _, _ = dogshell(cmd, stdin=comment_msg)
        post_data = self.parse_response(out)
        assert "id" in post_data
        assert "url" in post_data
        assert comment_msg in post_data["message"]

        # Read that comment from its id
        cmd = ["comment", "show", post_data["id"]]
        out, _, _ = dogshell_with_retry(cmd)
        show_data = self.parse_response(out)
        assert comment_msg in show_data["message"]

        # Update the comment
        cmd = ["comment", "update", post_data["id"], user_handle]
        new_comment = "nothing much"
        out, _, _ = dogshell(cmd, stdin=new_comment)
        update_data = self.parse_response(out)
        assert update_data["id"] == post_data["id"]
        assert new_comment in update_data["message"]

    def test_event(self, dog, dogshell, dogshell_with_retry):
        # Post an event
        title = "Testing events from dogshell"
        body = "%%%\n*Cool!*\n%%%\n"
        tags = "tag:a,tag:b"
        cmd = ["event", "post", title, "--tags", tags]
        event_id = None

        def match_permalink(out):
            match = re.match(r".*/event/event\?id=([0-9]*)", out, re.DOTALL) or re.match(
                r".*/event/jump_to\?event_id=([0-9]*)", out, re.DOTALL
            )
            if match:
                return match.group(1)
            else:
                return None

        out, err, return_code = dogshell(cmd, stdin=body)

        event_id = match_permalink(out)
        assert event_id

        # Retrieve the event
        cmd = ["event", "show", event_id]
        out, _, _ = dogshell_with_retry(cmd)
        event_id2 = match_permalink(out)
        assert event_id == event_id2

        # Get a real time from the event
        event = dog.Event.get(event_id)
        start = event["event"]["date_happened"] - 30 * 60
        end = event["event"]["date_happened"] + 1

        # Get a stream of events
        cmd = ["event", "stream", str(start), str(end), "--tags", tags]
        out, err, return_code = dogshell(cmd)
        event_ids = (match_permalink(l) for l in out.split("\n"))
        event_ids = set([e for e in event_ids if e])
        assert event_id in event_ids

    def test_metrics(self, dogshell, get_unique, dogshell_with_retry):
        # Submit a unique metric from a unique host
        unique = get_unique()
        metric = "test.dogshell.test_metric_{}".format(unique)
        host = "{}{}".format(self.host_name, unique)
        dogshell(["metric", "post", "--host", host, metric, "1"])

        # Query for the host and metric
        dogshell_with_retry(
            ["search", "query", unique], retry_condition=lambda o, r: host not in o or metric not in o
        )

        # Give the host some tags
        # The host tag association can take some time, so bump the retry limit to reduce flakiness
        tags0 = ["t0", "t1"]
        out, _, _ = dogshell_with_retry(["tag", "add", host] + tags0, retry_limit=30)
        for t in tags0:
            assert t in out

        # Verify that that host got those tags
        dogshell_with_retry(["tag", "show", host], retry_condition=lambda o, r: "t0" not in o or "t1" not in o)

        # Replace the tags with a different set
        tags1 = ["t2", "t3"]
        out, _, _ = dogshell(["tag", "replace", host] + tags1)
        for t in tags1:
            assert t in out
        for t in tags0:
            assert t not in out

        # Remove all the tags
        out, _, _ = dogshell(["tag", "detach", host])
        assert out == ""

    def test_timeboards(self, dogshell, get_unique):
        # Create a timeboard and write it to a file
        name, temp0 = get_temp_file()
        graph = {
            "title": "test metric graph",
            "definition": {"requests": [{"q": "testing.metric.1{host:blah.host.1}"}], "viz": "timeseries"},
        }
        dogshell(["timeboard", "new_file", name, json.dumps(graph)])
        dash = json.load(temp0)
        assert "id" in dash
        assert "title" in dash

        # Update the file and push it to the server
        unique = get_unique()
        dash["title"] = "dash title {}".format(unique)
        name, temp1 = get_temp_file()
        json.dump(dash, temp1)
        temp1.flush()
        dogshell(["timeboard", "push", temp1.name])

        # Query the server to verify the change
        out, _, _ = dogshell(["timeboard", "show", str(dash["id"])])

        out = json.loads(out)
        out["dash"]["id"] == dash["id"]
        out["dash"]["title"] == dash["title"]

        new_title = "new_title"
        new_desc = "new_desc"
        new_dash = [
            {
                "title": "blerg",
                "definition": {"viz": "timeseries", "requests": [{"q": "avg:system.load.15{web,env:prod}"}]},
            }
        ]

        # Update a dash directly on the server
        out, _, _ = dogshell(
            ["timeboard", "update", str(dash["id"]), new_title, new_desc], stdin=json.dumps(new_dash)
        )
        out = json.loads(out)
        # Template variables are empty, lets remove them because the `pull` command won't show them
        out["dash"].pop("template_variables", None)
        assert out["dash"]["id"] == dash["id"]
        assert out["dash"]["title"] == new_title
        assert out["dash"]["description"] == new_desc
        assert out["dash"]["graphs"] == new_dash

        # Pull the updated dash to disk
        fd, updated_file = tempfile.mkstemp()
        try:
            dogshell(["timeboard", "pull", str(dash["id"]), updated_file])
            updated_dash = {}
            with open(updated_file) as f:
                updated_dash = json.load(f)
            assert out["dash"] == updated_dash
        finally:
            os.unlink(updated_file)

        # Delete the dash
        dogshell(["--timeout", "30", "timeboard", "delete", str(dash["id"])])

        # Verify that it's not on the server anymore
        out, _, return_code = dogshell(["dashboard", "show", str(dash["id"])], check_return_code=False)
        assert return_code != 0

    def test_screenboards(self, dogshell, get_unique):
        # Create a screenboard and write it to a file
        name, temp0 = get_temp_file()
        graph = {
            "title": "test metric graph",
            "definition": {"requests": [{"q": "testing.metric.1{host:blah.host.1}"}], "viz": "timeseries"},
        }
        dogshell(["screenboard", "new_file", name, json.dumps(graph)])
        screenboard = json.load(temp0)

        assert "id" in screenboard
        assert "board_title" in screenboard

        # Update the file and push it to the server
        unique = get_unique()
        screenboard["title"] = "screenboard title {}".format(unique)
        name, temp1 = get_temp_file()
        json.dump(screenboard, temp1)
        temp1.flush()
        dogshell(["screenboard", "push", temp1.name])

        # Query the server to verify the change
        out, _, _ = dogshell(["screenboard", "show", str(screenboard["id"])])

        out = json.loads(out)
        assert out["id"] == screenboard["id"]
        assert out["title"] == screenboard["title"]

        new_title = "new_title"
        new_desc = "new_desc"
        new_screen = [{"title": "blerg", "definition": {"requests": [{"q": "avg:system.load.15{web,env:prod}"}]}}]

        # Update a screenboard directly on the server
        dogshell(
            ["screenboard", "update", str(screenboard["id"]), new_title, new_desc], stdin=json.dumps(new_screen)
        )
        # Query the server to verify the change
        out, _, _ = dogshell(["screenboard", "show", str(screenboard["id"])])
        out = json.loads(out)
        assert out["id"] == screenboard["id"]
        assert out["board_title"] == new_title
        assert out["description"] == new_desc
        assert out["widgets"] == new_screen

        # Pull the updated screenboard to disk
        fd, updated_file = tempfile.mkstemp()
        try:
            dogshell(["screenboard", "pull", str(screenboard["id"]), updated_file])
            updated_screenboard = {}
            with open(updated_file) as f:
                updated_screenboard = json.load(f)
            assert out == updated_screenboard
        finally:
            os.unlink(updated_file)

        # Share the screenboard
        out, _, _ = dogshell(["screenboard", "share", str(screenboard["id"])])
        out = json.loads(out)
        assert out["board_id"] == screenboard["id"]
        # Verify it's actually shared
        public_url = out["public_url"]
        response = requests.get(public_url)
        assert response.status_code == 200

        # Revoke the screenboard and verify it's actually revoked
        dogshell(["screenboard", "revoke", str(screenboard["id"])])
        response = requests.get(public_url)
        assert response.status_code == 404

        # Delete the screenboard
        dogshell(["--timeout", "30", "screenboard", "delete", str(screenboard["id"])])

        # Verify that it's not on the server anymore
        _, _, return_code = dogshell(["screenboard", "show", str(screenboard["id"])], check_return_code=False)
        assert return_code != 0

    # Test monitors
    @pytest.mark.admin_needed
    def test_monitors(self, dogshell):
        # Create a monitor
        query = "avg(last_1h):sum:system.net.bytes_rcvd{*} by {host} > 100"
        type_alert = "metric alert"
        out, _, _ = dogshell(["monitor", "post", type_alert, query])

        out = json.loads(out)
        assert out["query"] == query
        assert out["type"] == type_alert
        monitor_id = str(out["id"])
        monitor_name = out["name"]

        out, _, _ = dogshell(["monitor", "show", monitor_id])
        out = json.loads(out)
        assert out["query"] == query
        assert out["options"]["notify_no_data"] is False

        # Update options
        options = {"notify_no_data": True, "no_data_timeframe": 20}
        out, err, return_code = dogshell(
            ["monitor", "update", monitor_id, type_alert, query, "--options", json.dumps(options)],
            check_return_code=False
        )

        out = json.loads(out)
        assert query in out["query"]
        assert out["options"]["notify_no_data"] == options["notify_no_data"]
        assert out["options"]["no_data_timeframe"] == options["no_data_timeframe"]
        assert 'DEPRECATION' in err
        assert return_code == 0

        # Update message only
        updated_message = "monitor updated"
        current_options = out["options"]
        out, err, return_code = dogshell(
            ["monitor", "update", monitor_id, "--message", updated_message]
        )

        out = json.loads(out)
        assert updated_message == out["message"]
        assert query == out["query"]
        assert monitor_name == out["name"]
        assert current_options == out["options"]

        # Updating optional type and query
        updated_query = "avg(last_15m):sum:system.net.bytes_rcvd{*} by {env} > 222"
        updated_type = "query alert"

        out, err, return_code = dogshell(
            ["monitor", "update", monitor_id, "--type", updated_type, "--query", updated_query]
        )

        out = json.loads(out)
        assert updated_query in out["query"]
        assert updated_type in out["type"]
        assert updated_message in out["message"] # updated_message updated in previous step
        assert monitor_name in out["name"]
        assert current_options == out["options"]

        # Mute monitor
        out, _, _ = dogshell(["monitor", "mute", str(out["id"])])
        out = json.loads(out)
        assert str(out["id"]) == monitor_id
        assert out["options"]["silenced"] == {"*": None}

        # Unmute monitor
        out, _, _ = dogshell(["monitor", "unmute", "--all_scopes", monitor_id], check_return_code=False)
        out = json.loads(out)
        assert str(out["id"]) == monitor_id
        assert out["options"]["silenced"] == {}

        # Unmute all scopes of a monitor
        options = {"silenced": {"host:abcd1234": None, "host:abcd1235": None}}

        out, err, return_code = dogshell(
            ["monitor", "update", monitor_id, type_alert, query, "--options", json.dumps(options)],
            check_return_code=False
        )

        out = json.loads(out)
        assert out["query"] == query
        assert out["options"]["silenced"] == {"host:abcd1234": None, "host:abcd1235": None}
        assert "DEPRECATION" in err
        assert return_code == 0

        out, _, _ = dogshell(["monitor", "unmute", str(out["id"]), "--all_scopes"])
        out = json.loads(out)
        assert str(out["id"]) == monitor_id
        assert out["options"]["silenced"] == {}

        # Test can_delete monitor
        monitor_ids = [int(monitor_id)]
        str_monitor_ids = str(monitor_id)
        out, _, _ = dogshell(["monitor", "can_delete", str_monitor_ids])
        out = json.loads(out)
        assert out["data"]["ok"] == monitor_ids
        assert out["errors"] is None

        # Create a monitor-based SLO
        out, _, _ = dogshell(
            [
                "service_level_objective",
                "create",
                "--type",
                "monitor",
                "--monitor_ids",
                str_monitor_ids,
                "--name",
                "test_slo",
                "--thresholds",
                "7d:90",
            ]
        )
        out = json.loads(out)
        slo_id = out["data"][0]["id"]

        # Test can_delete monitor
        out, _, _ = dogshell(["monitor", "can_delete", str_monitor_ids])
        out = json.loads(out)
        assert out["data"]["ok"] == []
        # TODO update the error message template
        # assert out["errors"] == {
        #     str(monitor_id): [MONITOR_REFERENCED_IN_SLO_MESSAGE.format(monitor_id, slo_id)]
        # }

        # Delete a service_level_objective
        _, _, _ = dogshell(["service_level_objective", "delete", slo_id])

        # Test can_delete monitor
        out, _, _ = dogshell(["monitor", "can_delete", str_monitor_ids])
        out = json.loads(out)
        assert out["data"]["ok"] == monitor_ids
        assert out["errors"] is None

        # Delete a monitor
        dogshell(["monitor", "delete", monitor_id])
        # Verify that it's not on the server anymore
        _, _, return_code = dogshell(["monitor", "show", monitor_id], check_return_code=False)
        assert return_code != 0

        # Mute all
        out, _, _ = dogshell(["monitor", "mute_all"])
        out = json.loads(out)
        assert out["active"] is True

        # Unmute all
        dogshell(["monitor", "unmute_all"])
        # Retry unmuting all -> should raise an error this time
        _, _, return_code = dogshell(["monitor", "unmute_all"], check_return_code=False)
        assert return_code != 0

        # Test validate monitor
        monitor_type = "metric alert"
        valid_options = '{"thresholds": {"critical": 200.0}}'
        invalid_options = '{"thresholds": {"critical": 90.0}}'

        # Check with an invalid query.
        invalid_query = "THIS IS A BAD QUERY"
        out, _, _ = dogshell(["monitor", "validate", monitor_type, invalid_query, "--options", valid_options])
        out = json.loads(out)
        assert out == {"errors": ["The value provided for parameter 'query' is invalid"]}

        # Check with a valid query, invalid options.
        valid_query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 200"
        out, _, _ = dogshell(["monitor", "validate", monitor_type, valid_query, "--options", invalid_options])
        out = json.loads(out)
        assert out == {"errors": ["Alert threshold (90.0) does not match that used in the query (200.0)."]}

        # Check with a valid query, valid options.
        out, _, _ = dogshell(["monitor", "validate", monitor_type, valid_query, "--options", valid_options])
        out = json.loads(out)
        assert out == {}

    def test_host_muting(self, freezer, dogshell, get_unique, dogshell_with_retry):
        # Submit a metric to create a host
        hostname = "my.test.host{}".format(get_unique())
        dogshell(["metric", "post", "--host", hostname, "metric", "1"])

        # Wait for the host to appear
        dogshell_with_retry(["tag", "show", hostname])

        message = "Muting this host for a test."
        with freezer:
            end = int(time.time()) + 60 * 60

        # Mute a host
        out, _, _ = dogshell(["host", "mute", hostname, "--message", message, "--end", str(end)])
        out = json.loads(out)
        assert out["action"] == "Muted"
        assert out["hostname"] == hostname
        assert out["message"] == message
        assert out["end"] == end

        # We shouldn't be able to mute a host that's already muted, unless we include
        # the override param.
        end2 = end + 60 * 15

        _, _, return_code = dogshell_with_retry(
            ["host", "mute", hostname, "--end", str(end2)], retry_condition=lambda o, r: r == 0
        )
        assert return_code != 0

        out, _, _ = dogshell(["host", "mute", hostname, "--end", str(end2), "--override"])
        out = json.loads(out)
        assert out["action"] == "Muted"
        assert out["hostname"] == hostname
        assert out["end"] == end2

        # Unmute a host
        out, _, _ = dogshell(["host", "unmute", hostname])
        out = json.loads(out)
        assert out["action"] == "Unmuted"
        assert out["hostname"] == hostname

    def test_downtime_schedule(self, freezer, dogshell):
        # Schedule a downtime
        scope = "env:staging"
        with freezer:
            start = str(int(time.time()))
        out, _, _ = dogshell(["downtime", "post", scope, start])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is False
        downtime_id = str(out["id"])

        # Get downtime
        out, _, _ = dogshell(["downtime", "show", downtime_id])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is False

        # Update downtime
        message = "Doing some testing on staging."
        with freezer:
            end = int(time.time()) + 60000
        out, _, _ = dogshell(
            ["downtime", "update", downtime_id, "--scope", scope, "--end", str(end), "--message", message]
        )
        out = json.loads(out)
        assert out["end"] == end
        assert out["message"] == message
        assert out["disabled"] is False

        # Cancel downtime
        dogshell(["downtime", "delete", downtime_id])

        # Get downtime and check if it is cancelled
        out, _, _ = dogshell(["downtime", "show", downtime_id])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is True

    def test_downtime_cancel_by_scope(self, dogshell):
        # Schedule a downtime
        scope = "env:staging"
        out, _, _ = dogshell(["downtime", "post", scope, str(int(time.time()))])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is False
        downtime_id = str(out["id"])

        # Cancel the downtime by scope
        dogshell(["downtime", "cancel_by_scope", scope])

        # Get downtime and check if it is cancelled
        out, _, _ = dogshell(["downtime", "show", downtime_id])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is True

    def test_service_check(self, dogshell):
        out, _, _ = dogshell(["service_check", "check", "check_pg", "host0", "1"])
        out = json.loads(out)
        assert out["status"], "ok"

    def parse_response(self, out):
        data = {}
        for line in out.split("\n"):
            parts = re.split(r"\s+", str(line).strip())
            key = parts[0]
            # Could potentially have errors with other whitespace
            val = " ".join(parts[1:])
            if key:
                data[key] = val
        return data
