"""
Available HTTP Client for Datadog API client.

1. Priority to `requests`
2. Fall back to `urlfetch` module on Google App Engine
"""
# stdlib
import logging

# 3p
import requests

# datadog
from datadog.api.exceptions import ClientError, HttpTimeout


log = logging.getLogger('dd.datadogpy')


class HTTPClient(object):
    """
    An abstract generic HTTP client. Subclasses must implement the `request` methods.
    """
    _CORE = NotImplemented

    @classmethod
    def request(cls, method, url, headers, params, data, timeout, proxies, verify, max_retries):
        """
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
        # Use a session to set a max_retries parameters
        s = requests.Session()
        http_adapter = requests.adapters.HTTPAdapter(max_retries=max_retries)
        s.mount('https://', http_adapter)

        try:
            # Request
            result = s.request(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                timeout=timeout,
                proxies=proxies,
                verify=verify)

            # Raise on status
            result.raise_for_status()

        except requests.ConnectionError as e:
            raise ClientError(method, url, e)
        except requests.exceptions.Timeout as e:
            cls._timeout_counter += 1
            raise HttpTimeout(method, url, timeout)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (400, 403, 404, 409):
                # This gets caught afterwards and raises an ApiError exception
                pass
            else:
                raise
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
    pass
