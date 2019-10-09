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

    def test_api_test(self):
        """
        create, update and delete an API test
        """

        options_api = {"tick_every": 300}
        config_api = {
            "assertions": [{"operator": "is", "type": "statusCode", "target": 403}],
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
        assert output is not None
        assert len(output) > 1
        assert "public_id" in output
        assert output.get("status") == "live"

        test_id = output.get("public_id")

        # get this newly created test
        output = dog.Synthetics.get_test(id=test_id)
        assert "public_id" in output
        assert output["status"] == "live"

        # test that we can retrieve results_ids
        output = dog.Synthetics.get_results(id=test_id)
        assert output["results"] is not None

        # edit the test
        config_api['assertions'] = [{"operator": "is_not", "type": "statusCode", "target": 404}]
        config_api['name'] = "Test with API edited"

        output = dog.Synthetics.edit_test(test_id, config=config_api)
        assert output is not None

        output = dog.Synthetics.get_locations()
        assert len(output) > 1

        # cleanup
        output = dog.Synthetics.delete_test(public_ids=[test_id])


    def test_browser_test(self):
        """
        create, update and delete an API test
        """

        options_browser = {"device_ids": ["laptop_large"], "tick_every": 3600}
        config_browser = {
            "assertions": [{"operator": "is not", "type": "statusCode", "target": 403}],
            "request": {"method": "GET", "url": "https://example.com", "timeout": 60},
        }

        output = dog.Synthetics.create(
            config=config_browser,
            locations=["aws:us-east-2"],
            message="Test browser",
            options=options_browser,
            tags=["test:synthetics"],
            type="browser",
            name="Test with Browser"
        )

        # test that it is paused
        assert output is not None
        assert len(output) > 1
        assert "public_id" in output
        # the test is paused upon creation
        assert output["status"] == "paused"

        test_id = output.get("public_id")

        # get this newly created test
        output = dog.Synthetics.get_test(id=test_id)
        assert "public_id" in output

        # test that we can retrieve results_ids
        output = dog.Synthetics.get_results(id=test_id)
        assert output["results"] is not None

        # edit the test
        config_browser['assertions'] = [{"operator": "is not", "type": "statusCode", "target": 404}]
        config_browser['name'] = "Test with Browser edited"

        output = dog.Synthetics.edit_test(id=test_id, config=config_browser)
        assert output is not None

        # cleanup
        dog.Synthetics.delete_test(public_ids=[test_id])

    def test_get_locations(self):
        output = dog.Synthetics.get_locations()
        assert output is not None
        assert len(output) == 1

    def test_get_devices(self):
        output = dog.Synthetics.get_devices()
        assert output is not None
        assert len(output) == 1
