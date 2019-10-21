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

    def test_crud_test(self):
        options_api = {"tick_every": 300}
        config_api = {
            "assertions": [{"operator": "is", "type": "statusCode", "target": 200}],
            "request": {"method": "GET", "url": "https://example.com", "timeout": 300},
        }

        # create a test
        output = dog.Synthetics.create_test(
            config=config_api,
            locations=["aws:us-east-2"],
            message="Test API",
            options=options_api,
            tags=["test:synthetics"],
            type="api",
            name="Test with API"
        )

        # test that it is live
        assert len(output) > 1
        assert "public_id" in output
        assert output.get("status") == "live"

        public_test_id = output["public_id"]
        # get this newly created test
        output = dog.Synthetics.get_test(id=public_test_id)
        assert "public_id" in output
        assert output["status"] == "live"

        # test that we can retrieve results_ids
        output = dog.Synthetics.get_results(id=public_test_id)
        assert output["results"] is not None

        # edit the test
        config_api['assertions'] = [{"operator": "isNot", "type": "statusCode", "target": 404}]
        config_api['name'] = "Test with API edited"
        options_api = {"tick_every": 60}

        output = dog.Synthetics.edit_test(id=public_test_id, config=config_api, type='api', locations=["aws:us-west-2"],
                                          message="Test API edited", name="Test with API edited",
                                          options=options_api, tags=["test:edited"])
        assert output is not None

        # pause the test
        # output = dog.Synthetics.pause_test(id=public_test_id, new_status="paused")
        # assert output["status"] == "paused"

        # delete the test
        output = dog.Synthetics.delete_test(public_ids=[public_test_id])
        assert output["deleted_tests"] is not None

    def test_get_all_tests(self):
        output = dog.Synthetics.get_all_tests()
        assert len(output) >= 1

    def test_get_locations(self):
        output = dog.Synthetics.get_locations()
        assert len(output) == 1
        assert len(output["locations"]) >= 10

    def test_get_devices(self):
        output = dog.Synthetics.get_devices()
        assert len(output) == 1
