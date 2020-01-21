# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""Record HTTP requests to avoid hiting Datadog API from CI."""

import os

import betamax
import pytest

TEST_USER = os.environ.get("DD_TEST_CLIENT_USER")
API_KEY = os.environ.get("DD_TEST_CLIENT_API_KEY", "a" * 32)
APP_KEY = os.environ.get("DD_TEST_CLIENT_APP_KEY", "a" * 40)
API_HOST = os.environ.get("DATADOG_HOST")
FAKE_PROXY = {"https": "http://user:pass@10.10.1.10:3128/"}

RECORD_MODE = os.environ.get("DD_TEST_CLIENT_RECORD_MODE", "none")
"""Allow re-recording of HTTP responses when value 'once' is provided."""

from betamax_serializers import pretty_json

betamax.Betamax.register_serializer(pretty_json.PrettyJSONSerializer)

def _placeholders(config, **kwargs):
    """Configure placeholders."""
    for key, value in kwargs.items():
        config.define_cassette_placeholder("<{0}>".format(key.upper()), value)

with betamax.Betamax.configure() as config:
    config.cassette_library_dir = os.path.join(
        os.path.dirname(__file__), "cassettes"
    )
    matchers = ["method", "uri", "headers", "body"]
    serialize_with = "prettyjson"

    config.default_cassette_options["record_mode"] = RECORD_MODE
    # betamax_config.default_cassette_options['match_requests_on'] = matchers
    config.default_cassette_options["serialize_with"] = serialize_with

    _placeholders(
        config, api_key=API_KEY, app_key=APP_KEY
    )


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
    from betamax.fixtures.pytest import _casette_name

    recorder.use_cassette(_casette_name(request, True))

    yield recorder.session


@pytest.fixture
def dog(cassette):
    """Initialize Datadog API client."""
    from datadog import api, initialize
    initialize(api_key=API_KEY, app_key=APP_KEY, api_host=API_HOST)
    yield api

