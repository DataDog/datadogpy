# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.resources import SearchableAPIResource


class Infrastructure(SearchableAPIResource):
    """
    A wrapper around Infrastructure HTTP API.
    """

    _resource_name = "search"

    @classmethod
    def search(cls, **params):
        """
        Search for entities in Datadog.

        :param q: a query to search for host and metrics
        :type q: string query

        :returns: Dictionary representing the API's JSON response
        """
        # Deprecate the hosts search param
        query = params.get("q", "").split(":")
        if len(query) > 1 and query[0] == "hosts":
            print("[DEPRECATION] Infrastructure.search() is deprecated for ", "hosts. Use `Hosts.search` instead.")
        return super(Infrastructure, cls)._search(**params)
