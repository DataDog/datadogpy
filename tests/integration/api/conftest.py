# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""Record HTTP requests to avoid hiting Datadog API from CI."""

import os
import time
from datetime import datetime

import betamax
import pytest

from tests.integration.api.constants import API_KEY, APP_KEY, API_HOST

WAIT_TIME = 10
TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}

RECORD_MODE = os.environ.get("DD_TEST_CLIENT_RECORD_MODE", "none")
"""Allow re-recording of HTTP responses when value 'once' is provided."""

from betamax_serializers import pretty_json

betamax.Betamax.register_serializer(pretty_json.PrettyJSONSerializer)


class RecordAllMatcher(betamax.BaseMatcher):
    """Works well with allow_playback_repeats=False."""

    name = 'record-all'

    def match(self, request, recorded_request):
        return False

betamax.Betamax.register_request_matcher(RecordAllMatcher)


def _placeholders(config, **kwargs):
    """Configure placeholders."""
    for key, value in kwargs.items():
        config.define_cassette_placeholder(key.upper(), value)


MATCHERS = ["method", "path", "body"]
SERIALIZE_WITH = "prettyjson"


with betamax.Betamax.configure() as config:
    config.cassette_library_dir = os.path.join(os.path.dirname(__file__), "cassettes")

    config.default_cassette_options["record_mode"] = RECORD_MODE
    config.default_cassette_options['match_requests_on'] = MATCHERS
    config.default_cassette_options["serialize_with"] = SERIALIZE_WITH
    config.default_cassette_options['allow_playback_repeats'] = False

    _placeholders(config, api_key=API_KEY, app_key=APP_KEY)


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


@pytest.fixture
def recorder(api_session):
    with betamax.Betamax(api_session) as vrc:
        yield vrc


@pytest.fixture
def cassette(request, recorder):
    from freezegun import freeze_time
    from betamax.fixtures.pytest import _casette_name

    cassette_name = _casette_name(request, True)
    recorder.use_cassette(cassette_name)

    if recorder.current_cassette.is_recording():
        recorder.current_cassette.match_options = {RecordAllMatcher.name}

        freeze_at = datetime.now().isoformat()
        with open(
            os.path.join(
                recorder.config.cassette_library_dir, cassette_name + ".frozen"
            ),
            "w",
        ) as f:
            f.write(freeze_at)
    else:
        with open(
            os.path.join(
                recorder.config.cassette_library_dir, cassette_name + ".frozen"
            ),
            "r",
        ) as f:
            freeze_at = f.readline().strip()

    freezer = freeze_time(freeze_at, tick=True)
    freezer.start()

    yield recorder.session

    freezer.stop()


@pytest.fixture
def dog(recorder, cassette):
    """Initialize Datadog API client."""
    from datadog import api, initialize

    if recorder.current_cassette.is_recording():
        initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
    else:
        initialize(api_key='API_KEY', app_key='APP_KEY', api_host=API_HOST)
    yield api


@pytest.fixture
def get_with_retry(recorder, dog):
    """Return a retry factory that correctly handles the request recording."""

    def retry(
            resource_type,
            resource_id=None,
            operation="get",
            retry_limit=10,
            retry_condition=lambda r: r.get("errors"),
            **kwargs
    ):
        cassette = recorder.current_cassette
        number_of_interactions = len(cassette.interactions) if cassette.is_recording() else -1

        if resource_id is None:
            resource = getattr(getattr(dog, resource_type), operation)(**kwargs)
        else:
            resource = getattr(getattr(dog, resource_type), operation)(resource_id, **kwargs)
        retry_counter = 0
        while retry_condition(resource) and retry_counter < retry_limit:
            time.sleep(WAIT_TIME)

            if cassette.is_recording():
                # remove failed interactions
                cassette.interactions = cassette.interactions[:number_of_interactions]

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
