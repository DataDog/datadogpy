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
