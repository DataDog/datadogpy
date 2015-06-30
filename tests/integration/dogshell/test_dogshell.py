# stdlib
from hashlib import md5
import json
import os
import random
import re
import socket
import subprocess
import time
import tempfile
import unittest
import requests

# 3rd
from nose.plugins.attrib import attr

# datadog
from datadog.dogshell.common import find_localhost
from datadog.util.compat import is_p3k, ConfigParser


def get_temp_file():
    """Return a (fn, fp) pair"""
    if is_p3k():
        fn = "/tmp/{0}-{1}".format(time.time(), random.random())
        return (fn, open(fn, 'w+'))
    else:
        tf = tempfile.NamedTemporaryFile()
        return (tf.name, tf)


class TestDogshell(unittest.TestCase):
    host_name = 'test.host.dogshell5'
    wait_time = 10

    # Test init
    def setUp(self):
        # Generate a config file for the dog shell
        self.config_fn, self.config_file = get_temp_file()
        config = ConfigParser()
        config.add_section('Connection')
        config.set('Connection', 'apikey', os.environ['DATADOG_API_KEY'])
        config.set('Connection', 'appkey', os.environ['DATADOG_APP_KEY'])
        config.set('Connection', 'api_host', os.environ['DATADOG_HOST'])
        config.write(self.config_file)
        self.config_file.flush()

    # Tests
    def test_config_args(self):
        out, err, return_code = self.dogshell(["--help"], use_cl_args=True)

    def test_find_localhost(self):
        # Once run
        assert socket.getfqdn() == find_localhost()
        # Once memoized
        assert socket.getfqdn() == find_localhost()

    def test_comment(self):
        # Post a new comment
        cmd = ["comment", "post"]
        comment_msg = "yo dudes"
        post_data = {}
        out, err, return_code = self.dogshell(cmd, stdin=comment_msg)
        post_data = self.parse_response(out)
        assert 'id' in post_data, post_data
        assert 'url' in post_data, post_data
        assert 'message' in post_data, post_data
        assert comment_msg in post_data['message']

        # Read that comment from its id
        time.sleep(self.wait_time)
        cmd = ["comment", "show", post_data['id']]
        out, err, return_code = self.dogshell(cmd)
        show_data = self.parse_response(out)
        assert comment_msg in show_data['message']

        # Update the comment
        cmd = ["comment", "update", post_data['id']]
        new_comment = "nothing much"
        out, err, return_code = self.dogshell(cmd, stdin=new_comment)
        update_data = self.parse_response(out)
        self.assertEquals(update_data['id'], post_data['id'])
        assert new_comment in update_data['message']

        # Read the updated comment
        time.sleep(self.wait_time)
        cmd = ["comment", "show", post_data['id']]
        out, err, return_code = self.dogshell(cmd)
        show_data2 = self.parse_response(out)
        assert new_comment in show_data2['message']

        # Delete the comment
        cmd = ["comment", "delete", post_data['id']]
        out, err, return_code = self.dogshell(cmd)
        # self.assertEquals(out, '')

        # Shouldn't get anything
        time.sleep(self.wait_time)
        cmd = ["comment", "show", post_data['id']]
        out, err, return_code = self.dogshell(cmd, check_return_code=False)
        self.assertEquals(out, '')
        self.assertEquals(return_code, 1)

    def test_event(self):
        # Post an event
        title = "Testing events from dogshell"
        body = "%%%\n*Cool!*\n%%%\n"
        tags = "tag:a,tag:b"
        cmd = ["event", "post", title, "--tags", tags]
        event_id = None

        def match_permalink(out):
            match = re.match(r'.*/event/event\?id=([0-9]*)', out, re.DOTALL) or \
                re.match(r'.*/event/jump_to\?event_id=([0-9]*)', out, re.DOTALL)
            if match:
                return match.group(1)
            else:
                return None

        out, err, return_code = self.dogshell(cmd, stdin=body)
        event_id = match_permalink(out)
        assert event_id, out

        # Add a bit of latency for the event to appear
        time.sleep(self.wait_time)

        # Retrieve the event
        cmd = ["event", "show", event_id]
        out, err, return_code = self.dogshell(cmd)
        event_id2 = match_permalink(out)
        self.assertEquals(event_id, event_id2)

        # Get a stream of events
        cmd = ["event", "stream", "30m", "--tags", tags]
        out, err, return_code = self.dogshell(cmd)
        event_ids = (match_permalink(l) for l in out.split("\n"))
        event_ids = set([e for e in event_ids if e])
        assert event_id in event_ids

    def test_metrics(self):
        # Submit a unique metric from a unique host
        unique = self.get_unique()
        metric = "test.dogshell.test_metric_%s" % unique
        host = self.host_name
        self.dogshell(["metric", "post", "--host", host, metric, "1"])

        # Query for the metric, commented out because caching prevents us
        # from verifying new metrics
        # out, err, return_code = self.dogshell(["search", "query",
        #   "metrics:" + metric])
        # assert metric in out, (metric, out)

        # Query for the host
        out, err, return_code = self.dogshell(["search", "query",
                                              "hosts:" + host])
        # assert host in out, (host, out)

        # Query for the host and metric
        out, err, return_code = self.dogshell(["search", "query", unique])
        # assert host in out, (host, out)
        # Caching prevents us from verifying new metrics
        # assert metric in out, (metric, out)

        # Give the host some tags
        tags0 = ["t0", "t1"]
        self.dogshell(["tag", "add", host] + tags0)

        # Verify that that host got those tags
        out, err, return_code = self.dogshell(["tag", "show", host])
        for t in tags0:
            assert t in out, (t, out)

        # Replace the tags with a different set
        tags1 = ["t2", "t3"]
        self.dogshell(["tag", "replace", host] + tags1)
        out, err, return_code = self.dogshell(["tag", "show", host])
        for t in tags1:
            assert t in out, (t, out)
        for t in tags0:
            assert t not in out, (t, out)

        # Remove all the tags
        self.dogshell(["tag", "detach", host])
        out, err, return_code = self.dogshell(["tag", "show", host])
        self.assertEquals(out, "")

    def test_timeboards(self):
        # Create a timeboard and write it to a file
        name, temp0 = get_temp_file()
        graph = {
            "title": "test metric graph",
            "definition":
                {
                    "requests": [{"q": "testing.metric.1{host:blah.host.1}"}],
                    "viz": "timeseries",
                }
        }

        self.dogshell(["timeboard", "new_file", name, json.dumps(graph)])
        dash = json.load(temp0)

        assert 'id' in dash, dash
        assert 'title' in dash, dash

        # Update the file and push it to the server
        unique = self.get_unique()
        dash['title'] = 'dash title %s' % unique
        name, temp1 = get_temp_file()
        json.dump(dash, temp1)
        temp1.flush()
        self.dogshell(["timeboard", "push", temp1.name])

        # Query the server to verify the change
        out, _, _ = self.dogshell(["timeboard", "show", str(dash['id'])])

        out = json.loads(out)
        assert "dash" in out, out
        assert "id" in out["dash"], out
        self.assertEquals(out["dash"]["id"], dash["id"])
        assert "title" in out["dash"]
        self.assertEquals(out["dash"]["title"], dash["title"])

        new_title = "new_title"
        new_desc = "new_desc"
        new_dash = [{
                    "title": "blerg",
                    "definition": {
                        "requests": [
                            {"q": "avg:system.load.15{web,env:prod}"}
                        ]
                    }
                    }]

        # Update a dash directly on the server
        self.dogshell(["timeboard", "update", str(dash["id"]), new_title, new_desc],
                      stdin=json.dumps(new_dash))

        # Query the server to verify the change
        out, _, _ = self.dogshell(["timeboard", "show", str(dash["id"])])
        out = json.loads(out)
        assert "dash" in out, out
        assert "id" in out["dash"], out
        self.assertEquals(out["dash"]["id"], dash["id"])
        assert "title" in out["dash"], out
        self.assertEquals(out["dash"]["title"], new_title)
        assert "description" in out["dash"], out
        self.assertEquals(out["dash"]["description"], new_desc)
        assert "graphs" in out["dash"], out
        self.assertEquals(out["dash"]["graphs"], new_dash)

        # Pull the updated dash to disk
        fd, updated_file = tempfile.mkstemp()
        try:
            self.dogshell(["timeboard", "pull", str(dash["id"]), updated_file])
            updated_dash = {}
            with open(updated_file) as f:
                updated_dash = json.load(f)
            assert "dash" in out
            self.assertEquals(out["dash"], updated_dash)
        finally:
            os.unlink(updated_file)

        # Delete the dash
        self.dogshell(["timeboard", "delete", str(dash["id"])])

        # Verify that it's not on the server anymore
        out, err, return_code = self.dogshell(["dashboard", "show", str(dash['id'])],
                                              check_return_code=False)
        self.assertNotEquals(return_code, 0)

    @attr('screenboard')
    def test_screenboards(self):
        # Create a screenboard and write it to a file
        name, temp0 = get_temp_file()
        graph = {
            "title": "test metric graph",
            "definition":
                {
                    "requests": [{"q": "testing.metric.1{host:blah.host.1}"}],
                    "viz": "timeseries",
                }
        }
        self.dogshell(["screenboard", "new_file", name, json.dumps(graph)])
        screenboard = json.load(temp0)

        assert 'id' in screenboard, screenboard
        assert 'title' in screenboard, screenboard

        # Update the file and push it to the server
        unique = self.get_unique()
        screenboard['title'] = 'screenboard title %s' % unique
        name, temp1 = get_temp_file()
        json.dump(screenboard, temp1)
        temp1.flush()
        self.dogshell(["screenboard", "push", temp1.name])

        # Query the server to verify the change
        out, _, _ = self.dogshell(["screenboard", "show", str(screenboard['id'])])

        out = json.loads(out)
        assert "id" in out, out
        self.assertEquals(out["id"], screenboard["id"])
        assert "title" in out, out
        self.assertEquals(out["title"], screenboard["title"])

        new_title = "new_title"
        new_desc = "new_desc"
        new_screen = [{
            "title": "blerg",
            "definition": {
                "requests": [
                    {"q": "avg:system.load.15{web,env:prod}"}
                ]
            }
        }]

        # Update a screenboard directly on the server
        self.dogshell(["screenboard", "update", str(screenboard["id"]), new_title, new_desc],
                      stdin=json.dumps(new_screen))
        # Query the server to verify the change
        out, _, _ = self.dogshell(["screenboard", "show", str(screenboard["id"])])
        out = json.loads(out)
        assert "id" in out, out
        self.assertEquals(out["id"], screenboard["id"])
        assert "title" in out, out
        self.assertEquals(out["title"], new_title)
        assert "description" in out, out
        self.assertEquals(out["description"], new_desc)
        assert "graphs" in out, out
        self.assertEquals(out["graphs"], new_screen)

        # Pull the updated screenboard to disk
        fd, updated_file = tempfile.mkstemp()
        try:
            self.dogshell(["screenboard", "pull", str(screenboard["id"]), updated_file])
            updated_screenboard = {}
            with open(updated_file) as f:
                updated_screenboard = json.load(f)
            self.assertEquals(out, updated_screenboard)
        finally:
            os.unlink(updated_file)

        # Share the screenboard
        out, _, _ = self.dogshell(["screenboard", "share", str(screenboard["id"])])
        out = json.loads(out)
        assert out['board_id'] == screenboard['id']
        # Verify it's actually shared
        public_url = out['public_url']
        response = requests.get(public_url)
        assert response.status_code == 200

        # Revoke the screenboard and verify it's actually revoked
        self.dogshell(["screenboard", "revoke", str(screenboard["id"])])
        response = requests.get(public_url)
        assert response.status_code == 404

        # Delete the screenboard
        self.dogshell(["screenboard", "delete", str(screenboard["id"])])

        # Verify that it's not on the server anymore
        out, err, return_code = self.dogshell(["screenboard", "show", str(screenboard['id'])],
                                              check_return_code=False)
        self.assertNotEquals(return_code, 0)

    # Test monitors

    def test_monitors(self):
        # Create a monitor
        query = "avg(last_1h):sum:system.net.bytes_rcvd{*} by {host} > 100"
        type_alert = "metric alert"
        out, err, return_code = self.dogshell(["monitor", "post", type_alert, query])

        assert "id" in out, out
        assert "query" in out, out
        assert "type" in out, out
        out = json.loads(out)
        self.assertEquals(out["query"], query)
        self.assertEquals(out["type"], type_alert)
        monitor_id = str(out["id"])

        out, err, return_code = self.dogshell(["monitor", "show", monitor_id])
        out = json.loads(out)
        self.assertEquals(out["query"], query)
        self.assertEquals(out['options']['notify_no_data'], False)

        # Update options
        options = {
            "notify_no_data": True,
            "no_data_timeframe": 20
        }

        out, err, return_code = self.dogshell(
            ["monitor", "update", monitor_id, type_alert,
             query, "--options", json.dumps(options)])

        assert "id" in out, out
        assert "options" in out, out
        out = json.loads(out)
        self.assertEquals(out["query"], query)
        self.assertEquals(out['options']['notify_no_data'], options["notify_no_data"])
        self.assertEquals(out['options']['no_data_timeframe'], options["no_data_timeframe"])

        # Mute monitor
        out, err, return_code = self.dogshell(["monitor", "mute", str(out["id"])])
        assert "id" in out, out
        out = json.loads(out)
        self.assertEquals(str(out["id"]), monitor_id)
        self.assertEquals(out["options"]["silenced"], {"*": None})

        # Unmute monitor
        out, err, return_code = self.dogshell(["monitor", "unmute", monitor_id], check_return_code=False)
        out = json.loads(out)
        self.assertEquals(str(out["id"]), monitor_id)
        self.assertEquals(out["options"]["silenced"], {})

        # Unmute all scopes of a monitor
        options = {
            "silenced": {"host:abcd1234": None, "host:abcd1235": None}
        }

        out, err, return_code = self.dogshell(
            ["monitor", "update", monitor_id, type_alert,
             query, "--options", json.dumps(options)])

        assert "id" in out, out
        assert "options" in out, out
        out = json.loads(out)
        self.assertEquals(out["query"], query)
        self.assertEquals(out["options"]["silenced"], {"host:abcd1234": None, "host:abcd1235": None})

        out, err, return_code = self.dogshell(["monitor", "unmute", str(out["id"]),
                                                "--all_scopes"])
        assert "id" in out, out
        out = json.loads(out)
        self.assertEquals(str(out["id"]), monitor_id)
        self.assertEquals(out["options"]["silenced"], {})

        # Delete a monitor
        self.dogshell(["monitor", "delete", monitor_id])
        # Verify that it's not on the server anymore
        out, err, return_code = self.dogshell(["monitor", "show", monitor_id], check_return_code=False)
        self.assertNotEquals(return_code, 0)

        # Mute all
        out, err, return_code = self.dogshell(["monitor", "mute_all"])
        assert "id" in out, out
        assert "active" in out, out
        out = json.loads(out)
        self.assertEquals(out["active"], True)

        # Unmute all
        self.dogshell(["monitor", "unmute_all"])
        # Retry unmuting all -> should raise an error this time
        out, err, return_code = self.dogshell(["monitor", "unmute_all"], check_return_code=False)
        self.assertNotEquals(return_code, 0)

    @attr('host')
    def test_host_muting(self):
        hostname = "my.test.host"
        message = "Muting this host for a test."
        end = int(time.time()) + 60 * 60

        # Reset test
        self.dogshell(["host", "unmute", hostname], check_return_code=False)

        # Mute a host
        out, err, return_code = self.dogshell(
            ["host", "mute", hostname, "--message", message, "--end", str(end)])
        out = json.loads(out)
        assert "action" in out, out
        assert "hostname" in out, out
        assert "message" in out, out
        assert "end" in out, out
        self.assertEquals(out['action'], "Muted")
        self.assertEquals(out['hostname'], hostname)
        self.assertEquals(out['message'], message)
        self.assertEquals(out['end'], end)

        # We shouldn't be able to mute a host that's already muted, unless we include
        # the override param.
        end2 = end + 60 * 15

        out, err, return_code = self.dogshell(
            ["host", "mute", hostname, "--end", str(end2)], check_return_code=False)
        assert err

        out, err, return_code = self.dogshell(
            ["host", "mute", hostname,  "--end", str(end2), "--override"])
        out = json.loads(out)
        assert "action" in out, out
        assert "hostname" in out, out
        assert "end" in out, out
        self.assertEquals(out['action'], "Muted")
        self.assertEquals(out['hostname'], hostname)
        self.assertEquals(out['end'], end2)

        # Unmute a host
        out, err, return_code = self.dogshell(["host", "unmute", hostname])
        out = json.loads(out)
        assert "action" in out, out
        assert "hostname" in out, out
        self.assertEquals(out['action'], "Unmuted")
        self.assertEquals(out['hostname'], hostname)

    def test_downtime_schedule(self):
        # Schedule a downtime
        scope = "env:staging"
        out, err, return_code = self.dogshell(["downtime", "post", scope,
                                              str(int(time.time()))])
        assert "id" in out, out
        assert "scope" in out, out
        assert "disabled" in out, out
        out = json.loads(out)
        self.assertEquals(out["scope"][0], scope)
        self.assertEquals(out["disabled"], False)
        downtime_id = str(out["id"])

        # Get downtime
        out, err, return_code = self.dogshell(["downtime", "show",
                                              downtime_id])
        assert "id" in out, out
        assert "scope" in out, out
        out = json.loads(out)
        self.assertEquals(out["scope"][0], scope)
        self.assertEquals(out["disabled"], False)

        # Update downtime
        message = "Doing some testing on staging."
        end = int(time.time()) + 60000
        out, err, return_code = self.dogshell(["downtime", "update",
                                              downtime_id,
                                              "--scope", scope, "--end",
                                               str(end), "--message", message])
        assert "end" in out, out
        assert "message" in out, out
        assert "disabled" in out, out
        out = json.loads(out)
        self.assertEquals(out["end"], end)
        self.assertEquals(out["message"], message)
        self.assertEquals(out["disabled"], False)

        # Cancel downtime
        self.dogshell(["downtime", "delete", downtime_id])

        # Get downtime and check if it is cancelled
        out, err, return_code = self.dogshell(["downtime", "show", downtime_id])
        assert "id" in out, out
        assert "scope" in out, out
        out = json.loads(out)
        self.assertEquals(out["scope"][0], scope)
        self.assertEquals(out["disabled"], True)

    def test_service_check(self):
        out, err, return_code = self.dogshell(["service_check", "check", "check_pg",
                                              'host0', "1"])
        assert "status" in out, out
        out = json.loads(out)
        self.assertEquals(out["status"], 'ok')

    # Test helpers
    def dogshell(self, args, stdin=None, check_return_code=True, use_cl_args=False):
        """ Helper function to call the dog shell command
        """
        cmd = ["dog", "--config", self.config_file.name] + args
        if use_cl_args:
            cmd = ["dog",
                   "--api-key={0}".format(os.environ["DATADOG_API_KEY"]),
                   "--application-key={0}".format(os.environ["DATADOG_APP_KEY"])] + args
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        if stdin:
            out, err = proc.communicate(stdin.encode("utf-8"))
        else:
            out, err = proc.communicate()
        proc.wait()
        return_code = proc.returncode
        if check_return_code:
            self.assertEquals(return_code, 0, err)
            self.assertEquals(err, b'')
        return out.decode('utf-8'), err.decode('utf-8'), return_code

    def get_unique(self):
        return md5(str(time.time() + random.random()).encode('utf-8')).hexdigest()

    def parse_response(self, out):
        data = {}
        for line in out.split('\n'):
            parts = re.split('\s+', str(line).strip())
            key = parts[0]
            # Could potentially have errors with other whitespace
            val = " ".join(parts[1:])
            if key:
                data[key] = val
        return data

if __name__ == '__main__':
    unittest.main()
