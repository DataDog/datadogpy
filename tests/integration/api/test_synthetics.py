# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

import os

import pytest


class TestSynthetics:

    @pytest.fixture(autouse=True)  # TODO , scope="class"
    def synthetics(self, dog):
        # config and options for an API test
        self.options = {"tick_every": 300}
        self.config = {
            "assertions": [{"operator": "is", "type": "statusCode", "target": 200}],
            "request": {"method": "GET", "url": "https://example.com", "timeout": 30},
        }

        # config and option for a Browser test
        self.options_browser = {"device_ids": ["laptop_large"], "tick_every": 900}

        # create an API test
        self.output = dog.Synthetics.create_test(
            config=self.config,
            locations=["aws:us-east-2"],
            message="Test API",
            options=self.options,
            tags=["test:synthetics_api"],
            type="api",
            name="Test with API",
        )

        # create a Browser test
        self.output_browser = dog.Synthetics.create_test(
            config=self.config,
            locations=["aws:us-east-2"],
            message="Test Browser",
            options=self.options_browser,
            tags=["test:synthetics_browser"],
            type="browser",
            name="Test with Browser",
        )

        self.public_test_id = self.output["public_id"]
        self.public_test_id_browser = self.output_browser["public_id"]

        yield

        # delete all tests present in the account if any
        self.output_cleanup = dog.Synthetics.get_all_tests()
        self.public_ids_test_to_delete = []
        for test in self.output_cleanup["tests"]:
            self.public_ids_test_to_delete.append(test["public_id"])
        dog.Synthetics.delete_test(public_ids=self.public_ids_test_to_delete)

    def test_get_update_pause_test(self, dog):
        # test that both tests are live
        assert len(self.output) > 1
        assert "public_id" in self.output
        assert self.output["status"] == "live"
        assert len(self.output_browser) > 1
        assert "public_id" in self.output_browser
        assert self.output_browser["status"] == "paused"

        # get this newly created tests
        output_api = dog.Synthetics.get_test(id=self.public_test_id)
        assert "public_id" in output_api
        assert output_api["status"] == "live"
        output_browser = dog.Synthetics.get_test(id=self.public_test_id_browser)
        assert "public_id" in output_browser
        assert output_browser["status"] == "paused"

        # test that we can retrieve results_ids
        output_api = dog.Synthetics.get_results(id=self.public_test_id)
        assert output_api["results"] is not None
        output_browser = dog.Synthetics.get_results(id=self.public_test_id_browser)
        assert output_browser["results"] is not None

        # edit the API test
        self.options = {"tick_every": 60}
        self.config["assertions"] = [
            {"operator": "isNot", "type": "statusCode", "target": 404}
        ]

        output = dog.Synthetics.edit_test(
            id=self.public_test_id,
            config=self.config,
            type="api",
            locations=["aws:us-west-2"],
            message="Test API edited",
            name="Test with API edited",
            options=self.options,
            tags=["test:edited"],
        )
        assert "error" not in output
        # test that the new name matches
        assert output["name"] == "Test with API edited"

        # edit the Browser test
        self.config["assertions"] = [
            {"operator": "isNot", "type": "statusCode", "target": 404}
        ]
        self.options_browser = {"device_ids": ["tablet"], "tick_every": 1800}

        output = dog.Synthetics.edit_test(
            id=self.public_test_id,
            config=self.config,
            type="api",
            locations=["aws:us-west-2"],
            message="Test Browser edited",
            name="Test Browser edited",
            options=self.options_browser,
            tags=["test:edited"],
        )
        assert "error" not in output
        # test that the new name matches
        assert output["name"] == "Test Browser edited"

        # pause the API test
        output = dog.Synthetics.start_or_pause_test(id=self.public_test_id, new_status="paused")
        # output is a boolean
        assert output == True

    def test_get_all_tests(self, dog):
        output = dog.Synthetics.get_all_tests()
        # 2 tests were created
        assert len(output["tests"]) >= 2

    def test_get_locations(self, dog):
        output = dog.Synthetics.get_locations()
        assert len(output) == 1
        # 13 regions
        assert len(output["locations"]) >= 10

    def test_get_devices(self, dog):
        output = dog.Synthetics.get_devices()
        assert len(output) == 1
        # 3 devices
        assert len(output["devices"]) >= 3

    def test_delete_test(self, dog):
        # delete the test
        output = dog.Synthetics.delete_test(public_ids=[self.public_test_id])
        assert output["deleted_tests"] is not None
