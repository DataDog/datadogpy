# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Available HTTP Client for Datadog API client.

Priority:
1. `requests` 3p module
2. `urlfetch` 3p module - Google App Engine only
"""
# stdlib
import copy
import logging
import platform
import urllib
from threading import Lock

# 3p
try:
    import requests
    import requests.adapters
except ImportError:
    requests = None  # type: ignore

try:
    from google.appengine.api import urlfetch, urlfetch_errors
except ImportError:
    urlfetch, urlfetch_errors = None, None

try:
    import urllib3  # type: ignore
except ImportError:
    urllib3 = None

# datadog
from datadog.api.exceptions import ProxyError, ClientError, HTTPError, HttpTimeout


log = logging.getLogger("datadog.api")


def _get_user_agent_header():
    from datadog import version

    return "datadogpy/{version} (python {pyver}; os {os}; arch {arch})".format(
        version=version.__version__,
        pyver=platform.python_version(),
        os=platform.system().lower(),
        arch=platform.machine().lower(),
    )


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
        raise NotImplementedError(u"Must be implemented by HTTPClient subclasses.")


class RequestClient(HTTPClient):
    """
    HTTP client based on 3rd party `requests` module, using a single session.
    This allows us to keep the session alive to spare some execution time.
    """

    _session = None
    _session_lock = Lock()

    @classmethod
    def request(cls, method, url, headers, params, data, timeout, proxies, verify, max_retries):
        try:

            with cls._session_lock:
                if cls._session is None:
                    cls._session = requests.Session()
                    http_adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
                    cls._session.mount("https://", http_adapter)
                    cls._session.headers.update({"User-Agent": _get_user_agent_header()})

            result = cls._session.request(
                method, url, headers=headers, params=params, data=data, timeout=timeout, proxies=proxies, verify=verify
            )

            result.raise_for_status()

        except requests.exceptions.ProxyError as e:
            raise _remove_context(ProxyError(method, url, e))
        except requests.ConnectionError as e:
            raise _remove_context(ClientError(method, url, e))
        except requests.exceptions.Timeout:
            raise _remove_context(HttpTimeout(method, url, timeout))
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (400, 401, 403, 404, 409, 429):
                # This gets caught afterwards and raises an ApiError exception
                pass
            else:
                raise _remove_context(HTTPError(e.response.status_code, result.reason))
        except TypeError:
            raise TypeError(
                u"Your installed version of `requests` library seems not compatible with"
                u"Datadog's usage. We recommend upgrading it ('pip install -U requests')."
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
        url_with_params = "{url}?{params}".format(url=url, params=urllib.urlencode(params))
        newheaders = copy.deepcopy(headers)
        newheaders["User-Agent"] = _get_user_agent_header()

        try:
            result = urlfetch.fetch(
                url=url_with_params,
                method=method,
                headers=newheaders,
                validate_certificate=validate_certificate,
                deadline=timeout,
                payload=data,
                # setting follow_redirects=False may be slightly faster:
                # https://cloud.google.com/appengine/docs/python/microservice-performance#use_the_shortest_route
                follow_redirects=False,
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
            if status_code in (400, 401, 403, 404, 409, 429):
                pass
            else:
                raise HTTPError(status_code)


class Urllib3Client(HTTPClient):
    """
    HTTP client based on 3rd party `urllib3` module.
    """

    _pool = None
    _pool_lock = Lock()

    @classmethod
    def request(cls, method, url, headers, params, data, timeout, proxies, verify, max_retries):
        """
        Wrapper around `urllib3.PoolManager.request` method. This method will raise
        exceptions for HTTP status codes that are not 2xx.
        """
        try:
            with cls._pool_lock:
                if cls._pool is None:
                    cls._pool = urllib3.PoolManager(
                        retries=max_retries,
                        timeout=timeout,
                        cert_reqs="CERT_REQUIRED" if verify else "CERT_NONE",
                    )

            newheaders = copy.deepcopy(headers)
            newheaders["User-Agent"] = _get_user_agent_header()
            response = cls._pool.request(
                method, url, body=data, fields=params, headers=newheaders
            )
            cls.raise_on_status(response)

        except urllib3.exceptions.ProxyError as e:
            raise _remove_context(ProxyError(method, url, e))
        except urllib3.exceptions.MaxRetryError as e:
            raise _remove_context(ClientError(method, url, e))
        except urllib3.exceptions.TimeoutError as e:
            raise _remove_context(HttpTimeout(method, url, e))
        except urllib3.exceptions.HTTPError as e:
            raise _remove_context(HTTPError(e))

        return response

    @classmethod
    def raise_on_status(cls, response):
        """
        Raise on HTTP status code errors.
        """
        status_code = response.status
        if status_code < 200 or status_code >= 300:
            if status_code not in (400, 401, 403, 404, 409, 429):
                raise HTTPError(status_code, response.reason)


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

    if urllib3:
        log.debug(u"Use `urllib3` based HTTP client.")
        return Urllib3Client

    raise ImportError(
        u"Datadog API client was unable to resolve a HTTP client. " u" Please install `requests` library."
    )
