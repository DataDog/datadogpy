# stdlib
import logging
import time

# datadog
from datadog.api import _api_version, _max_timeouts, _backoff_period
from datadog.api.exceptions import ClientError, ApiError, HttpBackoff, \
    HttpTimeout, ApiNotInitialized
from datadog.api.http_client import resolve_http_client
from datadog.util.compat import json, is_p3k


log = logging.getLogger('datadog.api')


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
    _api_version = _api_version

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
    def submit(cls, method, path, body=None, attach_host_name=False, response_formatter=None,
               error_formatter=None, **params):
        """
        Make an HTTP API request

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param path: API endpoint url
        :type path: url

        :param body: dictionary to be sent in the body of the request
        :type body: dictionary

        :param response_formatter: function to format JSON response from HTTP API request
        :type response_formatter: JSON input function

        :param error_formatter: function to format JSON error response from HTTP API request
        :type error_formatter: JSON input function

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param params: dictionary to be sent in the query string of the request
        :type params: dictionary

        :returns: JSON or formated response from HTTP API request
        """
        try:
            # Check if it's ok to submit
            if not cls._should_submit():
                _, backoff_time_left = cls._backoff_status()
                raise HttpBackoff(backoff_time_left)

            # Import API, User and HTTP settings
            from datadog.api import _api_key, _application_key, _api_host, \
                _mute, _host_name, _proxies, _max_retries, _timeout, \
                _cacert

            # Check keys and add then to params
            if _api_key is None:
                raise ApiNotInitialized("API key is not set."
                                        " Please run 'initialize' method first.")
            params['api_key'] = _api_key
            if _application_key:
                params['application_key'] = _application_key

            # Attach host name to body
            if attach_host_name and body:
                # Is it a 'series' list of objects ?
                if 'series' in body:
                    # Adding the host name to all objects
                    for obj_params in body['series']:
                        if obj_params.get('host', "") == "":
                            obj_params['host'] = _host_name
                else:
                    if body.get('host', "") == "":
                        body['host'] = _host_name

            # If defined, make sure tags are defined as a comma-separated string
            if 'tags' in params and isinstance(params['tags'], list):
                params['tags'] = ','.join(params['tags'])

            # Process the body, if necessary
            headers = {}
            if isinstance(body, dict):
                body = json.dumps(body)
                headers['Content-Type'] = 'application/json'

            # Construct the URL
            url = "{api_host}/api/{api_version}/{path}".format(
                  api_host=_api_host,
                  api_version=cls._api_version,
                  path=path.lstrip("/"),
            )

            # Process requesting
            start_time = time.time()

            result = cls._get_http_client().request(
                method=method, url=url,
                headers=headers, params=params, data=body,
                timeout=_timeout, max_retries=_max_retries,
                proxies=_proxies, verify=_cacert
            )

            # Request succeeded: log it and reset the timeout counter
            duration = round((time.time() - start_time) * 1000., 4)
            log.info("%s %s %s (%sms)" % (result.status_code, method, url, duration))
            cls._timeout_counter = 0

            # Format response content
            content = result.content

            if content:
                try:
                    if is_p3k():
                        response_obj = json.loads(content.decode('utf-8'))
                    else:
                        response_obj = json.loads(content)
                except ValueError:
                    raise ValueError('Invalid JSON response: {0}'.format(content))

                if response_obj and 'errors' in response_obj:
                    raise ApiError(response_obj)
            else:
                response_obj = None
            if response_formatter is None:
                return response_obj
            else:
                return response_formatter(response_obj)

        except HttpTimeout:
            cls._timeout_counter += 1
            raise
        except ClientError as e:
            if _mute:
                log.error(str(e))
                if error_formatter is None:
                    return {'errors': e.args[0]}
                else:
                    return error_formatter({'errors': e.args[0]})
            else:
                raise
        except ApiError as e:
            if _mute:
                for error in e.args[0]['errors']:
                    log.error(str(error))
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
            log.info("Max number of datadog timeouts exceeded, backing off for {0} seconds"
                     .format(cls._backoff_period))
            cls._backoff_timestamp = now
            should_submit = False

        # If we are backing off but the we've waiting sufficiently long enough
        # (backoff_retry_age), exit the backoff state and reset the timeout
        # counter so that we try submitting metrics again
        elif cls._backoff_timestamp:
            backed_off_time, backoff_time_left = cls._backoff_status()
            if backoff_time_left < 0:
                log.info("Exiting backoff state after {0} seconds, will try to submit metrics again"
                         .format(backed_off_time))
                cls._backoff_timestamp = None
                cls._timeout_counter = 0
                should_submit = True
            else:
                log.info("In backoff state, won't submit metrics for another {0} seconds"
                         .format(backoff_time_left))
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
