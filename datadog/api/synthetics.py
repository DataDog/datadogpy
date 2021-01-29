# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
from datadog.api.exceptions import ApiError
from datadog.api.resources import (
    CreateableAPIResource,
    GetableAPIResource,
    ActionAPIResource,
    UpdatableAPISyntheticsResource,
    UpdatableAPISyntheticsSubResource,
    ActionAPISyntheticsResource,
)


class Synthetics(
    ActionAPIResource,
    ActionAPISyntheticsResource,
    CreateableAPIResource,
    GetableAPIResource,
    UpdatableAPISyntheticsResource,
    UpdatableAPISyntheticsSubResource,
):
    """
    A wrapper around Sythetics HTTP API.
    """

    _resource_name = "synthetics"
    _sub_resource_name = "status"

    @classmethod
    def get_test(cls, id, **params):
        """
        Get test's details.

        :param id: public id of the test to retrieve
        :type id: string

        :returns: Dictionary representing the API's JSON response
        """

        # API path = "synthetics/tests/<public_test_id>

        name = "tests"

        return super(Synthetics, cls)._trigger_synthetics_class_action("GET", id=id, name=name, params=params)

    @classmethod
    def get_all_tests(cls, **params):
        """
        Get all tests' details.

        :returns: Dictionary representing the API's JSON response
        """

        for p in ["locations", "tags"]:
            if p in params and isinstance(params[p], list):
                params[p] = ",".join(params[p])

        # API path = "synthetics/tests"

        return super(Synthetics, cls).get(id="tests", params=params)

    @classmethod
    def get_devices(cls, **params):
        """
        Get a list of devices for browser checks

        :returns: Dictionary representing the API's JSON response
        """

        # API path = "synthetics/browser/devices"

        name = "browser/devices"

        return super(Synthetics, cls)._trigger_synthetics_class_action("GET", name=name, params=params)

    @classmethod
    def get_locations(cls, **params):
        """
        Get a list of all available locations

        :return: Dictionary representing the API's JSON response
        """

        name = "locations"

        # API path = "synthetics/locations

        return super(Synthetics, cls)._trigger_synthetics_class_action("GET", name=name, params=params)

    @classmethod
    def get_results(cls, id, **params):
        """
        Get the most recent results for a test

        :param id: public id of the test to retrieve results for
        :type id: id

        :return: Dictionary representing the API's JSON response
        """

        # API path = "synthetics/tests/<public_test_id>/results

        path = "tests/{}/results".format(id)

        return super(Synthetics, cls)._trigger_synthetics_class_action("GET", path, params=params)

    @classmethod
    def get_result(cls, id, result_id, **params):
        """
        Get a specific result for a given test.

        :param id: public ID of the test to retrieve the most recent result for
        :type id: id

        :param result_id: result ID of the test to retrieve the most recent result for
        :type result_id: id

        :returns: Dictionary representing the API's JSON response
        """

        # API path = "synthetics/tests/results/<result_id>

        path = "tests/{}/results/{}".format(id, result_id)

        return super(Synthetics, cls)._trigger_synthetics_class_action("GET", path, params=params)

    @classmethod
    def create_test(cls, **params):
        """
        Create a test

        :param name: A unique name for the test
        :type name: string

        :param type: The type of test. Valid values are api and browser
        :type type: string

        :param subtype: required for SSL test - For a SSL API test, specify ssl as the value.
        :Otherwise, you should omit this argument.
        :type subtype: string

        :param config: The test configuration, contains the request specification and the assertions.
        :type config: dict

        :param options: List of options to customize the test
        :type options: dict

        :param message: A description of the test
        :type message: string

        :param locations: A list of the locations to send the tests from
        :type locations: list

        :param tags: A list of tags used to filter the test
        :type tags: list

        :return: Dictionary representing the API's JSON response
        """

        # API path = "synthetics/tests"

        return super(Synthetics, cls).create(id="tests", **params)

    @classmethod
    def edit_test(cls, id, **params):
        """
        Edit a test

        :param id: Public id of the test to edit
        :type id: string

        :return: Dictionary representing the API's JSON response
        """

        # API path = "synthetics/tests/<public_test_id>"

        return super(Synthetics, cls).update_synthetics(id=id, **params)

    @classmethod
    def start_or_pause_test(cls, id, **body):
        """
        Pause a given test

        :param id: public id of the test to pause
        :type id: string

        :param new_status: mew status for the test
        :type id: string

        :returns: Dictionary representing the API's JSON response
        """

        # API path = "synthetics/tests/<public_test_id>/status"

        return super(Synthetics, cls).update_synthetics_items(id=id, **body)

    @classmethod
    def delete_test(cls, **body):
        """
        Delete a test

        :param public_ids: list of public IDs to delete corresponding tests
        :type public_ids: list of strings

        :return: Dictionary representing the API's JSON response
        """

        if not isinstance(body["public_ids"], list):
            raise ApiError("Parameter 'public_ids' must be a list")

        # API path = "synthetics/tests/delete

        return super(Synthetics, cls)._trigger_action("POST", name="synthetics", id="tests/delete", **body)
