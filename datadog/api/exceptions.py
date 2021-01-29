# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
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
        message = (
            u"Could not request {method} {url}: Unable to connect to proxy. "
            u"Please check the proxy configuration and try again.".format(method=method, url=url)
        )
        super(ProxyError, self).__init__(message)


class ClientError(DatadogException):
    """
    HTTP connection to Datadog endpoint is not possible.
    """

    def __init__(self, method, url, exception):
        message = (
            u"Could not request {method} {url}: {exception}. "
            u"Please check the network connection or try again later. "
            u"If the problem persists, please contact support@datadoghq.com".format(
                method=method, url=url, exception=exception
            )
        )
        super(ClientError, self).__init__(message)


class HttpTimeout(DatadogException):
    """
    HTTP connection timeout.
    """

    def __init__(self, method, url, timeout):
        message = (
            u"{method} {url} timed out after {timeout}. "
            u"Please try again later. "
            u"If the problem persists, please contact support@datadoghq.com".format(
                method=method, url=url, timeout=timeout
            )
        )
        super(HttpTimeout, self).__init__(message)


class HttpBackoff(DatadogException):
    """
    Backing off after too many timeouts.
    """

    def __init__(self, backoff_period):
        message = u"Too many timeouts. Won't try again for {backoff_period} seconds. ".format(
            backoff_period=backoff_period
        )
        super(HttpBackoff, self).__init__(message)


class HTTPError(DatadogException):
    """
    Datadog returned a HTTP error.
    """

    def __init__(self, status_code=None, reason=None):
        reason = u" - {reason}".format(reason=reason) if reason else u""
        message = (
            u"Datadog returned a bad HTTP response code: {status_code}{reason}. "
            u"Please try again later. "
            u"If the problem persists, please contact support@datadoghq.com".format(
                status_code=status_code,
                reason=reason,
            )
        )

        super(HTTPError, self).__init__(message)


class ApiError(DatadogException):
    """
    Datadog returned an API error (known HTTPError).

    Matches the following status codes: 400, 401, 403, 404, 409, 429.
    """


class ApiNotInitialized(DatadogException):
    "No API key is set"
