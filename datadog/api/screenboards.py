from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, DeletableAPIResource, ActionAPIResource, ListableAPIResource


class Screenboard(GetableAPIResource, CreateableAPIResource,
                  UpdatableAPIResource, DeletableAPIResource,
                  ActionAPIResource, ListableAPIResource):
    """
    A wrapper around Screenboard HTTP API.
    """
    _class_name = 'screen'
    _class_url = '/screen'
    _json_name = 'board'

    @classmethod
    def share(cls, board_id):
        """
        Share the screenboard with given id

        :param board_id: screenboard to share
        :type board_id: id

        :returns: JSON response from HTTP request
        """
        return super(Screenboard, cls)._trigger_action('GET', 'screen/share', board_id)

    @classmethod
    def revoke(cls, board_id):
        """
        Revoke a shared screenboard with given id

        :param board_id: screenboard to revoke
        :type board_id: id

        :returns: JSON response from HTTP request
        """
        return super(Screenboard, cls)._trigger_action('DELETE', 'screen/share', board_id)
