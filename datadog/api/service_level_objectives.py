from datadog.api.resources import (
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
)


class ServiceLevelObjective(
    GetableAPIResource,
    CreateableAPIResource,
    UpdatableAPIResource,
    ListableAPIResource,
    DeletableAPIResource,
    ActionAPIResource,
):
    """
    A wrapper around Service Level Objective HTTP API.
    """

    _resource_name = "slo"

    @classmethod
    def create(
        cls, attach_host_name=False, method="POST", id=None, params=None, **body
    ):
        """
        Create a SLO

        :returns: created SLO details
        """
        results = super(ServiceLevelObjective, cls).create(
            attach_host_name=False, method="POST", id=None, params=None, **body
        )
        if results["error"]:
            raise Exception(results["error"])
        else:
            return results["data"][0]

    @classmethod
    def get(cls, id, **params):
        """
        Get a specific SLO details.

        :param id: SLO id to get details for
        :type id: str

        :returns: SLO details
        """
        results = super(ServiceLevelObjective, cls).get(id, **params)
        if results["error"]:
            raise Exception(results["error"])
        else:
            return results["data"]

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

        :returns: SLOs matching the query
        """
        search_terms = {}
        if query:
            search_terms["query"] = query
        if ids:
            search_terms["ids"] = ids
        search_terms["offset"] = offset
        search_terms["limit"] = limit

        results = super(ServiceLevelObjective, cls).get_all(**search_terms)
        if results["error"]:
            raise Exception(results["error"])
        else:
            return results["data"]

    @classmethod
    def update(cls, id, params=None, **body):
        """
        Update a specific SLO details.

        :param id: SLO id to update details for
        :type id: str

        :returns: SLO details
        """
        results = super(ServiceLevelObjective, cls).update(id, params, **body)
        if results["error"]:
            raise Exception(results["error"])
        else:
            return results["data"][0]

    @classmethod
    def delete(cls, id, **params):
        """
        Delete a specific SLO.

        :param id: SLO id to delete
        :type id: str

        :returns: SLO ids removed
        """
        results = super(ServiceLevelObjective, cls).delete(id, **params)
        if results["error"]:
            raise Exception(results["error"])
        else:
            return results["data"][0]

    @classmethod
    def bulk_delete(cls, ops):
        """
        Bulk Delete Timeframes from multiple SLOs.

        :param ops: a dictionary mapping of SLO ID to timeframes to remove.
        :type ops: dict(str, list(str))

        :returns: Dictionary representing the API's JSON response
            `errors` - errors with operation
            `data` - updates and deletions
        """
        return super(ServiceLevelObjective, cls)._trigger_class_action(
            "POST", "bulk_delete", body=ops
        )

    @classmethod
    def delete_many(cls, ids, **params):
        """
        Delete Multiple SLOs

        :param ids: a list of SLO IDs to remove
        :type ids: list(str)

        :returns: Dictionary representing the API's JSON response see `data` list(slo ids) && `errors`
        """
        return super(ServiceLevelObjective, cls)._trigger_class_action(
            "DELETE", "", params=params, body={"ids": ids}
        )
