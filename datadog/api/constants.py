# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc


class CheckStatus(object):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3
    ALL = (OK, WARNING, CRITICAL, UNKNOWN)
