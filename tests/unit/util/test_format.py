# coding: utf8
# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import unittest

import pytest

from datadog.util.format import construct_url, normalize_tags


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

class TestNormalizeTags:
    """
    Test of the format's `normalize_tags` functionality
    """
    test_data = [
        ([], []),
        ([''],['']),
        (['this is a tag'], ['this_is_a_tag']),
        (['abc!@#$%^&*()0987654321{}}{'], ['abc__________0987654321____']),
        (['abc!@#', '^%$#3456#'], ['abc___', '____3456_']),
        (['mutliple', 'tags', 'included'], ['mutliple', 'tags', 'included']),
        ([u'абвгдежзийкл', u'абв' , 'test123'], [u'абвгдежзийкл', u'абв' , 'test123']),
        ([u'абвгд西😃ежзийкл', u'аб😃西в' , u'a😃😃b'],  [u'абвгд西_ежзийкл', u'аб_西в', u'a__b']),
    ]

    @pytest.mark.parametrize("original_tags,expected_tags", test_data)
    def test_normalize_tags(self, original_tags, expected_tags):
            assert normalize_tags(original_tags) == expected_tags
