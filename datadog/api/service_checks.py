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

from datadog.api.constants import CheckStatus
from datadog.api.exceptions import ApiError
from datadog.api.resources import ActionAPIResource


class ServiceCheck(ActionAPIResource):
    """
    A wrapper around ServiceCheck HTTP API.
    """
    @classmethod
    def check(cls, **body):
        """
        Post check statuses for use with monitors

        :param check: text for the message
        :type check: string

        :param host_name: name of the host submitting the check
        :type host_name: string

        :param status: integer for the status of the check
        :type status: Options: '0': OK, '1': WARNING, '2': CRITICAL, '3': UNKNOWN

        :param timestamp: timestamp of the event
        :type timestamp: POSIX timestamp

        :param message: description of why this status occurred
        :type message: string

        :param tags: list of tags for this check
        :type tags: string list

        :returns: Dictionary representing the API's JSON response
        """

        # Validate checks, include only non-null values
        for param, value in body.items():
            if param == 'status' and body[param] not in CheckStatus.ALL:
                raise ApiError('Invalid status, expected one of: %s'
                               % ', '.join(str(v) for v in CheckStatus.ALL))

        return super(ServiceCheck, cls)._trigger_action('POST', 'check_run', **body)
