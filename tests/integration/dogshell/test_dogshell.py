from hashlib import md5
import json
import os
import random
import re
import subprocess
import time
import tempfile

import pytest
import requests

from datadog.util.compat import is_p3k, ConfigParser


TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
WAIT_TIME = 10


def get_temp_file():
    """Return a (fn, fp) pair"""
    if is_p3k():
        fn = "/tmp/{0}-{1}".format(time.time(), random.random())
        return (fn, open(fn, "w+"))
    else:
        tf = tempfile.NamedTemporaryFile()
        return (tf.name, tf)


class TestDogshell:
    host_name = "test.host.dogshell5"

    # Test init
    @classmethod
    def setup_class(cls):
        # Generate a config file for the dog shell
        cls.config_fn, cls.config_file = get_temp_file()
        config = ConfigParser()
        config.add_section("Connection")
        config.set("Connection", "apikey", os.environ["DD_TEST_CLIENT_API_KEY"])
        config.set("Connection", "appkey", os.environ["DD_TEST_CLIENT_APP_KEY"])
        config.set("Connection", "api_host", os.environ.get("DATADOG_HOST", "https://api.datadoghq.com"))
        config.write(cls.config_file)
        cls.config_file.flush()

    # Tests
    def test_config_args(self):
        out, err, return_code = self.dogshell(["--help"], use_cl_args=True)

    def test_comment(self):
        assert TEST_USER is not None, "You must set DD_TEST_CLIENT_USER environment variable to run comment tests"

        # Post a new comment
        cmd = ["comment", "post", TEST_USER]
        comment_msg = "yo dudes"
        post_data = {}
        out, _, _ = self.dogshell(cmd, stdin=comment_msg)
        post_data = self.parse_response(out)
        assert "id" in post_data
        assert "url" in post_data
        assert comment_msg in post_data["message"]

        # Read that comment from its id
        cmd = ["comment", "show", post_data["id"]]
        out, _, _ = self.dogshell_with_retry(cmd)
        show_data = self.parse_response(out)
        assert comment_msg in show_data["message"]

        # Update the comment
        cmd = ["comment", "update", post_data["id"], TEST_USER]
        new_comment = "nothing much"
        out, _, _ = self.dogshell(cmd, stdin=new_comment)
        update_data = self.parse_response(out)
        assert update_data["id"] == post_data["id"]
        assert new_comment in update_data["message"]

    def test_event(self):
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

        out, err, return_code = self.dogshell(cmd, stdin=body)

        event_id = match_permalink(out)
        assert event_id

        # Retrieve the event
        cmd = ["event", "show", event_id]
        out, _, _ = self.dogshell_with_retry(cmd)
        event_id2 = match_permalink(out)
        assert event_id == event_id2

        # Get a stream of events
        cmd = ["event", "stream", "30m", "--tags", tags]
        out, err, return_code = self.dogshell(cmd)
        event_ids = (match_permalink(l) for l in out.split("\n"))
        event_ids = set([e for e in event_ids if e])
        assert event_id in event_ids

    def test_metrics(self):
        # Submit a unique metric from a unique host
        unique = self.get_unique()
        metric = "test.dogshell.test_metric_{}".format(unique)
        host = "{}{}".format(self.host_name, unique)
        self.dogshell(["metric", "post", "--host", host, metric, "1"])

        # Query for the host and metric
        self.dogshell_with_retry(
            ["search", "query", unique], retry_condition=lambda o, r: host not in o or metric not in o
        )

        # Give the host some tags
        tags0 = ["t0", "t1"]
        out, _, _ = self.dogshell_with_retry(["tag", "add", host] + tags0)
        for t in tags0:
            assert t in out

        # Verify that that host got those tags
        self.dogshell_with_retry(["tag", "show", host], retry_condition=lambda o, r: "t0" not in o or "t1" not in o)

        # Replace the tags with a different set
        tags1 = ["t2", "t3"]
        out, _, _ = self.dogshell(["tag", "replace", host] + tags1)
        for t in tags1:
            assert t in out
        for t in tags0:
            assert t not in out

        # Remove all the tags
        out, _, _ = self.dogshell(["tag", "detach", host])
        assert out == ""

    def test_timeboards(self):
        # Create a timeboard and write it to a file
        name, temp0 = get_temp_file()
        graph = {
            "title": "test metric graph",
            "definition": {"requests": [{"q": "testing.metric.1{host:blah.host.1}"}], "viz": "timeseries"},
        }
        self.dogshell(["timeboard", "new_file", name, json.dumps(graph)])
        dash = json.load(temp0)
        assert "id" in dash
        assert "title" in dash

        # Update the file and push it to the server
        unique = self.get_unique()
        dash["title"] = "dash title {}".format(unique)
        name, temp1 = get_temp_file()
        json.dump(dash, temp1)
        temp1.flush()
        self.dogshell(["timeboard", "push", temp1.name])

        # Query the server to verify the change
        out, _, _ = self.dogshell(["timeboard", "show", str(dash["id"])])

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
        out, _, _ = self.dogshell(
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
            self.dogshell(["timeboard", "pull", str(dash["id"]), updated_file])
            updated_dash = {}
            with open(updated_file) as f:
                updated_dash = json.load(f)
            assert out["dash"] == updated_dash
        finally:
            os.unlink(updated_file)

        # Delete the dash
        self.dogshell(["timeboard", "delete", str(dash["id"])])

        # Verify that it's not on the server anymore
        out, _, return_code = self.dogshell(["dashboard", "show", str(dash["id"])], check_return_code=False)
        assert return_code != 0

    def test_screenboards(self):
        # Create a screenboard and write it to a file
        name, temp0 = get_temp_file()
        graph = {
            "title": "test metric graph",
            "definition": {"requests": [{"q": "testing.metric.1{host:blah.host.1}"}], "viz": "timeseries"},
        }
        self.dogshell(["screenboard", "new_file", name, json.dumps(graph)])
        screenboard = json.load(temp0)

        assert "id" in screenboard
        assert "board_title" in screenboard

        # Update the file and push it to the server
        unique = self.get_unique()
        screenboard["title"] = "screenboard title {}".format(unique)
        name, temp1 = get_temp_file()
        json.dump(screenboard, temp1)
        temp1.flush()
        self.dogshell(["screenboard", "push", temp1.name])

        # Query the server to verify the change
        out, _, _ = self.dogshell(["screenboard", "show", str(screenboard["id"])])

        out = json.loads(out)
        assert out["id"] == screenboard["id"]
        assert out["title"] == screenboard["title"]

        new_title = "new_title"
        new_desc = "new_desc"
        new_screen = [{"title": "blerg", "definition": {"requests": [{"q": "avg:system.load.15{web,env:prod}"}]}}]

        # Update a screenboard directly on the server
        self.dogshell(
            ["screenboard", "update", str(screenboard["id"]), new_title, new_desc], stdin=json.dumps(new_screen)
        )
        # Query the server to verify the change
        out, _, _ = self.dogshell(["screenboard", "show", str(screenboard["id"])])
        out = json.loads(out)
        assert out["id"] == screenboard["id"]
        assert out["board_title"] == new_title
        assert out["description"] == new_desc
        assert out["widgets"] == new_screen

        # Pull the updated screenboard to disk
        fd, updated_file = tempfile.mkstemp()
        try:
            self.dogshell(["screenboard", "pull", str(screenboard["id"]), updated_file])
            updated_screenboard = {}
            with open(updated_file) as f:
                updated_screenboard = json.load(f)
            assert out == updated_screenboard
        finally:
            os.unlink(updated_file)

        # Share the screenboard
        out, _, _ = self.dogshell(["screenboard", "share", str(screenboard["id"])])
        out = json.loads(out)
        assert out["board_id"] == screenboard["id"]
        # Verify it's actually shared
        public_url = out["public_url"]
        response = requests.get(public_url)
        assert response.status_code == 200

        # Revoke the screenboard and verify it's actually revoked
        self.dogshell(["screenboard", "revoke", str(screenboard["id"])])
        response = requests.get(public_url)
        assert response.status_code == 404

        # Delete the screenboard
        self.dogshell(["screenboard", "delete", str(screenboard["id"])])

        # Verify that it's not on the server anymore
        _, _, return_code = self.dogshell(["screenboard", "show", str(screenboard["id"])], check_return_code=False)
        assert return_code != 0

    # Test monitors
    @pytest.mark.admin_needed
    def test_monitors(self):
        # Create a monitor
        query = "avg(last_1h):sum:system.net.bytes_rcvd{*} by {host} > 100"
        type_alert = "metric alert"
        out, _, _ = self.dogshell(["monitor", "post", type_alert, query])

        out = json.loads(out)
        assert out["query"] == query
        assert out["type"] == type_alert
        monitor_id = str(out["id"])
        monitor_name = out["name"]

        out, _, _ = self.dogshell(["monitor", "show", monitor_id])
        out = json.loads(out)
        assert out["query"] == query
        assert out["options"]["notify_no_data"] is False

        # Update options
        options = {"notify_no_data": True, "no_data_timeframe": 20}
        out, err, return_code = self.dogshell(
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
        out, err, return_code = self.dogshell(
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

        out, err, return_code = self.dogshell(
            ["monitor", "update", monitor_id, "--type", updated_type, "--query", updated_query]
        )

        out = json.loads(out)
        assert updated_query in out["query"]
        assert updated_type in out["type"]
        assert updated_message in out["message"] # updated_message updated in previous step
        assert monitor_name in out["name"]
        assert current_options == out["options"]

        # Mute monitor
        out, _, _ = self.dogshell(["monitor", "mute", str(out["id"])])
        out = json.loads(out)
        assert str(out["id"]) == monitor_id
        assert out["options"]["silenced"] == {"*": None}

        # Unmute monitor
        out, _, _ = self.dogshell(["monitor", "unmute", "--all_scopes", monitor_id], check_return_code=False)
        out = json.loads(out)
        assert str(out["id"]) == monitor_id
        assert out["options"]["silenced"] == {}

        # Unmute all scopes of a monitor
        options = {"silenced": {"host:abcd1234": None, "host:abcd1235": None}}

        out, err, return_code = self.dogshell(
            ["monitor", "update", monitor_id, type_alert, query, "--options", json.dumps(options)],
            check_return_code=False
        )

        out = json.loads(out)
        assert out["query"] == query
        assert out["options"]["silenced"] == {"host:abcd1234": None, "host:abcd1235": None}
        assert "DEPRECATION" in err
        assert return_code == 0

        out, _, _ = self.dogshell(["monitor", "unmute", str(out["id"]), "--all_scopes"])
        out = json.loads(out)
        assert str(out["id"]) == monitor_id
        assert out["options"]["silenced"] == {}

        # Delete a monitor
        self.dogshell(["monitor", "delete", monitor_id])
        # Verify that it's not on the server anymore
        _, _, return_code = self.dogshell(["monitor", "show", monitor_id], check_return_code=False)
        assert return_code != 0

        # Mute all
        out, _, _ = self.dogshell(["monitor", "mute_all"])
        out = json.loads(out)
        assert out["active"] is True

        # Unmute all
        self.dogshell(["monitor", "unmute_all"])
        # Retry unmuting all -> should raise an error this time
        _, _, return_code = self.dogshell(["monitor", "unmute_all"], check_return_code=False)
        assert return_code != 0

    def test_host_muting(self):
        # Submit a metric to create a host
        hostname = "my.test.host{}".format(self.get_unique())
        self.dogshell(["metric", "post", "--host", hostname, "metric", "1"])

        # Wait for the host to appear
        self.dogshell_with_retry(["tag", "show", hostname])

        message = "Muting this host for a test."
        end = int(time.time()) + 60 * 60

        # Mute a host
        out, _, _ = self.dogshell(["host", "mute", hostname, "--message", message, "--end", str(end)])
        out = json.loads(out)
        assert out["action"] == "Muted"
        assert out["hostname"] == hostname
        assert out["message"] == message
        assert out["end"] == end

        # We shouldn't be able to mute a host that's already muted, unless we include
        # the override param.
        end2 = end + 60 * 15

        _, _, return_code = self.dogshell_with_retry(
            ["host", "mute", hostname, "--end", str(end2)], retry_condition=lambda o, r: r == 0
        )
        assert return_code != 0

        out, _, _ = self.dogshell(["host", "mute", hostname, "--end", str(end2), "--override"])
        out = json.loads(out)
        assert out["action"] == "Muted"
        assert out["hostname"] == hostname
        assert out["end"] == end2

        # Unmute a host
        out, _, _ = self.dogshell(["host", "unmute", hostname])
        out = json.loads(out)
        assert out["action"] == "Unmuted"
        assert out["hostname"] == hostname

    def test_downtime_schedule(self):
        # Schedule a downtime
        scope = "env:staging"
        out, _, _ = self.dogshell(["downtime", "post", scope, str(int(time.time()))])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is False
        downtime_id = str(out["id"])

        # Get downtime
        out, _, _ = self.dogshell(["downtime", "show", downtime_id])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is False

        # Update downtime
        message = "Doing some testing on staging."
        end = int(time.time()) + 60000
        out, _, _ = self.dogshell(
            ["downtime", "update", downtime_id, "--scope", scope, "--end", str(end), "--message", message]
        )
        out = json.loads(out)
        assert out["end"] == end
        assert out["message"] == message
        assert out["disabled"] is False

        # Cancel downtime
        self.dogshell(["downtime", "delete", downtime_id])

        # Get downtime and check if it is cancelled
        out, _, _ = self.dogshell(["downtime", "show", downtime_id])
        out = json.loads(out)
        assert out["scope"][0] == scope
        assert out["disabled"] is True

    def test_service_check(self):
        out, _, _ = self.dogshell(["service_check", "check", "check_pg", "host0", "1"])
        out = json.loads(out)
        assert out["status"], "ok"

    # Test helpers
    def dogshell(self, args, stdin=None, check_return_code=True, use_cl_args=False):
        """ Helper function to call the dog shell command
        """
        cmd = ["dog", "--config", self.config_file.name] + args
        if use_cl_args:
            cmd = [
                "dog",
                "--api-key={0}".format(os.environ["DD_TEST_CLIENT_API_KEY"]),
                "--application-key={0}".format(os.environ["DD_TEST_CLIENT_APP_KEY"]),
            ] + args
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        if stdin:
            out, err = proc.communicate(stdin.encode("utf-8"))
        else:
            out, err = proc.communicate()
        proc.wait()
        return_code = proc.returncode
        if check_return_code:
            assert return_code == 0, err
            assert err == b""
        return out.decode("utf-8"), err.decode("utf-8"), return_code

    def dogshell_with_retry(self, cmd, retry_limit=10, retry_condition=lambda o, r: r != 0):
        out, err, return_code = self.dogshell(cmd, check_return_code=False)
        retry_count = 0
        while retry_count < retry_limit and retry_condition(out, return_code):
            out, err, return_code = self.dogshell(cmd, check_return_code=False)
            time.sleep(WAIT_TIME)
            retry_count += 1
        if retry_condition(out, return_code):
            raise Exception(
                "Retry limit reached for command {}:\nSTDOUT: {}\nSTDERR: {}\nSTATUS_CODE: {}".format(
                    cmd, out, err, return_code
                )
            )
        return out, err, return_code

    def get_unique(self):
        return md5(str(time.time() + random.random()).encode("utf-8")).hexdigest()

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
