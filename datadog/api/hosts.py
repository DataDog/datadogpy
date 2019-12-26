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

from datadog.api.resources import ActionAPIResource, SearchableAPIResource


class Host(ActionAPIResource):
    """
    A wrapper around Host HTTP API.
    """
    _resource_name = 'host'

    @classmethod
    def mute(cls, host_name, **body):
        """
        Mute a host.

        :param host_name: hostname
        :type host_name: string

        :param end: timestamp to end muting
        :type end: POSIX timestamp

        :param override: if true and the host is already muted, will override\
         existing end on the host
        :type override: bool

        :param message: message to associate with the muting of this host
        :type message: string

        :returns: Dictionary representing the API's JSON response

        """
        return super(Host, cls)._trigger_class_action('POST', 'mute', host_name, **body)

    @classmethod
    def unmute(cls, host_name):
        """
        Unmute a host.

        :param host_name: hostname
        :type host_name: string

        :returns: Dictionary representing the API's JSON response

        """
        return super(Host, cls)._trigger_class_action('POST', 'unmute', host_name)


class Hosts(ActionAPIResource, SearchableAPIResource):
    """
    A wrapper around Hosts HTTP API.
    """
    _resource_name = 'hosts'

    @classmethod
    def search(cls, **params):
        """
        Search among hosts live within the past 2 hours. Max 100
        results at a time.

        :param filter: query to filter search results
        :type filter: string

        :param sort_field: "status", "apps", "cpu", "iowait", or "load"
        :type sort_field: string

        :param sort_dir: "asc" or "desc"
        :type sort_dir: string

        :param start: host result to start at
        :type start: integer

        :param count: number of host results to return
        :type count: integer

        :returns: Dictionary representing the API's JSOn response

        """
        return super(Hosts, cls)._search(**params)

    @classmethod
    def totals(cls):
        """
        Get total number of hosts active and up.

        :returns: Dictionary representing the API's JSON response
        """
        return super(Hosts, cls)._trigger_class_action('GET', 'totals')
