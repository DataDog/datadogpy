# Copyright (c) 2010-2020, Datadog <opensource@datadoghq.com>
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from datadog.util.format import force_to_epoch_seconds
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
        return super(ServiceLevelObjective, cls).create(
            attach_host_name=False, method="POST", id=None, params=params, **body
        )

    @classmethod
    def get(cls, id, **params):
        """
        Get a specific SLO details.

        :param id: SLO id to get details for
        :type id: str

        :returns: SLO details
        """
        return super(ServiceLevelObjective, cls).get(id, **params)

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

        return super(ServiceLevelObjective, cls).get_all(**search_terms)

    @classmethod
    def update(cls, id, params=None, **body):
        """
        Update a specific SLO details.

        :param id: SLO id to update details for
        :type id: str

        :returns: SLO details
        """
        return super(ServiceLevelObjective, cls).update(id, params, **body)

    @classmethod
    def delete(cls, id, **params):
        """
        Delete a specific SLO.

        :param id: SLO id to delete
        :type id: str

        :returns: SLO ids removed
        """
        return super(ServiceLevelObjective, cls).delete(id, **params)

    @classmethod
    def bulk_delete(cls, ops, **params):
        """
        Bulk Delete Timeframes from multiple SLOs.

        :param ops: a dictionary mapping of SLO ID to timeframes to remove.
        :type ops: dict(str, list(str))

        :returns: Dictionary representing the API's JSON response
            `errors` - errors with operation
            `data` - updates and deletions
        """
        return super(ServiceLevelObjective, cls)._trigger_class_action(
            "POST",
            "bulk_delete",
            body=ops,
            params=params,
            suppress_response_errors_on_codes=[200],
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
            "DELETE",
            "",
            params=params,
            body={"ids": ids},
            suppress_response_errors_on_codes=[200],
        )

    @classmethod
    def can_delete(cls, ids, **params):
        """
        Check if the following SLOs can be safely deleted.

        This is used to check if SLO has any references to it.

        :param ids: a list of SLO IDs to check
        :type ids: list(str)

        :returns: Dictionary representing the API's JSON response
                  "data.ok" represents a list of SLO ids that have no known references.
                  "errors" contains a dictionary of SLO ID to known reference(s).
        """
        params["ids"] = ids
        return super(ServiceLevelObjective, cls)._trigger_class_action(
            "GET",
            "can_delete",
            params=params,
            body=None,
            suppress_response_errors_on_codes=[200],
        )

    @classmethod
    def history(cls, id, from_ts, to_ts, **params):
        """
        Get the SLO's history from the given time range.

        :param id: SLO ID to query
        :type id: str

        :param from_ts: `from` timestamp in epoch seconds to query
        :type from_ts: int|datetime.datetime

        :param to_ts: `to` timestamp in epoch seconds to query, must be > `from_ts`
        :type to_ts: int|datetime.datetime

        :returns: Dictionary representing the API's JSON response
                  "data.ok" represents a list of SLO ids that have no known references.
                  "errors" contains a dictionary of SLO ID to known reference(s).
        """
        params["id"] = id
        params["from_ts"] = force_to_epoch_seconds(from_ts)
        params["to_ts"] = force_to_epoch_seconds(to_ts)
        return super(ServiceLevelObjective, cls)._trigger_class_action(
            "GET",
            "history",
            id=id,
            params=params,
            body=None,
            suppress_response_errors_on_codes=[200],
        )
