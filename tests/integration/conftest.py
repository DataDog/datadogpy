# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""Record HTTP requests to avoid hiting Datadog API from CI."""

import logging
import os
import time
from datetime import datetime

import pytest
from vcr import VCR
from dateutil import parser

from tests.integration.api.constants import API_KEY, APP_KEY, API_HOST, TEST_USER

WAIT_TIME = 10
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}

logging.basicConfig()
vcr_log = logging.getLogger("vcr")
vcr_log.setLevel(logging.INFO)


@pytest.fixture(scope="module")
def api():
    """Initialize Datadog API client."""
    from datadog import api, initialize
    from datadog.api.api_client import APIClient
    APIClient._sort_keys = True
    initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)

    http_client = APIClient._get_http_client()
    try:
        assert http_client._session is None
        http_client.request(None, None, None, None, None, None, None, None, max_retries=10)
    except Exception as e:
        assert http_client._session is not None

    return api


@pytest.fixture(scope='module')
def vcr_config():
    return dict(
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

    freeze_at = parser.isoparse(freeze_at)

    # dt = parser.isoparse(freeze_at)
    # tz_offset = dt.tzinfo.utcoffset(dt).seconds / 60
    # os.environ['TZ'] =  "UTC%+03d:%02d" % (
    #     int( tz_offset / 60), tz_offset % 60
    # )
    # time.tzset()

    return freeze_time(freeze_at)


@pytest.fixture
def user_handle(vcr_cassette_name, vcr_cassette, vcr):
    if vcr_cassette.record_mode == "all":
        assert TEST_USER is not None, "You must set DD_TEST_CLIENT_USER environment variable to run comment tests"
        handle = TEST_USER
        with open(
            os.path.join(
                vcr.cassette_library_dir, vcr_cassette_name + ".handle"
            ),
            "w",
        ) as f:
            f.write(handle)
    else:
        with open(
            os.path.join(
                vcr.cassette_library_dir, vcr_cassette_name + ".handle"
            ),
            "r",
        ) as f:
            handle = f.readline().strip()

    return handle


@pytest.fixture
def dog(api, vcr_cassette):
    """Record communication with Datadog API."""
    from datadog.util.compat import is_p3k
    if not is_p3k() and vcr_cassette.record_mode != "all":
        pytest.skip("Can not replay responses on Python 2")

    old_host_name = api._host_name
    api._host_name = "test.host"

    yield api

    api._host_name = old_host_name


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
