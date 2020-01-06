# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
"""
Helper(s), load fixtures.
"""
# stdlib
import os


def load_fixtures(name):
    """
    Load fixtures.

    Args:
        name (string): name of the fixture
    """
    with open(os.path.join(os.path.dirname(__file__), 'fixtures', '{}'.format(name))) as fixture:
        return fixture.read()
