# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""Record HTTP requests to avoid hiting Datadog API from CI."""

import os
import time
from datetime import datetime

import pytest
from vcr import VCR

from tests.integration.api.constants import API_KEY, APP_KEY, API_HOST

WAIT_TIME = 10
TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}

RECORD_MODE = os.environ.get("DD_TEST_CLIENT_RECORD_MODE", "none")
"""Allow re-recording of HTTP responses when value 'once' is provided."""


@pytest.fixture
def api_session():
    """Yield fresh API session."""
    import requests
    from datadog.api.api_client import APIClient

    http_client = APIClient._get_http_client()
    http_client._session = requests.Session()
    http_adapter = requests.adapters.HTTPAdapter(max_retries=10)
    http_client._session.mount("https://", http_adapter)

    yield http_client._session

    APIClient._http_client = None


@pytest.fixture(scope='module')
def vcr_config():
    return dict(
        # record_mode=RECORD_MODE,
        filter_headers=('DD-API-KEY', 'DD-APPLICATION-KEY'),
        filter_query_parameters=('api_key', 'application_key'),
        # cassette_library_dir=os.path.join(os.path.dirname(__file__), "cassettes"),
    )


@pytest.fixture
def freezer(vcr_cassette_name, vcr_cassette, vcr):
    from freezegun import freeze_time

    if vcr_cassette.record_mode != "none":
        # ecorder.current_cassette.match_options = {RecordAllMatcher.name}
        freeze_at = datetime.now().isoformat()
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

    return freeze_time(freeze_at)  #, tick=True)


@pytest.fixture()
def dog(vcr_cassette):
    """Initialize Datadog API client."""
    from datadog import api, initialize

    # if not cassette.write_protected:
    initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
    # else:
    #     initialize(api_key='API_KEY', app_key='APP_KEY', api_host=API_HOST)
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
        number_of_interactions = len(vcr_cassette.data) if vcr_cassette.record_mode != "none" else -1

        if resource_id is None:
            resource = getattr(getattr(dog, resource_type), operation)(**kwargs)
        else:
            resource = getattr(getattr(dog, resource_type), operation)(resource_id, **kwargs)
        retry_counter = 0
        while retry_condition(resource) and retry_counter < retry_limit:
            time.sleep(WAIT_TIME)

            if vcr_cassette.record_mode != "none":
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
