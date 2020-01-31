# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""Record HTTP requests to avoid hiting Datadog API from CI."""

import os
import time
from datetime import datetime, timezone

import pytest
from vcr import VCR

from tests.integration.api.constants import API_KEY, APP_KEY, API_HOST

WAIT_TIME = 10
TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}


@pytest.fixture(scope="module")
def api():
    """Initialize Datadog API client."""
    from datadog import api, initialize
    initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
    return api


@pytest.fixture(scope='module')
def vcr_config():
    return dict(
        match_on=('method', 'scheme', 'host', 'port', 'path', 'query', 'body'),
        filter_headers=('DD-API-KEY', 'DD-APPLICATION-KEY'),
        filter_query_parameters=('api_key', 'application_key'),
    )


@pytest.fixture
def freezer(vcr_cassette_name, vcr_cassette, vcr):
    from freezegun import freeze_time

    if vcr_cassette.record_mode == "all":
        tzinfo = datetime.now().astimezone().tzinfo
        freeze_at = datetime.now().replace(tzinfo=tzinfo).isoformat()
        with open(
            os.path.join(
                vcr.cassette_library_dir, vcr_cassette_name + ".frozen"
            ),
            "w",
        ) as f:
            f.write(freeze_at)
    else:
        with open(
            os.path.join(
                vcr.cassette_library_dir, vcr_cassette_name + ".frozen"
            ),
            "r",
        ) as f:
            freeze_at = f.readline().strip()

    return freeze_time(freeze_at)


@pytest.fixture
def dog(api, vcr_cassette):
    """Record communication with Datadog API."""
    yield api


@pytest.fixture
def get_with_retry(vcr_cassette, dog):
    """Return a retry factory that correctly handles the request recording."""

    def retry(
            resource_type,
            resource_id=None,
            operation="get",
            retry_limit=10,
            retry_condition=lambda r: r.get("errors"),
            **kwargs
    ):
        number_of_interactions = len(vcr_cassette.data) if vcr_cassette.record_mode == "all" else -1

        if resource_id is None:
            resource = getattr(getattr(dog, resource_type), operation)(**kwargs)
        else:
            resource = getattr(getattr(dog, resource_type), operation)(resource_id, **kwargs)
        retry_counter = 0
        while retry_condition(resource) and retry_counter < retry_limit:
            time.sleep(WAIT_TIME)

            if vcr_cassette.record_mode == "all":
                # remove failed interactions
                vcr_cassette.data = vcr_cassette.data[:number_of_interactions]

            if resource_id is None:
                resource = getattr(getattr(dog, resource_type), operation)(**kwargs)
            else:
                resource = getattr(getattr(dog, resource_type), operation)(resource_id, **kwargs)
            retry_counter += 1

        if retry_condition(resource):
            raise Exception(
                "Retry limit reached performing `{}` on resource {}, ID {}".format(operation, resource_type, resource_id)
            )
        return resource
    return retry
