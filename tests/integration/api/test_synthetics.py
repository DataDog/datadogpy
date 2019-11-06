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

        # config and options for an API test
        cls.options = {"tick_every": 300}
        cls.config = {
            "assertions": [{"operator": "is", "type": "statusCode", "target": 200}],
            "request": {"method": "GET", "url": "https://example.com", "timeout": 300},
        }

        # config and option for a Browser test
        cls.options_browser = {"device_ids": ["laptop_large"], "tick_every": 900}

        # create an API test
        cls.output = dog.Synthetics.create_test(
            config=cls.config,
            locations=["aws:us-east-2"],
            message="Test API",
            options=cls.options,
            tags=["test:synthetics_api"],
            type="api",
            name="Test with API",
        )

        # create a Browser test
        cls.output_browser = dog.Synthetics.create_test(
            config=cls.config,
            locations=["aws:us-east-2"],
            message="Test Browser",
            options=cls.options_browser,
            tags=["test:synthetics_browser"],
            type="browser",
            name="Test with Browser",
        )

        cls.public_test_id = cls.output["public_id"]
        cls.public_test_id_browser = cls.output_browser["public_id"]

    @classmethod
    def teardown_class(cls):
        # delete all tests present in the account if any
        cls.output_cleanup = dog.Synthetics.get_all_tests()
        cls.public_ids_test_to_delete = []
        for test in cls.output_cleanup["tests"]:
            cls.public_ids_test_to_delete.append(test["public_id"])
        dog.Synthetics.delete_test(public_ids=cls.public_ids_test_to_delete)

    def test_get_update_pause_test(cls):
        # test that both tests are live
        assert len(cls.output) > 1
        assert "public_id" in cls.output
        assert cls.output["status"] == "live"
        assert len(cls.output_browser) > 1
        assert "public_id" in cls.output_browser
        assert cls.output_browser["status"] == "paused"

        # get this newly created tests
        output_api = dog.Synthetics.get_test(id=cls.public_test_id)
        assert "public_id" in output_api
        assert output_api["status"] == "live"
        output_browser = dog.Synthetics.get_test(id=cls.public_test_id_browser)
        assert "public_id" in output_browser
        assert output_browser["status"] == "paused"

        # test that we can retrieve results_ids
        output_api = dog.Synthetics.get_results(id=cls.public_test_id)
        assert output_api["results"] is not None
        output_browser = dog.Synthetics.get_results(id=cls.public_test_id_browser)
        assert output_browser["results"] is not None

        # edit the API test
        cls.options = {"tick_every": 60}
        cls.config["assertions"] = [
            {"operator": "isNot", "type": "statusCode", "target": 404}
        ]

        output = dog.Synthetics.edit_test(
            id=cls.public_test_id,
            config=cls.config,
            type="api",
            locations=["aws:us-west-2"],
            message="Test API edited",
            name="Test with API edited",
            options=cls.options,
            tags=["test:edited"],
        )
        assert "error" not in output
        # test that the new name matches
        assert output["name"] == "Test with API edited"

        # edit the Browser test
        cls.config["assertions"] = [
            {"operator": "isNot", "type": "statusCode", "target": 404}
        ]
        cls.options_browser = {"device_ids": ["tablet"], "tick_every": 1800}

        output = dog.Synthetics.edit_test(
            id=cls.public_test_id,
            config=cls.config,
            type="api",
            locations=["aws:us-west-2"],
            message="Test Browser edited",
            name="Test Browser edited",
            options=cls.options_browser,
            tags=["test:edited"],
        )
        assert "error" not in output
        # test that the new name matches
        assert output["name"] == "Test Browser edited"

        # pause the API test
        output = dog.Synthetics.start_or_pause_test(id=cls.public_test_id, new_status="paused")
        # output is a boolean
        assert output == True

    def test_get_all_tests(self):
        output = dog.Synthetics.get_all_tests()
        # 2 tests were created
        assert len(output["tests"]) == 2

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
