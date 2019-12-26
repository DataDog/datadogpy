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

"""
API & HTTP Clients exceptions.
"""


class DatadogException(Exception):
    """
    Base class for Datadog API exceptions.  Use this for patterns like the following:

        try:
            # do something with the Datadog API
        except datadog.api.exceptions.DatadogException:
            # handle any Datadog-specific exceptions
    """


class ProxyError(DatadogException):
    """
    HTTP connection to the configured proxy server failed.
    """
    def __init__(self, method, url, exception):
        message = u"Could not request {method} {url}: Unable to connect to proxy. "\
                  u"Please check the proxy configuration and try again.".format(
                      method=method, url=url
                  )
        super(ProxyError, self).__init__(message)


class ClientError(DatadogException):
    """
    HTTP connection to Datadog endpoint is not possible.
    """
    def __init__(self, method, url, exception):
        message = u"Could not request {method} {url}: {exception}. "\
                  u"Please check the network connection or try again later. "\
                  u"If the problem persists, please contact support@datadoghq.com".format(
                      method=method, url=url, exception=exception
                  )
        super(ClientError, self).__init__(message)


class HttpTimeout(DatadogException):
    """
    HTTP connection timeout.
    """
    def __init__(self, method, url, timeout):
        message = u"{method} {url} timed out after {timeout}. "\
                  u"Please try again later. "\
                  u"If the problem persists, please contact support@datadoghq.com".format(
                      method=method, url=url, timeout=timeout
                  )
        super(HttpTimeout, self).__init__(message)


class HttpBackoff(DatadogException):
    """
    Backing off after too many timeouts.
    """
    def __init__(self, backoff_period):
        message = u"Too many timeouts. Won't try again for {backoff_period} seconds. ".format(
                  backoff_period=backoff_period)
        super(HttpBackoff, self).__init__(message)


class HTTPError(DatadogException):
    """
    Datadog returned a HTTP error.
    """
    def __init__(self, status_code=None, reason=None):
        reason = u" - {reason}".format(reason=reason) if reason else u""
        message = u"Datadog returned a bad HTTP response code: {status_code}{reason}. "\
                  u"Please try again later. "\
                  u"If the problem persists, please contact support@datadoghq.com".format(
                      status_code=status_code,
                      reason=reason,
                  )

        super(HTTPError, self).__init__(message)


class ApiError(DatadogException):
    """
    Datadog returned an API error (known HTTPError).

    Matches the following status codes: 400, 401, 403, 404, 409, 429.
    """


class ApiNotInitialized(DatadogException):
    "No API key is set"
