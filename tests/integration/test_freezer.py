# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc

import datetime


def test_freezer(freezer):
    with freezer:
        assert datetime.datetime.now() == freezer.time_to_freeze
