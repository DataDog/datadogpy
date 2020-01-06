# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import pytest

from datadog.util.format import construct_url


class TestConstructURL:
    expected = "https://api.datadoghq.com/api/v1/graph/snapshot"
    test_data = [
        ("https://api.datadoghq.com", "v1", "graph/snapshot", expected),
        ("https://api.datadoghq.com/", "v1", "graph/snapshot", expected),
        ("https://api.datadoghq.com", "/v1", "graph/snapshot", expected),
        ("https://api.datadoghq.com/", "/v1", "graph/snapshot", expected),
        ("https://api.datadoghq.com", "v1/", "graph/snapshot", expected),
        ("https://api.datadoghq.com/", "v1/", "graph/snapshot", expected),
        ("https://api.datadoghq.com", "/v1/", "graph/snapshot", expected),
        ("https://api.datadoghq.com/", "/v1/", "graph/snapshot", expected),
        ("https://api.datadoghq.com", "v1", "/graph/snapshot", expected),
        ("https://api.datadoghq.com/", "v1", "/graph/snapshot", expected),
        ("https://api.datadoghq.com", "/v1", "/graph/snapshot", expected),
        ("https://api.datadoghq.com/", "/v1", "/graph/snapshot", expected),
        ("https://api.datadoghq.com", "v1/", "/graph/snapshot", expected),
        ("https://api.datadoghq.com/", "v1/", "/graph/snapshot", expected),
        ("https://api.datadoghq.com", "/v1/", "/graph/snapshot", expected),
        ("https://api.datadoghq.com/", "/v1/", "/graph/snapshot", expected),
    ]

    @pytest.mark.parametrize("host,api_version,path,expected", test_data)
    def test_construct_url(self, host, api_version, path, expected):
        assert construct_url(host, api_version, path) == expected
