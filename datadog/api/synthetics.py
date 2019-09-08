from datadog.api.exceptions import ApiError
from datadog.api.resources import CreateableAPIResource, ActionAPIResource, SendableAPIResource


class Synthetics(ActionAPIResource, CreateableAPIResource, SendableAPIResource):
    """
    A wrapper around Sythetics HTTP API.
    """

    _resource_name = 'synthetics'

    @classmethod
    def get_test(cls, id, **params):
        """
        Get test's details.

        :param id: public id of the test to retrieve
        :type id: id

        :returns: Dictionary representing the API's JSON response
        """

        name = 'tests/{}'.format(id)

        return super(Synthetics, cls)._trigger_class_action('GET', name, params=params)

    @classmethod
    def get_all_tests(cls, **params):
        """
        Get all tests' details.

        :param locations: locations to filter the list of tests by
        :type locatons: string list

        :param name: name to filter the list of tests by
        :type name: string

        :param tags: tags to filter the list of tests by scope
        :type tags: string list

        :returns: Dictionary representing the API's JSON response
        """

        for p in ['locations', 'tags']:
            if p in params and isinstance(params[p], list):
                params[p] = ','.join(params[p])

        return super(Synthetics, cls)._trigger_class_action('GET', 'tests', params=params)

    @classmethod
    def get_devices(cls, **params):
        """
        Get a list of devices for browser checks

         :returns: Dictionary representing the API's JSON response
        """

        name = 'browser/devices'

        return super(Synthetics, cls)._trigger_class_action('GET', name, params=params)

    @classmethod
    def get_locations(cls, **params):
        """
        Get a list of all available locations

        :return: Dictionary representing the API's JSON response
        """

        return super(Synthetics, cls)._trigger_class_action('GET', 'locations', params=params)

    @classmethod
    def get_results(cls, id, **params):
        """
        Get the most recent results for a test

        :param id: public id of the test to retrieve results for
        :type id: id

        :return: Dictionary representing the API's JSON response
        """

        name = 'tests/{}/results'.format(id)

        return super(Synthetics, cls)._trigger_class_action('GET', name, params=params)

    @classmethod
    def get_result(cls, id, result_id, **params):
        """
        Get a specific result for a given test.

        :param id: test to retrieve the most recent results for
        :type id: id

        :returns: Dictionary representing the API's JSON response
        """

        name = 'tests/{}/results/{}'.format(id, result_id)

        return super(Synthetics, cls)._trigger_class_action('GET', name, params=params)

    @classmethod
    def create(cls, id='tests', **params):
        """
        Create a test

        :return: Dictionary representing the API's JSON response
        """

        return super(Synthetics, cls).create(id=id, **params)

    @classmethod
    def edit_test(cls, id, **params):
        """
        Edit a test

        :param id: Public id of the test to edit
        :type id: id

        :return: Dictionary representing the API's JSON response
        """

        cls._resource_name = cls._resource_name + '/tests'

        return super(Synthetics, cls).update(id=id, **params)

    @classmethod
    def pause_test(cls, id, **params):
        """
        Pause a given test

        :param id: public id of the test to pause
        :type id: id

        :returns: Dictionary representing the API's JSON response
        """

        name = 'tests/{}/status'.format(id)

        return super(Synthetics, cls)._trigger_class_action('PUT', name, **params)

    @classmethod
    def delete_test(cls, ids, **params):
        """
        Delete a test

        :param ids: list of public IDs to delete corresponding tests
        :type ids: ids

        :return: Dictionary representing the API's JSON response
        """

        if not isinstance(ids, list):
            raise ApiError("Parameter 'ids' must be a list")

        return super(Synthetics, cls).delete(ids=ids)
