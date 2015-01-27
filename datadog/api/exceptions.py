""" Module containing all the possible exceptions that datadog can raise.
"""
__all__ = [
    'DatadogException',
    'ClientError',
    'HttpTimeout',
    'HttpBackoff',
    'ApiError',
    'ApiNotInitialized',
]


class DatadogException(Exception):
    pass


class ClientError(DatadogException):
    "When HTTP connection to Datadog endpoint is not possible"


class HttpTimeout(DatadogException):
    "HTTP connection timeout"


class HttpBackoff(DatadogException):
    "Backing off after too many timeouts"


class ApiError(DatadogException):
    "Datadog API is returning an error"


class ApiNotInitialized(DatadogException):
    "No API key is set"
