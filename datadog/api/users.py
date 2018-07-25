from datadog.api.resources import ActionAPIResource, GetableAPIResource, \
    CreateableAPIResource, UpdatableAPIResource, ListableAPIResource, \
    DeletableAPIResource


class User(ActionAPIResource, GetableAPIResource, CreateableAPIResource,
           UpdatableAPIResource, ListableAPIResource,
           DeletableAPIResource):

    _resource_name = 'user'

    """
    A wrapper around User HTTP API.
    """
    @classmethod
    def invite(cls, emails):
        """
        Send an invite to join datadog to each of the email addresses in the
        *emails* list. If *emails* is a string, it will be wrapped in a list and
        sent. Returns a list of email addresses for which an email was sent.

        :param emails: emails adresses to invite to join datadog
        :type emails: string list

        :returns: Dictionary representing the API's JSON response
        """
        print("[DEPRECATION] User.invite() is deprecated. Use `create` instead.")

        if not isinstance(emails, list):
            emails = [emails]

        body = {
            'emails': emails,
        }

        return super(User, cls)._trigger_action('POST', '/invite_users', **body)
