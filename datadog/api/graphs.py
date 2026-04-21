# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from typing import Any, Dict, Optional

from datadog.util.compat import urlparse
from datadog.api.resources import CreateableAPIResource, ActionAPIResource, GetableAPIResource, ListableAPIResource


class Graph(CreateableAPIResource, ActionAPIResource):
    """
    A wrapper around Graph HTTP API.
    """

    _resource_name = "graph/snapshot"

    @classmethod
    def create(cls, attach_host_name=False, method="GET", id=None, params=None, **body):
        # type: (bool, str, Optional[Any], Optional[Dict[str, Any]], **Any) -> Any
        """
        Take a snapshot of a graph, returning the full url to the snapshot.

        :param metric_query: metric query
        :type metric_query: string query

        :param start: query start timestamp
        :type start: POSIX timestamp

        :param end: query end timestamp
        :type end: POSIX timestamp

        :param event_query: a query that will add event bands to the graph
        :type event_query: string query

        :returns: Dictionary representing the API's JSON response
        """
        return super(Graph, cls).create(method="GET", **body)

    @classmethod
    def status(cls, snapshot_url):
        # type: (str) -> Any
        """
        Returns the status code of snapshot. Can be used to know when the
        snapshot is ready for download.

        :param snapshot_url: snapshot URL to check
        :type snapshot_url: string url

        :returns: Dictionary representing the API's JSON response
        """
        snap_path = urlparse(snapshot_url).path
        snap_path = snap_path.split("/snapshot/view/")[1].split(".png")[0]

        snapshot_status_url = "graph/snapshot_status/{0}".format(snap_path)

        return super(Graph, cls)._trigger_action("GET", snapshot_status_url)


class Embed(ListableAPIResource, GetableAPIResource, ActionAPIResource, CreateableAPIResource):
    """
    A wrapper around Embed HTTP API.
    """

    _resource_name = "graph/embed"

    @classmethod
    def enable(cls, embed_id):
        # type: (str) -> Any
        """
        Enable a specified embed.

        :param embed_id: embed token
        :type embed_id: string embed token

        :returns: Dictionary representing the API's JSON response
        """
        return super(Embed, cls)._trigger_class_action("GET", id=embed_id, action_name="enable")

    @classmethod
    def revoke(cls, embed_id):
        # type: (str) -> Any
        """
        Revoke a specified embed.

        :param embed_id: embed token
        :type embed_id: string embed token

        :returns: Dictionary representing the API's JSON response
        """
        return super(Embed, cls)._trigger_class_action("GET", id=embed_id, action_name="revoke")
