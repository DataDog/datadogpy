# python
import datetime
import os
import time
import unittest
import requests
import json

# 3p
import pytest

# datadog
from datadog import initialize
from datadog import api as dog
from datadog.api.exceptions import ApiError
from tests.integration.util.snapshot_test_utils import (
    assert_snap_not_blank, assert_snap_has_no_events
)

TEST_USER = os.environ.get('DD_TEST_CLIENT_USER')
API_KEY = os.environ.get('DD_TEST_CLIENT_API_KEY', "a"*32)
APP_KEY = os.environ.get('DD_TEST_CLIENT_APP_KEY', "a"*40)
API_HOST = os.environ.get('DATADOG_HOST')
FAKE_PROXY = {
    "https": "http://user:pass@10.10.1.10:3128/",
}


def eq(a, b):
    assert a == b


def ok(assertion, message):
    assert assertion, message


class TestDatadog(unittest.TestCase):
    host_name = 'test.host.unit'
    wait_time = 10

    def setUp(self):
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
        dog._swallow = False

    @pytest.mark.tags
    def test_tags(self):
        # post a metric to make sure the test host context exists
        hostname = self.host_name
        dog.Metric.send(metric='test.tag.metric', points=1, host=hostname)

        dog.Tag.get_all()

        dog.Tag.delete(hostname)
        assert len(dog.Tag.get(hostname)['tags']) == 0

        dog.Tag.create(hostname, tags=['test.tag.1', 'test.tag.2'], source='datadog')
        new_tags = dog.Tag.get(hostname)['tags']
        assert len(new_tags) == 2
        assert 'test.tag.1' in new_tags
        assert 'test.tag.2' in new_tags

        dog.Tag.create(hostname, tags=['test.tag.3'], source='datadog')
        new_tags = dog.Tag.get(hostname)['tags']
        assert len(new_tags) == 3
        assert 'test.tag.1' in new_tags
        assert 'test.tag.2' in new_tags
        assert 'test.tag.3' in new_tags

        dog.Tag.update(hostname, tags=['test.tag.4'], source='datadog')
        new_tags = dog.Tag.get(hostname)['tags']
        assert len(new_tags) == 1
        assert 'test.tag.4' in new_tags

        dog.Tag.delete(hostname, source='datadog')
        assert len(dog.Tag.get(hostname)['tags']) == 0

    def test_events(self):
        now = datetime.datetime.now()

        now_ts = int(time.mktime(now.timetuple()))
        now_title = 'end test title ' + str(now_ts)
        now_message = 'test message ' + str(now_ts)

        before_ts = int(time.mktime((now - datetime.timedelta(minutes=5)).timetuple()))
        before_title = 'start test title ' + str(before_ts)
        before_message = 'test message ' + str(before_ts)

        now_event_id = dog.Event.create(title=now_title, text=now_message,
                                        date_happened=now_ts)['event']['id']
        before_event_id = dog.Event.create(title=before_title, text=before_message,
                                           date_happened=before_ts)['event']['id']
        time.sleep(self.wait_time)

        now_event = self.get_event_with_retry(now_event_id)
        before_event = self.get_event_with_retry(before_event_id)

        self.assertEqual(now_event['event']['text'], now_message)
        self.assertEqual(before_event['event']['text'], before_message)

        event_id = dog.Event.create(title='test host and device',
                                    text='test host and device',
                                    host=self.host_name,)['event']['id']
        time.sleep(self.wait_time)
        event = self.get_event_with_retry(event_id)

        self.assertEqual(event['event']['host'], self.host_name)

        event_id = dog.Event.create(title='test event tags',
                                    text='test event tags',
                                    tags=['test-tag-1', 'test-tag-2'])['event']['id']
        time.sleep(self.wait_time)
        event = self.get_event_with_retry(event_id)

        self.assertIn('test-tag-1', event['event']['tags'])
        self.assertIn('test-tag-2', event['event']['tags'])

        event_id = dog.Event.create(
            title='test no hostname',
            text='test no hostname',
            attach_host_name=False
        )['event']['id']
        time.sleep(self.wait_time)
        event = self.get_event_with_retry(event_id)
        assert not event['event']['host']

    def test_aggregate_events(self):
        now_ts = int(time.time())
        agg_key = 'aggregate_me ' + str(now_ts)
        msg_1 = 'aggregate 1'
        msg_2 = 'aggregate 2'

        # send two events that should aggregate
        event1_id = dog.Event.create(title=msg_1, text=msg_1,
                                     aggregation_key=agg_key)['event']['id']
        event2_id = dog.Event.create(title=msg_2, text=msg_2,
                                     aggregation_key=agg_key)['event']['id']
        time.sleep(self.wait_time)

        event1 = self.get_event_with_retry(event1_id)
        event2 = self.get_event_with_retry(event2_id)

        self.assertEqual(msg_1, event1['event']['text'])
        self.assertEqual(msg_2, event2['event']['text'])

        # TODO FIXME: Need the aggregation_id to check if they are attached to the
        # same aggregate

    def test_git_commits(self):
        """Pretend to send git commits"""
        event_id = dog.Event.create(title="Testing git commits", text="""$$$
            eac54655 *   Merge pull request #2 from DataDog/alq-add-arg-validation (alq@datadoghq.com)
            |\
            760735ef | * origin/alq-add-arg-validation Simple typecheck between metric and metrics (matt@datadoghq.com)
            |/
            f7a5a23d * missed version number in docs (matt@datadoghq.com)
            $$$""", event_type="commit", source_type_name="git", event_object="0xdeadbeef")['event']['id']
        event = self.get_event_with_retry(event_id)
        self.assertEqual(event['event']['title'], "Testing git commits")

    def test_comments(self):
        self.assertIsNotNone(
            TEST_USER,
            "You must set DD_TEST_CLIENT_USER environment to run comment tests"
        )

        now = datetime.datetime.now()
        now_ts = int(time.mktime(now.timetuple()))
        before_ts = int(time.mktime((now - datetime.timedelta(minutes=15)).timetuple()))
        message = 'test message ' + str(now_ts)
        comment_id = dog.Comment.create(handle=TEST_USER, message=message)['comment']['id']
        time.sleep(self.wait_time)
        event = dog.Event.get(comment_id)
        eq(event['event']['text'], message)
        dog.Comment.update(comment_id, handle=TEST_USER, message=message + ' updated')
        time.sleep(self.wait_time)
        event = dog.Event.get(comment_id)
        eq(event['event']['text'], message + ' updated')
        reply_id = dog.Comment.create(handle=TEST_USER, message=message + ' reply',
                                      related_event_id=comment_id)['comment']['id']
        time.sleep(30)
        stream = dog.Event.query(start=before_ts, end=now_ts + 100)['events']
        ok(stream is not None, msg="No events found in stream")
        ok(isinstance(stream, list), msg="Event stream is not a list")
        ok(len(stream) > 0, msg="No events found in stream")
        comment_ids = [x['id'] for x in stream[0]['comments']]
        ok(reply_id in comment_ids,
           msg="Should find {0} in {1}".format(reply_id, comment_ids))

    @pytest.mark.timeboards
    @pytest.mark.validation
    def test_timeboard_validation(self):
        graph = {
            "title": "test metric graph",
            "definition":
                {
                    "requests": [{"q": "testing.metric.1{host:blah.host.1}"}],
                    "viz": "timeseries",
                }
        }

        # No title
        resp = dog.Timeboard.create(title=None, description='my api timeboard', graphs=[graph])
        exception_msg = resp['errors'][0]
        eq(exception_msg, "The parameter 'title' is required")

        # No graph
        resp = dog.Timeboard.create(title='api timeboard', description='my api timeboard', graphs=None)
        exception_msg = resp['errors'][0]
        eq(exception_msg, "The parameter 'graphs' is required")

        # Graphs not list
        dog.Timeboard.create(title='api timeboard', description='my api timeboard',
                                graphs=graph)
        exception_msg = resp['errors'][0]
        eq(exception_msg, "The parameter 'graphs' is required")

        # Empty list of graphs
        resp = dog.Timeboard.create(title='api timeboard', description='my api timeboard', graphs=[])
        exception_msg = resp['errors'][0]
        eq(exception_msg, "The 'graphs' parameter is required")

        # None in the graph list
        resp = dog.Timeboard.create(title='api timeboard', description='my api timeboard',
                                graphs=[graph, None])
        exception_msg = resp['errors'][0]
        eq(exception_msg, "The 'graphs' parameter contains None graphs")

        # Dashboard not found
        resp = dog.Timeboard.get(999999)
        exception_msg = resp['errors'][0]
        eq(exception_msg, "No dashboard matches that dash_id.")

    @pytest.mark.dashboards
    def test_timeboard(self):
        graph = {
            "title": "test metric graph",
            "definition":
                {
                    "requests": [{"q": "testing.metric.1{host:blah.host.1}"}],
                    "viz": "timeseries",
                }
        }

        timeboard_id = dog.Timeboard.create(title='api timeboard', description='my api timeboard',
                                            graphs=[graph])['dash']['id']
        remote_timeboard = dog.Timeboard.get(timeboard_id)

        eq('api timeboard', remote_timeboard['dash']['title'])
        eq('my api timeboard', remote_timeboard['dash']['description'])
        eq(graph['definition']['requests'],
           remote_timeboard['dash']['graphs'][0]['definition']['requests'])

        graph = {
            "title": "updated test metric graph",
            "definition": {
                "requests": [{"q": "testing.metric.1{host:blah.host.1}"}],
                "viz": "timeseries",
            }
        }

        timeboard_id = dog.Timeboard.update(timeboard_id, title='updated api timeboard',
                                            description='my updated api timeboard',
                                            graphs=[graph])['dash']['id']

        # Query and ensure all is well.
        remote_timeboard = dog.Timeboard.get(timeboard_id)

        eq('updated api timeboard', remote_timeboard['dash']['title'])
        eq('my updated api timeboard', remote_timeboard['dash']['description'])

        p = graph['definition']['requests']
        eq(p, remote_timeboard['dash']['graphs'][0]['definition']['requests'])

        # Query all dashboards and make sure it's in there.

        timeboards = dog.Timeboard.get_all()['dashes']
        ids = [timeboard["id"] for timeboard in timeboards]
        assert timeboard_id in ids or str(timeboard_id) in ids

        dog.Timeboard.delete(timeboard_id)

        try:
            dog.get(timeboard_id)
        except Exception:
            pass
        else:
            # the previous get *should* throw an exception
            assert False

    def test_search(self):
        results = dog.Infrastructure.search(q='e')
        assert len(results['results']['hosts']) > 0
        assert len(results['results']['metrics']) > 0

    @pytest.mark.metric
    def test_metrics(self):
        now = datetime.datetime.now()
        now_ts = int(time.mktime(now.timetuple()))
        metric_name = "test.metric." + str(now_ts)
        host_name = "test.host." + str(now_ts)

        dog.Metric.send(metric=metric_name, points=1, host=host_name)
        time.sleep(self.wait_time)

        metric_query = dog.Metric.query(start=now_ts - 3600, end=now_ts + 3600,
                                        query="%s{host:%s}" % (metric_name, host_name))
        # There can be a slight delay before the metric is ready to be queried
        retry_time = 0
        while not metric_query['series'] and retry_time < 10:
            metric_query = dog.Metric.query(start=now_ts - 3600, end=now_ts + 3600,
                query="%s{host:%s}" % (metric_name, host_name))
            time.sleep(self.wait_time)
            retry_time += 1
        assert len(metric_query['series']) == 1, metric_query

        # results = dog.Infrastructure.search(q='metrics:test.metric.' + str(now_ts))
        # TODO mattp: cache issue. move this test to server side.
        # assert len(results['results']['metrics']) == 1, results

        matt_series = [
            (int(time.mktime((now - datetime.timedelta(minutes=25)).timetuple())), 5),
            (int(time.mktime((now - datetime.timedelta(minutes=25)).timetuple())) + 1, 15),
            (int(time.mktime((now - datetime.timedelta(minutes=24)).timetuple())), 10),
            (int(time.mktime((now - datetime.timedelta(minutes=23)).timetuple())), 15),
            (int(time.mktime((now - datetime.timedelta(minutes=23)).timetuple())) + 1, 5),
            (int(time.mktime((now - datetime.timedelta(minutes=22)).timetuple())), 5),
            (int(time.mktime((now - datetime.timedelta(minutes=20)).timetuple())), 15),
            (int(time.mktime((now - datetime.timedelta(minutes=18)).timetuple())), 5),
            (int(time.mktime((now - datetime.timedelta(minutes=17)).timetuple())), 5),
            (int(time.mktime((now - datetime.timedelta(minutes=17)).timetuple())) + 1, 15),
            (int(time.mktime((now - datetime.timedelta(minutes=15)).timetuple())), 15),
            (int(time.mktime((now - datetime.timedelta(minutes=15)).timetuple())) + 1, 5),
            (int(time.mktime((now - datetime.timedelta(minutes=14)).timetuple())), 5),
            (int(time.mktime((now - datetime.timedelta(minutes=14)).timetuple())) + 1, 15),
            (int(time.mktime((now - datetime.timedelta(minutes=12)).timetuple())), 15),
            (int(time.mktime((now - datetime.timedelta(minutes=12)).timetuple())) + 1, 5),
            (int(time.mktime((now - datetime.timedelta(minutes=11)).timetuple())), 5),
        ]

        dog.Metric.send(metric='matt.metric', points=matt_series, host="matt.metric.host")

    def test_type_check(self):
        dog.Metric.send(metric="test.metric", points=[(time.time() - 3600, 1.0)])
        dog.Metric.send(metric="test.metric", points=1.0)
        dog.Metric.send(metric="test.metric", points=(time.time(), 1.0))

    @pytest.mark.monitor
    def test_monitors(self):
        query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"

        monitor_id = dog.Monitor.create(query=query, type="metric alert")['id']
        monitor = dog.Monitor.get(monitor_id)
        time.sleep(self.wait_time)
        assert monitor['query'] == query, monitor['query']
        assert monitor['options']['notify_no_data'] is False, monitor['options']['notify_no_data']

        options = {
            "notify_no_data": True,
            "no_data_timeframe": 20,
            "silenced": {"*": None}
        }
        dog.Monitor.update(monitor_id, query=query, options=options, timeout_h=1)
        monitor = dog.Monitor.get(monitor_id)
        assert monitor['query'] == query, monitor['query']
        assert monitor['options']['notify_no_data'] is True, monitor['options']['notify_no_data']
        assert monitor['options']['no_data_timeframe'] == 20, monitor['options']['no_data_timeframe']
        assert monitor['options']['silenced'] == {"*": None}, monitor['options']['silenced']

        dog.Monitor.delete(monitor_id)
        resp = dog.Monitor.delete(monitor_id)
        eq(resp["errors"][0], "Monitor not found")

        query1 = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"
        query2 = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 200"

        monitor_id1 = dog.Monitor.create(query=query1, type="metric alert")['id']
        monitor_id2 = dog.Monitor.create(query=query2, type="metric alert")['id']
        monitors = dog.Monitor.get_all()
        monitor1 = [a for a in monitors if a['id'] == monitor_id1][0]
        monitor2 = [a for a in monitors if a['id'] == monitor_id2][0]
        assert monitor1['query'] == query1, monitor1
        assert monitor2['query'] == query2, monitor2

    def test_user_error(self):
        query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"

        dog._swallow = True

        monitor = dog.Monitor.create(query=query, type="metric alert")
        assert 'id' in monitor, monitor
        result = dog.Monitor.update(monitor['id'], query='aaa', silenced=True)
        assert 'errors' in result, result

        dog._swallow = False

        monitor_id = dog.Monitor.create(query=query, type="metric alert")['id']
        assert monitor_id == int(monitor_id), monitor_id
        result = dog.Monitor.update(monitor_id, query='aaa', silenced=True)
        assert result['errors'][0] == "The value provided for parameter 'query' is invalid"

    @pytest.mark.snapshot
    def test_graph_snapshot(self):
        metric_query = "system.load.1{*}"
        event_query = "*"
        end = int(time.time())
        start = end - 60 * 60  # go back 1 hour

        # Test without an event query
        snap = dog.Graph.create(metric_query=metric_query, start=start, end=end)
        ok('snapshot_url' in snap, msg=snap)
        ok('metric_query' in snap, msg=snap)
        ok('event_query' not in snap, msg=snap)
        eq(snap['metric_query'], metric_query)
        snapshot_url = snap['snapshot_url']
        while dog.Graph.status(snapshot_url)['status_code'] != 200:
            time.sleep(self.wait_time)
        if 'localhost' in dog._api_host:
            snapshot_url = 'http://%s%s' % (dog.api_host, snapshot_url)
        assert_snap_not_blank(snapshot_url)
        assert_snap_has_no_events(snapshot_url)

        # Test with an event query
        snap = dog.Graph.create(metric_query=metric_query, start=start, end=end,
                                event_query=event_query)
        ok('snapshot_url' in snap, msg=snap)
        ok('metric_query' in snap, msg=snap)
        ok('event_query' in snap, msg=snap)
        eq(snap['metric_query'], metric_query)
        eq(snap['event_query'], event_query)
        snapshot_url = snap['snapshot_url']
        while dog.Graph.status(snapshot_url)['status_code'] != 200:
            time.sleep(self.wait_time)
        if 'localhost' in dog._api_host:
            snapshot_url = 'http://%s%s' % (dog.api_host, snapshot_url)
        assert_snap_not_blank(snapshot_url)

        # Test with a graph def
        graph_def = {
            "viz": "toplist",
            "requests": [{
                "q": "top(system.disk.free{*} by {device}, 10, 'mean', 'desc')",
                "style": {
                    "palette": "dog_classic"
                },
                "conditional_formats": [{
                    "palette": "red",
                    "comparator": ">",
                    "value": 50000000000
                }, {
                    "palette": "green",
                    "comparator": ">",
                    "value": 30000000000
                }]
            }]
        }
        graph_def = json.dumps(graph_def)
        snap = dog.Graph.create(graph_def=graph_def, start=start, end=end)
        ok('snapshot_url' in snap, msg=snap)
        ok('graph_def' in snap, msg=snap)
        ok('metric_query' not in snap, msg=snap)
        ok('event_query' not in snap, msg=snap)
        eq(snap['graph_def'], graph_def)
        snapshot_url = snap['snapshot_url']
        while dog.Graph.status(snapshot_url)['status_code'] != 200:
            time.sleep(self.wait_time)
        if 'localhost' in dog._api_host:
            snapshot_url = 'http://%s%s' % (dog.api_host, snapshot_url)
        assert_snap_not_blank(snapshot_url)

    @pytest.mark.screenboard
    def test_screenboard(self):
        def _compare_screenboard(apiBoard, expectedBoard):
            compare_keys = ['board_title', 'height', 'width', 'widgets']
            for key in compare_keys:
                assert apiBoard[key] == expectedBoard[key], key

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
                    "time": {
                        "live_span": "1w"
                    }
                },
                {
                    "type": "image",
                    "height": 20,
                    "width": 32,
                    "y": 7,
                    "x": 32,
                    "url": "http://path/to/image.jpg"
                }
            ]
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
                    "url": "http://path/to/image.jpg"
                }
            ]
        }

        create_res = dog.Screenboard.create(**board)
        _compare_screenboard(board, create_res)

        get_res = dog.Screenboard.get(create_res['id'])
        _compare_screenboard(get_res, create_res)
        assert get_res['id'] == create_res['id']

        get_all_res = dog.Screenboard.get_all()['screenboards']
        created = [s for s in get_all_res if s['id'] == create_res['id']]
        self.assertEqual(len(created), 1)
        update_res = dog.Screenboard.update(get_res['id'], **updated_board)
        _compare_screenboard(update_res, updated_board)
        assert get_res['id'] == update_res['id']

        share_res = dog.Screenboard.share(get_res['id'])
        assert share_res['board_id'] == get_res['id']
        public_url = share_res['public_url']

        response = requests.get(public_url)
        assert response.status_code == 200

        dog.Screenboard.revoke(get_res['id'])
        response = requests.get(public_url)
        assert response.status_code == 404

        delete_res = dog.Screenboard.delete(update_res['id'])
        assert delete_res['id'] == update_res['id']

    @pytest.mark.monitor
    def test_monitor_crud(self):
        # Metric alerts
        query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"

        options = {
            'silenced': {'*': int(time.time()) + 60 * 60},
            'notify_no_data': False
        }
        monitor_id = dog.Monitor.create(type='metric alert', query=query, options=options)['id']
        monitor = dog.Monitor.get(monitor_id)

        eq(monitor['query'], query)
        eq(monitor['options']['notify_no_data'],
            options['notify_no_data'])
        eq(monitor['options']['silenced'], options['silenced'])

        query2 = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 200"
        updated_monitor_id = dog.Monitor.update(monitor_id, query=query2, options=options)['id']
        monitor = dog.Monitor.get(updated_monitor_id)
        eq(monitor['query'], query2)

        name = 'test_monitors'
        monitor_id = dog.Monitor.update(monitor_id, query=query2, name=name,
                                        options={'notify_no_data': True})['id']
        monitor = dog.Monitor.get(monitor_id)
        eq(monitor['name'], name)
        eq(monitor['options']['notify_no_data'], True)

        dog.Monitor.delete(monitor_id)
        resp = dog.Monitor.get(monitor_id)
        assert 'Monitor not found' in resp.get('errors'), resp

        query1 = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"
        query2 = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 200"

        monitor_id1 = dog.Monitor.create(type='metric alert', query=query1)['id']
        monitor_id2 = dog.Monitor.create(type='metric alert', query=query2)['id']
        monitors = dog.Monitor.get_all(group_states=['alert', 'warn'])
        monitor1 = [m for m in monitors if m['id'] == monitor_id1][0]
        monitor2 = [m for m in monitors if m['id'] == monitor_id2][0]
        assert monitor1['query'] == query1, monitor1
        assert monitor2['query'] == query2, monitor2

        # Service checks
        query = '"ntp.in_sync".over("role:herc").last(3).count_by_status()'
        options = {
            'notify_no_data': True,
            'no_data_timeframe': 3,
            'thresholds': {
                'ok': 3,
                'warning': 2,
                'critical': 1,
            }
        }
        monitor_id = dog.Monitor.create(type='service check', query=query, options=options)['id']
        monitor = dog.Monitor.get(monitor_id, group_states=['all'])

        eq(monitor['query'], query)
        eq(monitor['options']['notify_no_data'],
            options['notify_no_data'])
        eq(monitor['options']['no_data_timeframe'], options['no_data_timeframe'])
        eq(monitor['options']['thresholds'], options['thresholds'])

        query2 = '"ntp.in_sync".over("role:sobotka").last(3).count_by_status()'
        monitor_id = dog.Monitor.update(monitor_id, query=query2)['id']
        monitor = dog.Monitor.get(monitor_id)
        eq(monitor['query'], query2)

        dog.Monitor.delete(monitor_id)
        resp = dog.Monitor.get(monitor_id)
        assert resp.get('errors')[0] == 'Monitor not found'

    # @pytest.mark.monitor
    # def test_monitor_muting(self):
    #     query = "avg(last_1h):sum:system.net.bytes_rcvd{host:host0} > 100"
    #     monitor_id = dog.Monitor.create(type='metric alert', query=query)['id']
    #     monitor = dog.Monitor.get(monitor_id)
    #     eq(monitor['query'], query)

        # dt = dog.Monitor.mute_all()
        # eq(dt['active'], True)
        # eq(dt['scope'], ['*'])

        # dt = dog.Monitor.unmute_all()
        # eq(dt, None)  # No response is expected.

        # # We shouldn't be able to mute a simple alert on a scope.
        # assert_raises(ApiError, dog.Monitor.mute, monitor_id, scope='env:staging')

        # query2 = "avg(last_1h):sum:system.net.bytes_rcvd{*} by {host} > 100"
        # monitor_id = dog.Monitor.create(type='metric alert', query=query2)['id']
        # monitor = dog.Monitor.get(monitor_id)
        # eq(monitor['query'], query2)

        # dog.Monitor.mute(monitor_id, scope='host:foo')
        # monitor = dog.Monitor.get(monitor_id)
        # eq(monitor['options']['silenced'], {'host:foo': None})

        # dog.Monitor.unmute(monitor_id, scope='host:foo')
        # monitor = dog.Monitor.get(monitor_id)
        # eq(monitor['options']['silenced'], {})

        # options = {
        #     "silenced": {"host:abcd1234": None, "host:abcd1235": None}
        # }
        # dog.Monitor.update(monitor_id, query=query, options=options)
        # monitor = dog.Monitor.get(monitor_id)
        # eq(monitor['options']['silenced'], options['silenced'])

        # dog.Monitor.unmute(monitor_id, all_scopes=True)
        # monitor = dog.Monitor.get(monitor_id)
        # eq(monitor['options']['silenced'], {})

        # dog.Monitor.delete(monitor_id)

    @pytest.mark.monitor
    def test_downtime(self):
        start = int(time.time())
        end = start + 1000

        # Create downtime
        downtime_id = dog.Downtime.create(scope='env:staging', start=start, end=end)['id']
        dt = dog.Downtime.get(downtime_id)
        eq(dt['start'], start)
        eq(dt['end'], end)
        eq(dt['scope'], ['env:staging'])
        eq(dt['disabled'], False)

        # Update downtime
        message = "Doing some testing on staging."
        end = int(time.time()) + 60000
        dog.Downtime.update(downtime_id, scope='env:staging',
                            end=end, message=message)
        dt = dog.Downtime.get(downtime_id)
        eq(dt['end'], end)
        eq(dt['message'], message)
        eq(dt['disabled'], False)

        # Delete downtime
        dog.Downtime.delete(downtime_id)
        dt = dog.Downtime.get(downtime_id)
        eq(dt['disabled'], True)

    @pytest.mark.monitor
    def test_service_check(self):
        dog.ServiceCheck.check(
            check='check_pg', host_name='host0', status=1,
            message='PG is WARNING', tags=['db:prod_data'])

    @pytest.mark.host
    def test_host_muting(self):
        hostname = "my.test.host"
        message = "Muting this host for a test."
        end = int(time.time()) + 60 * 60

        try:
            # reset test
            dog.Host.unmute(hostname)
        except ApiError:
            pass

        # Mute a host
        mute = dog.Host.mute(hostname, end=end, message=message)
        eq(mute['hostname'], hostname)
        eq(mute['action'], "Muted")
        eq(mute['message'], message)
        eq(mute['end'], end)

        # We shouldn't be able to mute a host that's already muted, unless we include
        # the override param.
        end2 = end + 60 * 15
        resp = dog.Host.mute(hostname, end=end2)
        assert resp['errors'][0].startswith('host:my.test.host is already muted.')

        mute = dog.Host.mute(hostname, end=end2, override=True)
        eq(mute['hostname'], hostname)
        eq(mute['action'], "Muted")
        eq(mute['end'], end2)

        dog.Host.unmute(hostname)

    @pytest.mark.embed
    def test_get_all_embeds(self):
        all_embeds = dog.Embed.get_all()
        # Check all embeds is a valid response
        assert "embedded_graphs" in all_embeds

    @pytest.mark.embed
    def test_create_embed(self):
        # Initialize a graph definition
        graph_def = {
            "viz": "toplist",
            "requests": [{
                "q": "top(system.disk.free{$var} by {device}, 10, 'mean', 'desc')",
                "style": {
                    "palette": "dog_classic"
                },
                "conditional_formats": [{
                    "palette": "red",
                    "comparator": ">",
                    "value": 50000000000
                }, {
                    "palette": "green",
                    "comparator": ">",
                    "value": 30000000000
                }]
            }]
        }
        timeframe = "1_hour"
        size = "medium"
        legend = "no"
        title = "Custom titles!"
        # Dump the dictionary to a JSON string and make an API call
        graph_json = json.dumps(graph_def)
        result = dog.Embed.create(graph_json=graph_json, timeframe=timeframe, size=size, legend=legend, title=title)
        # Check various result attributes
        assert "embed_id" in result
        assert result["revoked"] is False
        assert len(result["template_variables"]) == 1
        assert result["template_variables"][0] == "var"
        assert "html" in result
        assert result["graph_title"] == title

    @pytest.mark.embed
    def test_get_embed(self):
        # Create a graph that we can try getting
        graph_def = {
            "viz": "toplist",
            "requests": [{
                "q": "top(system.disk.free{$var} by {device}, 10, 'mean', 'desc')",
                "style": {
                    "palette": "dog_classic"
                },
                "conditional_formats": [{
                    "palette": "red",
                    "comparator": ">",
                    "value": 50000000000
                }, {
                    "palette": "green",
                    "comparator": ">",
                    "value": 30000000000
                }]
            }]
        }
        timeframe = "1_hour"
        size = "medium"
        legend = "no"
        graph_json = json.dumps(graph_def)
        created_graph = dog.Embed.create(graph_json=graph_json, timeframe=timeframe, size=size, legend=legend)
        # Save the html to check against replaced var get
        html = created_graph["html"]
        # Save the embed_id into a variable and get it again
        embed_id = created_graph["embed_id"]
        response_graph = dog.Embed.get(embed_id, var="asdfasdfasdf")
        # Check the graph has the same embed_id and the template_var is added to the url
        assert "embed_id" in response_graph
        assert response_graph["embed_id"] == embed_id
        assert len(response_graph["html"]) > len(html)

    @pytest.mark.embed
    def test_enable_embed(self):
        # Create a graph that we can try getting
        graph_def = {
            "viz": "toplist",
            "requests": [{
                "q": "top(system.disk.free{$var} by {device}, 10, 'mean', 'desc')",
                "style": {
                    "palette": "dog_classic"
                },
                "conditional_formats": [{
                    "palette": "red",
                    "comparator": ">",
                    "value": 50000000000
                }, {
                    "palette": "green",
                    "comparator": ">",
                    "value": 30000000000
                }]
            }]
        }
        timeframe = "1_hour"
        size = "medium"
        legend = "no"
        graph_json = json.dumps(graph_def)
        created_graph = dog.Embed.create(graph_json=graph_json, timeframe=timeframe, size=size, legend=legend)
        # Save the embed_id into a variable and enable it again
        embed_id = created_graph["embed_id"]
        result = dog.Embed.enable(embed_id)
        # Check that the graph is enabled again
        assert "success" in result

    @pytest.mark.embed
    def test_revoke_embed(self):
        # Create a graph that we can try getting
        graph_def = {
            "viz": "toplist",
            "requests": [{
                "q": "top(system.disk.free{$var} by {device}, 10, 'mean', 'desc')",
                "style": {
                    "palette": "dog_classic"
                },
                "conditional_formats": [{
                    "palette": "red",
                    "comparator": ">",
                    "value": 50000000000
                }, {
                    "palette": "green",
                    "comparator": ">",
                    "value": 30000000000
                }]
            }]
        }
        timeframe = "1_hour"
        size = "medium"
        legend = "no"
        graph_json = json.dumps(graph_def)
        created_graph = dog.Embed.create(graph_json=graph_json, timeframe=timeframe, size=size, legend=legend)
        # Save the embed_id into a variable and enable it again
        embed_id = created_graph["embed_id"]
        result = dog.Embed.revoke(embed_id)
        # Check embed is revoked and that we can't get it again
        assert "success" in result
        resp = dog.Embed.get(embed_id)
        eq(
            resp["errors"][0],
            "Embed {} does not exist.".format(embed_id)
        )

    def test_user_crud(self):
        handle = 'user@test.com'
        name = 'Test User'
        alternate_name = 'Test User Alt'
        alternate_email = 'user_alternate@test.com'

        # test create user
        # the user might already exist
        try:
            u = dog.User.create(handle=handle, name=name)
        except ApiError:
            pass

        # reset user to original status
        u = dog.User.update(handle, email=handle, name=name, disabled=False)
        assert u['user']['handle'] == handle
        assert u['user']['name'] == name
        assert u['user']['disabled'] is False

        # test get
        u = dog.User.get(handle)
        assert u['user']['handle'] == handle
        assert u['user']['name'] == name


        # [TODO] You can't update another user's email
        # This is based on who owns the APP key that is making the changes
        # # test update user
        # u = dog.User.update(handle, email=alternate_email, name=alternate_name)
        # assert u['user']['handle'] == handle
        # assert u['user']['name'] == alternate_name
        # assert u['user']['email'] == alternate_email

        # test disable user
        dog.User.delete(handle)
        u = dog.User.get(handle)
        assert u['user']['disabled'] is True

        # test get all users
        u = dog.User.get_all()
        assert len(u['users']) >= 1

    def get_event_with_retry(self, event_id):
        event = dog.Event.get(event_id)
        retry_counter = 0
        while not event.get('event') and retry_counter < 10:
            event = dog.Event.get(event_id)
            retry_counter += 1
            time.sleep(self.wait_time)
        return event

if __name__ == '__main__':
    unittest.main()
