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

from datadog.api.resources import CreateableAPIResource, UpdatableAPIResource,\
    DeletableAPIResource, GetableAPIResource, ListableAPIResource


class Tag(CreateableAPIResource, UpdatableAPIResource, GetableAPIResource,
          ListableAPIResource, DeletableAPIResource):
    """
    A wrapper around Tag HTTP API.
    """
    _resource_name = 'tags/hosts'

    @classmethod
    def create(cls, host, **body):
        """
        Add tags to a host

        :param tags: list of tags to apply to the host
        :type tags: string list

        :param source: source of the tags
        :type source: string

        :returns: Dictionary representing the API's JSON response
        """
        params = {}
        if 'source' in body:
            params['source'] = body['source']
        return super(Tag, cls).create(id=host, params=params, **body)

    @classmethod
    def update(cls, host, **body):
        """
        Update all tags for a given host

        :param tags: list of tags to apply to the host
        :type tags: string list

        :param source: source of the tags
        :type source: string

        :returns: Dictionary representing the API's JSON response
        """
        params = {}
        if 'source' in body:
            params['source'] = body['source']
        return super(Tag, cls).update(id=host, params=params, **body)
