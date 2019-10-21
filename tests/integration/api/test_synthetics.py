import os

from datadog import api as dog
from datadog import initialize

API_KEY = os.environ.get("DD_TEST_CLIENT_API_KEY", "a" * 32)
APP_KEY = os.environ.get("DD_TEST_CLIENT_APP_KEY", "a" * 40)
API_HOST = os.environ.get("DATADOG_HOST")


class TestSynthetics:

    @classmethod
    def setup_class(cls):
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
        
        cls.options_api = {"tick_every": 300}
        cls.config_api = {
            "assertions": [{"operator": "is", "type": "statusCode", "target": 200}],
            "request": {"method": "GET", "url": "https://example.com", "timeout": 300},
        }

        # create a test
        cls.output = dog.Synthetics.create_test(
            config=cls.config_api,
            locations=["aws:us-east-2"],
            message="Test API",
            options=cls.options_api,
            tags=["test:synthetics"],
            type="api",
            name="Test with API"
        )

        cls.public_test_id = cls.output["public_id"]

    @classmethod
    def teardown_class(cls):
        # delete all tests present in the account if any
        cls.output_cleanup = dog.Synthetics.get_all_tests()
        cls.public_ids_test_to_delete = []
        for test in cls.output_cleanup["tests"]:
            cls.public_ids_test_to_delete.append(test["public_id"])
        dog.Synthetics.delete_test(public_ids=cls.public_ids_test_to_delete)

    def test_api_test(cls):
        # test that the test is live
        assert len(cls.output) > 1
        assert "public_id" in cls.output
        assert cls.output["status"] == "live"

        # get this newly created test
        output = dog.Synthetics.get_test(id=cls.public_test_id)
        assert "public_id" in output
        assert output["status"] == "live"

        # test that we can retrieve results_ids
        output = dog.Synthetics.get_results(id=cls.public_test_id)
        assert output["results"] is not None

        # edit the test
        cls.options_api = {"tick_every": 60}
        cls.config_api['assertions'] = [{"operator": "isNot", "type": "statusCode", "target": 404}]

        output = dog.Synthetics.edit_test(id=cls.public_test_id, config=cls.config_api, type='api',
                                          locations=["aws:us-west-2"],
                                          message="Test API edited", name="Test with API edited",
                                          options=cls.options_api, tags=["test:edited"])
        assert "error" not in output
        # test that the new name matches
        assert output["name"] == "Test with API edited"

        # pause the test
        # output = dog.Synthetics.start_or_pause_test(id=public_test_id, new_status="paused")
        # assert output["status"] == "paused"

    def test_get_all_tests(self):
        output = dog.Synthetics.get_all_tests()
        assert len(output) >= 1

    def test_get_locations(self):
        output = dog.Synthetics.get_locations()
        assert len(output) == 1
        # 13 regions
        assert len(output["locations"]) >= 10

    def test_get_devices(self):
        output = dog.Synthetics.get_devices()
        assert len(output) == 1
        # 3 devices
        assert len(output["devices"]) >= 3

    def test_delete_test(cls):
        # delete the test
        output = dog.Synthetics.delete_test(public_ids=[cls.public_test_id])
        assert output["deleted_tests"] is not None
