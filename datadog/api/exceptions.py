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
        message = f"Could not request {method} {url}: Unable to connect to proxy. "\
                  f"Please check the proxy configuration and try again."
        super(ProxyError, self).__init__(message)


class ClientError(DatadogException):
    """
    HTTP connection to Datadog endpoint is not possible.
    """
    def __init__(self, method, url, exception):
        message = f"Could not request {method} {url}: {exception}. "\
                  "Please check the network connection or try again later. "\
                  "If the problem persists, please contact support@datadoghq.com"
        super(ClientError, self).__init__(message)


class HttpTimeout(DatadogException):
    """
    HTTP connection timeout.
    """
    def __init__(self, method, url, timeout):
        message = f"{method} {url} timed out after {timeout}. "\
                  "Please try again later. "\
                  "If the problem persists, please contact support@datadoghq.com"
        super(HttpTimeout, self).__init__(message)


class HttpBackoff(DatadogException):
    """
    Backing off after too many timeouts.
    """
    def __init__(self, backoff_period):
        message = f"Too many timeouts. Won't try again for {backoff_period} seconds. "
        super(HttpBackoff, self).__init__(message)


class HTTPError(DatadogException):
    """
    Datadog returned a HTTP error.
    """
    def __init__(self, status_code=None, reason=None):
        reason = f" - {reason}" if reason else ""
        message = f"Datadog returned a bad HTTP response code: {status_code}{reason}. "\
                  "Please try again later. "\
                  "If the problem persists, please contact support@datadoghq.com"

        super(HTTPError, self).__init__(message)


class ApiError(DatadogException):
    """
    Datadog returned an API error (known HTTPError).

    Matches the following status codes: 400, 401, 403, 404, 409, 429.
    """


class ApiNotInitialized(DatadogException):
    "No API key is set"
