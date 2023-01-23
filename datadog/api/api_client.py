# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
# stdlib
import json
import logging
import time
import zlib

# datadog
from datadog.api import _api_version, _max_timeouts, _backoff_period
from datadog.api.exceptions import ClientError, ApiError, HttpBackoff, HttpTimeout, ApiNotInitialized
from datadog.api.http_client import resolve_http_client
from datadog.util.compat import is_p3k
from datadog.util.format import construct_url, normalize_tags


log = logging.getLogger("datadog.api")


class APIClient(object):
    """
    Datadog API client: format and submit API calls to Datadog.
    Embeds a HTTP client.
    """

    # HTTP transport parameters
    _backoff_period = _backoff_period
    _max_timeouts = _max_timeouts
    _backoff_timestamp = None
    _timeout_counter = 0
    _sort_keys = False

    # Plugged HTTP client
    _http_client = None

    @classmethod
    def _get_http_client(cls):
        """
        Getter for the embedded HTTP client.
        """
        if not cls._http_client:
            cls._http_client = resolve_http_client()

        return cls._http_client

    @classmethod
    def submit(
        cls,
        method,
        path,
        api_version=None,
        body=None,
        attach_host_name=False,
        response_formatter=None,
        error_formatter=None,
        suppress_response_errors_on_codes=None,
        compress_payload=False,
        **params
    ):
        """
        Make an HTTP API request

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param path: API endpoint url
        :type path: url

        :param api_version: The API version used

        :param body: dictionary to be sent in the body of the request
        :type body: dictionary

        :param response_formatter: function to format JSON response from HTTP API request
        :type response_formatter: JSON input function

        :param error_formatter: function to format JSON error response from HTTP API request
        :type error_formatter: JSON input function

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param suppress_response_errors_on_codes: suppress ApiError on `errors` key in the response for the given HTTP
                                                  status codes
        :type suppress_response_errors_on_codes: None|list(int)

        :param compress_payload: compress the payload using zlib
        :type compress_payload: bool

        :param params: dictionary to be sent in the query string of the request
        :type params: dictionary

        :returns: JSON or formatted response from HTTP API request
        """
        try:
            # Check if it's ok to submit
            if not cls._should_submit():
                _, backoff_time_left = cls._backoff_status()
                raise HttpBackoff(backoff_time_left)

            # Import API, User and HTTP settings
            from datadog.api import (
                _api_key,
                _application_key,
                _api_host,
                _mute,
                _host_name,
                _proxies,
                _max_retries,
                _timeout,
                _cacert,
                _return_raw_response,
            )

            # Check keys and add then to params
            if _api_key is None:
                raise ApiNotInitialized("API key is not set." " Please run 'initialize' method first.")

            # Set api and app keys in headers
            headers = {}
            headers["DD-API-KEY"] = _api_key
            if _application_key:
                headers["DD-APPLICATION-KEY"] = _application_key

            # Check if the api_version is provided
            if not api_version:
                api_version = _api_version

            # Attach host name to body
            if attach_host_name and body:
                # Is it a 'series' list of objects ?
                if "series" in body:
                    # Adding the host name to all objects
                    for obj_params in body["series"]:
                        if obj_params.get("host", "") == "":
                            obj_params["host"] = _host_name
                else:
                    if body.get("host", "") == "":
                        body["host"] = _host_name

            # If defined, make sure tags are defined as a comma-separated string
            if "tags" in params and isinstance(params["tags"], list):
                tag_list = normalize_tags(params["tags"])
                params["tags"] = ",".join(tag_list)

            # If defined, make sure monitor_ids are defined as a comma-separated string
            if "monitor_ids" in params and isinstance(params["monitor_ids"], list):
                params["monitor_ids"] = ",".join(str(i) for i in params["monitor_ids"])

            # Process the body, if necessary
            if isinstance(body, dict):
                body = json.dumps(body, sort_keys=cls._sort_keys)
                headers["Content-Type"] = "application/json"

            if compress_payload:
                body = zlib.compress(body.encode("utf-8"))
                headers["Content-Encoding"] = "deflate"

            # Construct the URL
            url = construct_url(_api_host, api_version, path)

            # Process requesting
            start_time = time.time()

            result = cls._get_http_client().request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=body,
                timeout=_timeout,
                max_retries=_max_retries,
                proxies=_proxies,
                verify=_cacert,
            )

            # Request succeeded: log it and reset the timeout counter
            duration = round((time.time() - start_time) * 1000.0, 4)
            log.info("%s %s %s (%sms)" % (result.status_code, method, url, duration))
            cls._timeout_counter = 0

            # Format response content
            content = result.content

            if content:
                try:
                    if is_p3k():
                        response_obj = json.loads(content.decode("utf-8"))
                    else:
                        response_obj = json.loads(content)
                except ValueError:
                    raise ValueError("Invalid JSON response: {0}".format(content))

                # response_obj can be a bool and not a dict
                if isinstance(response_obj, dict):
                    if response_obj and "errors" in response_obj:
                        # suppress ApiError when specified and just return the response
                        if not (
                            suppress_response_errors_on_codes
                            and result.status_code in suppress_response_errors_on_codes
                        ):
                            raise ApiError(response_obj)
            else:
                response_obj = None

            if response_formatter is not None:
                response_obj = response_formatter(response_obj)

            if _return_raw_response:
                return response_obj, result
            else:
                return response_obj

        except HttpTimeout:
            cls._timeout_counter += 1
            raise
        except ClientError as e:
            if _mute:
                log.error(str(e))
                if error_formatter is None:
                    return {"errors": e.args[0]}
                else:
                    return error_formatter({"errors": e.args[0]})
            else:
                raise
        except ApiError as e:
            if _mute:
                for error in e.args[0].get("errors") or []:
                    log.error(error)
                if error_formatter is None:
                    return e.args[0]
                else:
                    return error_formatter(e.args[0])
            else:
                raise

    @classmethod
    def _should_submit(cls):
        """
        Returns True if we're in a state where we should make a request
        (backoff expired, no backoff in effect), false otherwise.
        """
        now = time.time()
        should_submit = False

        # If we're not backing off, but the timeout counter exceeds the max
        # number of timeouts, then enter the backoff state, recording the time
        # we started backing off
        if not cls._backoff_timestamp and cls._timeout_counter >= cls._max_timeouts:
            log.info(
                "Max number of datadog timeouts exceeded, backing off for %s seconds",
                cls._backoff_period,
            )
            cls._backoff_timestamp = now
            should_submit = False

        # If we are backing off but the we've waiting sufficiently long enough
        # (backoff_retry_age), exit the backoff state and reset the timeout
        # counter so that we try submitting metrics again
        elif cls._backoff_timestamp:
            backed_off_time, backoff_time_left = cls._backoff_status()
            if backoff_time_left < 0:
                log.info(
                    "Exiting backoff state after %s seconds, will try to submit metrics again",
                    backed_off_time,
                )
                cls._backoff_timestamp = None
                cls._timeout_counter = 0
                should_submit = True
            else:
                log.info(
                    "In backoff state, won't submit metrics for another %s seconds",
                    backoff_time_left,
                )
                should_submit = False
        else:
            should_submit = True

        return should_submit

    @classmethod
    def _backoff_status(cls):
        """
        Get a backoff report, i.e. backoff total and remaining time.
        """
        now = time.time()
        backed_off_time = now - cls._backoff_timestamp
        backoff_time_left = cls._backoff_period - backed_off_time
        return round(backed_off_time, 2), round(backoff_time_left, 2)
