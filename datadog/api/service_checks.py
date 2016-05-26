from datadog.api.constants import CheckStatus
from datadog.api.exceptions import ApiError
from datadog.api.resources import ActionAPIResource


class ServiceCheck(ActionAPIResource):
    """
    A wrapper around ServiceCheck HTTP API.
    """
    @classmethod
    def check(cls, **params):
        """
        Post check statuses for use with monitors

        :param check: text for the message
        :type check: string

        :param host_name: name of the host submitting the check
        :type host_name: string

        :param status: integer for the status of the check
        :type status: Options: '0': OK, '1': WARNING, '2': CRITICAL, '3': UNKNOWN

        :param timestamp: timestamp of the event
        :type timestamp: POSIX timestamp

        :param message: description of why this status occurred
        :type message: string

        :param tags: list of tags for this check
        :type tags: string list

        :returns: JSON response from HTTP request
        """
        if 'status' in params and params['status'] not in CheckStatus.ALL:
            raise ApiError('Invalid status, expected one of: %s'
                           % ', '.join(str(v) for v in CheckStatus.ALL))

        return super(ServiceCheck, cls)._trigger_action('POST', 'check_run', **params)
