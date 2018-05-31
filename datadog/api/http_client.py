"""
Available HTTP Client for Datadog API client.

Priority:
1. `requests` 3p module
2. `urlfetch` 3p module - Google App Engine only
"""
# stdlib
import logging
import urllib

# 3p
try:
    import requests
    import requests.adapters
except ImportError:
    requests = None

try:
    from google.appengine.api import urlfetch, urlfetch_errors
except ImportError:
    urlfetch, urlfetch_errors = None, None

# datadog
from datadog.api.exceptions import ClientError, HTTPError, HttpTimeout


log = logging.getLogger('datadog.api')


def _remove_context(exc):
    """Python3: remove context from chained exceptions to prevent leaking API keys in tracebacks."""
    exc.__cause__ = None
    return exc


class HTTPClient(object):
    """
    An abstract generic HTTP client. Subclasses must implement the `request` methods.
    """
    @classmethod
    def request(cls, method, url, headers, params, data, timeout, proxies, verify, max_retries):
        """
        Main method to be implemented by HTTP clients.

        The returned data structure has the following fields:
        * `content`: string containing the response from the server
        * `status_code`: HTTP status code returned by the server

        Can raise the following exceptions:
        * `ClientError`: server cannot be contacted
        * `HttpTimeout`: connection timed out
        * `HTTPError`: unexpected HTTP response code
        """
        raise NotImplementedError(
            u"Must be implemented by HTTPClient subclasses."
        )


class RequestClient(HTTPClient):
    """
    HTTP client based on 3rd party `requests` module.
    """
    @classmethod
    def request(cls, method, url, headers, params, data, timeout, proxies, verify, max_retries):
        """
        """
        try:
            # Use a session to set a max_retries parameters
            with requests.Session() as s:
                http_adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
                s.mount('https://', http_adapter)

                # Since stream=False we can close the session after this call
                result = s.request(
                    method, url,
                    headers=headers, params=params, data=data,
                    timeout=timeout,
                    proxies=proxies, verify=verify)

                result.raise_for_status()

        except requests.ConnectionError as e:
            raise _remove_context(ClientError(method, url, e))
        except requests.exceptions.Timeout:
            raise _remove_context(HttpTimeout(method, url, timeout))
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (400, 403, 404, 409):
                # This gets caught afterwards and raises an ApiError exception
                pass
            else:
                raise _remove_context(HTTPError(e.response.status_code, result.reason))
        except TypeError as e:
            raise TypeError(
                u"Your installed version of `requests` library seems not compatible with"
                u"Datadog's usage. We recommand upgrading it ('pip install -U requests')."
                u"If you need help or have any question, please contact support@datadoghq.com"
            )

        return result


class URLFetchClient(HTTPClient):
    """
    HTTP client based on Google App Engine `urlfetch` module.
    """
    @classmethod
    def request(cls, method, url, headers, params, data, timeout, proxies, verify, max_retries):
        """
        Wrapper around `urlfetch.fetch` method.

        TO IMPLEMENT:
        * `max_retries`
        """
        # No local certificate file can be used on Google App Engine
        validate_certificate = True if verify else False

        # Encode parameters in the url
        url_with_params = "{url}?{params}".format(
            url=url,
            params=urllib.urlencode(params)
        )

        try:
            result = urlfetch.fetch(
                url=url_with_params,
                method=method,
                headers=headers,
                validate_certificate=validate_certificate,
                deadline=timeout,
                payload=data,
                # setting follow_redirects=False may be slightly faster:
                # https://cloud.google.com/appengine/docs/python/microservice-performance#use_the_shortest_route
                follow_redirects=False
            )

            cls.raise_on_status(result)

        except urlfetch.DownloadError as e:
            raise ClientError(method, url, e)
        except urlfetch_errors.DeadlineExceededError:
            raise HttpTimeout(method, url, timeout)

        return result

    @classmethod
    def raise_on_status(cls, result):
        """
        Raise on HTTP status code errors.
        """
        status_code = result.status_code

        if (status_code / 100) != 2:
            if status_code in (400, 403, 404, 409):
                pass
            else:
                raise HTTPError(status_code)


def resolve_http_client():
    """
    Resolve an appropriate HTTP client based the defined priority and user environment.
    """
    if requests:
        log.debug(u"Use `requests` based HTTP client.")
        return RequestClient

    if urlfetch and urlfetch_errors:
        log.debug(u"Use `urlfetch` based HTTP client.")
        return URLFetchClient

    raise ImportError(
        u"Datadog API client was unable to resolve a HTTP client. "
        u" Please install `requests` library."
    )
