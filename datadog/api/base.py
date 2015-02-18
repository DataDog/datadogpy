# stdlib
import time
import logging
import requests

# datadog
from datadog.api.exceptions import ClientError, ApiError, HttpBackoff, \
    HttpTimeout, ApiNotInitialized
from datadog.api import _api_version, _timeout, _max_timeouts, _backoff_period
from datadog.util.compat import json, is_p3k

log = logging.getLogger('dd.datadogpy')


class HTTPClient(object):
    """
    HTTP client based on Requests library for Datadog API calls
    """
    # http transport params
    _backoff_period = _backoff_period
    _max_timeouts = _max_timeouts
    _backoff_timestamp = None
    _timeout_counter = 0
    _api_version = _api_version
    _timeout = _timeout

    @classmethod
    def request(cls, method, path, body=None, attach_host_name=False, response_formatter=None,
                error_formatter=None, **params):
        """
        Make an HTTP API request

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param path: API endpoint url
        :type path: url

        :param body: dictionnary to be sent in the body of the request
        :type body: dictionary

        :param response_formatter: function to format JSON response from HTTP API request
        :type response_formatter: JSON input function

        :param error_formatter: function to format JSON error response from HTTP API request
        :type error_formatter: JSON input function

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param params: dictionnary to be sent in the query string of the request
        :type params: dictionary

        :returns: JSON or formated response from HTTP API request
        """

        try:
            # Check if it's ok to submit
            if not cls._should_submit():
                raise HttpBackoff("Too many timeouts. Won't try again for {1} seconds."
                                  .format(*cls._backoff_status()))

            # Import API, User and HTTP settings
            from datadog.api import _api_key, _application_key, _api_host, \
                _swallow, _host_name, _proxies, _max_retries

            # Check keys and add then to params
            if _api_key is None:
                raise ApiNotInitialized("API key is not set."
                                        " Please run 'initialize' method first.")
            params['api_key'] = _api_key
            if _application_key:
                params['application_key'] = _application_key

            # Construct the url
            url = "%s/api/%s/%s" % (_api_host, cls._api_version, path.lstrip("/"))

            # Attach host name to body
            if attach_host_name and body:
                # Is it a 'series' list of objects ?
                if 'series' in body:
                    # Adding the host name to all objects
                    for obj_params in body['series']:
                        if 'host' not in obj_params:
                            obj_params['host'] = _host_name
                else:
                    if 'host' not in body:
                        body['host'] = _host_name

            # If defined, make sure tags are defined as a comma-separated string
            if 'tags' in params and isinstance(params['tags'], list):
                params['tags'] = ','.join(params['tags'])

            # Process the body, if necessary
            headers = {}
            if isinstance(body, dict):
                body = json.dumps(body)
                headers['Content-Type'] = 'application/json'

            # Process requesting
            start_time = time.time()
            try:
                # Use a session to set a max_retries parameters
                s = requests.Session()
                http_adapter = requests.adapters.HTTPAdapter(max_retries=_max_retries)
                s.mount('https://', http_adapter)

                # Request
                result = s.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=body,
                    timeout=cls._timeout,
                    proxies=_proxies)

                result.raise_for_status()
            except requests.ConnectionError as e:
                raise ClientError("Could not request %s %s%s: %s" % (method, _api_host, url, e))
            except requests.exceptions.Timeout as e:
                cls._timeout_counter += 1
                raise HttpTimeout('%s %s timed out after %d seconds.' % (method, url, cls._timeout))
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404 or e.response.status_code == 400:
                    pass
                else:
                    raise
            except TypeError as e:
                raise TypeError(
                    "Your installed version of 'requests' library seems not compatible with"
                    "Datadog's usage. We recommand upgrading it ('pip install -U requests')."
                    "If you need help or have any question, please contact support@datadoghq.com")

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

        except ClientError as e:
            if _swallow:
                log.error(str(e))
                if error_formatter is None:
                    return {'errors': e.args[0]}
                else:
                    return error_formatter({'errors': e.args[0]})
            else:
                raise
        except ApiError as e:
            if _swallow:
                for error in e.args[0]['errors']:
                    log.error(str(error))
                if error_formatter is None:
                    return e.args[0]
                else:
                    return error_formatter(e.args[0])
            else:
                raise

    # Private functions
    @classmethod
    def _should_submit(cls):
        """ Returns True if we're in a state where we should make a request
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
        now = time.time()
        backed_off_time = now - cls._backoff_timestamp
        backoff_time_left = cls._backoff_period - backed_off_time
        return round(backed_off_time, 2), round(backoff_time_left, 2)


# API Resource types are listed below
class CreateableAPIResource(object):
    """
    Creatable API Resource
    """
    @classmethod
    def create(cls, attach_host_name=False, method='POST', id=None, params=None, **body):
        """
        Create a new API resource object

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param id: create a new resource object as a child of the given object
        :type id: id

        :param params: new resource object source
        :type params: dictionary

        :param body: new resource object attributes
        :type body: dictionary

        :returns: JSON response from HTTP API request
        """
        if params is None:
            params = {}
        if method == 'GET':
            return HTTPClient.request('GET', cls._class_url, **body)
        if id is None:
            return HTTPClient.request('POST', cls._class_url, body,
                                      attach_host_name=attach_host_name, **params)
        else:
            return HTTPClient.request('POST', cls._class_url + "/" + str(id), body,
                                      attach_host_name=attach_host_name, **params)


class SendableAPIResource(object):
    """
    Fork of CreateableAPIResource class with different method names
    """
    @classmethod
    def send(cls, attach_host_name=False, id=None, **body):
        """
        Create an API resource object

        :param attach_host_name: link the new resource object to the host name
        :type attach_host_name: bool

        :param id: create a new resource object as a child of the given object
        :type id: id

        :param body: new resource object attributes
        :type body: dictionary

        :returns: JSON response from HTTP API request
        """
        if id is None:
            return HTTPClient.request('POST', cls._class_url, body,
                                      attach_host_name=attach_host_name)
        else:
            return HTTPClient.request('POST', cls._class_url + "/" + str(id), body,
                                      attach_host_name=attach_host_name)


class UpdatableAPIResource(object):
    """
    Updatable API Resource
    """
    @classmethod
    def update(cls, id, params=None, **body):
        """
        Update an API resource object

        :param params: updated resource object source
        :type params: dictionary

        :param body: updated resource object attributes
        :type body: dictionary

        :returns: JSON response from HTTP API request
        """
        if params is None:
            params = {}
        return HTTPClient.request('PUT', cls._class_url + "/" + str(id), body, **params)


class DeletableAPIResource(object):
    """
    Deletable API Resource
    """
    @classmethod
    def delete(cls, id, **params):
        """
        Delete an API resource object

        :param id: resource object to delete
        :type id: id

        :returns: JSON response from HTTP API request
        """
        return HTTPClient.request('DELETE', cls._class_url + "/" + str(id), **params)


class GetableAPIResource(object):
    """
    Getable API Resource
    """
    @classmethod
    def get(cls, id, **params):
        """
        Get information about an API resource object

        :param id: resource object id to retrieve
        :type id: id

        :param params: parameters to filter API resource stream
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        return HTTPClient.request('GET', cls._class_url + "/" + str(id), **params)


class ListableAPIResource(object):
    """
    Listable API Resource
    """
    @classmethod
    def get_all(cls, **params):
        """
        List API resource objects

        :param params: parameters to filter API resource stream
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        return HTTPClient.request('GET', cls._class_url, **params)


class SearchableAPIResource(object):
    """
    Fork of ListableAPIResource class with different method names
    """
    @classmethod
    def _search(cls, **params):
        """
        Query an API resource stream

        :param params: parameters to filter API resource stream
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        return HTTPClient.request('GET', cls._class_url, **params)


class ActionAPIResource(object):
    """
    Actionable API Resource
    """
    @classmethod
    def _trigger_class_action(cls, method, name, id=None, **params):
        """
        Trigger an action

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param name: action name
        :type name: string

        :param id: trigger the action for the specified resource object
        :type id: id

        :param params: action parameters
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        if id is None:
            return HTTPClient.request(method, cls._class_url + "/" + name, params)
        else:
            return HTTPClient.request(method, cls._class_url + "/" + str(id) + "/" + name, params)

    @classmethod
    def _trigger_action(cls, method, name, id=None, **params):
        """
        Trigger an action

        :param method: HTTP method to use to contact API endpoint
        :type method: HTTP method string

        :param name: action name
        :type name: string

        :param id: trigger the action for the specified resource object
        :type id: id

        :param params: action parameters
        :type params: dictionary

        :returns: JSON response from HTTP API request
        """
        if id is None:
            return HTTPClient.request(method, name, params)
        else:
            return HTTPClient.request(method, name + "/" + str(id), params)
