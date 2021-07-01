# coding: utf8
# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import logging
import unittest

from mock import patch

from datadog.util.compat import conditional_lru_cache, is_higher_py32

class TestConditionalLRUCache(unittest.TestCase):
    def test_normal_usage(self):
        @conditional_lru_cache
        def test_function(some_string, num1, num2, num3):
            return (some_string, num1 + num2 + num3)

        for idx in range(600):
            self.assertEqual(
                test_function("abc", idx, idx*2, idx *3),
                ("abc", idx + idx * 2 + idx *3),
            )

    def test_var_args(self):
        @conditional_lru_cache
        def test_function(*args):
            return sum(list(args))

        args = []
        for idx in range(100):
            args.append(idx)
            self.assertEqual(
                test_function(*args),
                sum(args),
            )

    # pylint: disable=no-self-use
    def test_debug_log(self):
        test_object_logger = logging.getLogger('datadog.util')
        with patch.object(test_object_logger, 'debug') as mock_debug:
            @conditional_lru_cache
            def test_function():
                pass

            test_function()

            if is_higher_py32():
                mock_debug.assert_called_once()
            else:
                mock_debug.assert_not_called()
