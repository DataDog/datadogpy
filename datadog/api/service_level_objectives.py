from datadog.api.resources import GetableAPIResource, CreateableAPIResource, \
    UpdatableAPIResource, ListableAPIResource, DeletableAPIResource, \
    ActionAPIResource


class ServiceLevelObjective(GetableAPIResource, CreateableAPIResource, UpdatableAPIResource,
              ListableAPIResource, DeletableAPIResource, ActionAPIResource):
    """
    A wrapper around Service Level Objective HTTP API.
    """
    _resource_name = 'slo'

    @classmethod
    def get_all(cls, query=None, ids=None, offset=0, limit=100, **params):
        """
        Get all SLO details.

        :param query: optional search query - syntax in UI && online documentation
        :type query: str

        :param ids: optional list of SLO ids to get many specific SLOs at once.
        :type ids: list(str)

        :param offset: offset of results to use (default 0)
        :type offset: int

        :param limit: limit of results to return (default: 1000)
        :type limit: int

        :returns: Dictionary representing the API's JSON response
        """
        search_terms = {}
        if query:
            search_terms["query"] = query
        if ids:
            search_terms["ids"] = ids
        search_terms["offset"] = offset
        search_terms["limit"] = limit

        return super(ServiceLevelObjective, cls).get_all(**search_terms)


    @classmethod
    def bulk_delete(cls, ops):
        """
        Bulk Delete Timeframes from multiple SLOs.

        :param ops: a dictionary mapping of SLO ID to timeframes to remove.
        :type ops: dict(str, list(str))

        :returns: Dictionary representing the API's JSON response
        """
        return super(ServiceLevelObjective, cls)._trigger_class_action('POST', 'bulk_delete', body=ops)

    @classmethod
    def delete_many(cls, ids, **params):
        """
        Delete Multiple SLOs

        :param ids: a list of SLO IDs to remove
        :type ids: list(str)

        :returns: Dictionary representing the API's JSON response
        """
        return super(ServiceLevelObjective, cls)._trigger_class_action('DELETE', '', body={"ids": ids})
