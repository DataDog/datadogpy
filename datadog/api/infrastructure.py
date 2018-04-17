from datadog.api.resources import SearchableAPIResource


class Infrastructure(SearchableAPIResource):
    """
    A wrapper around Infrastructure HTTP API.
    """
    _resource_name = 'search'

    @classmethod
    def search(cls, **params):
        """
        Search for entities in Datadog.

        :param q: a query to serch for host and metrics
        :type q: string query

        :returns: Dictionary representing the API's JSON response
        """
        # Deprecate the hosts search param
        query = params.get('q', '').split(':')
        if len(query) > 1 and query[0] == 'hosts':
            print("[DEPRECATION] Infrastructure.search() is deprecated for ",
                  "hosts. Use `Hosts.search` instead.")
        return super(Infrastructure, cls)._search(**params)
