# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from datadog.util.compat import urlparse
from datadog.api.resources import (
    CreateableAPIResource,
    ActionAPIResource,
    GetableAPIResource,
    ListableAPIResource
)


class Graph(CreateableAPIResource, ActionAPIResource):
    """
    A wrapper around Graph HTTP API.
    """
    _resource_name = 'graph/snapshot'

    @classmethod
    def create(cls, **params):
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
        return super(Graph, cls).create(method='GET', **params)

    @classmethod
    def status(cls, snapshot_url):
        """
        Returns the status code of snapshot. Can be used to know when the
        snapshot is ready for download.

        :param snapshot_url: snapshot URL to check
        :type snapshot_url: string url

        :returns: Dictionary representing the API's JSON response
        """
        snap_path = urlparse(snapshot_url).path
        snap_path = snap_path.split('/snapshot/view/')[1].split('.png')[0]

        snapshot_status_url = 'graph/snapshot_status/{0}'.format(snap_path)

        return super(Graph, cls)._trigger_action('GET', snapshot_status_url)


class Embed(ListableAPIResource, GetableAPIResource, ActionAPIResource, CreateableAPIResource):
    """
    A wrapper around Embed HTTP API.
    """
    _resource_name = 'graph/embed'

    @classmethod
    def enable(cls, embed_id):
        """
        Enable a specified embed.

        :param embed_id: embed token
        :type embed_id: string embed token

        :returns: Dictionary representing the API's JSON response
        """
        return super(Embed, cls)._trigger_class_action('GET', id=embed_id, action_name='enable')

    @classmethod
    def revoke(cls, embed_id):
        """
        Revoke a specified embed.

        :param embed_id: embed token
        :type embed_id: string embed token

        :returns: Dictionary representing the API's JSON response
        """
        return super(Embed, cls)._trigger_class_action('GET', id=embed_id,  action_name='revoke')
