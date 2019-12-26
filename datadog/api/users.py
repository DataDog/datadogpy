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

from datadog.api.resources import ActionAPIResource, GetableAPIResource, \
    CreateableAPIResource, UpdatableAPIResource, ListableAPIResource, \
    DeletableAPIResource


class User(ActionAPIResource, GetableAPIResource, CreateableAPIResource,
           UpdatableAPIResource, ListableAPIResource,
           DeletableAPIResource):

    _resource_name = 'user'

    """
    A wrapper around User HTTP API.
    """
    @classmethod
    def invite(cls, emails):
        """
        Send an invite to join datadog to each of the email addresses in the
        *emails* list. If *emails* is a string, it will be wrapped in a list and
        sent. Returns a list of email addresses for which an email was sent.

        :param emails: emails adresses to invite to join datadog
        :type emails: string list

        :returns: Dictionary representing the API's JSON response
        """
        print("[DEPRECATION] User.invite() is deprecated. Use `create` instead.")

        if not isinstance(emails, list):
            emails = [emails]

        body = {
            'emails': emails,
        }

        return super(User, cls)._trigger_action('POST', '/invite_users', **body)
