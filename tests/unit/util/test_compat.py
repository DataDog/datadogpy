# coding: utf8
# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import logging
import pytest
import sys
import unittest

from mock import patch

from datadog.util.compat import conditional_lru_cache, is_higher_py32, is_p3k

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

@pytest.mark.skipif(not is_p3k(), reason='Python 3 only')
def test_slow_imports(monkeypatch):
    # We should lazy load certain modules to avoid slowing down the startup
    # time when running in a serverless environment.  This test will fail if
    # any of those modules are imported during the import of datadogpy.

    blocklist = [
        'configparser',
        'email.mime.application',
        'email.mime.multipart',
        'importlib.metadata',
        'importlib_metadata',
        'logging.handlers',
        'multiprocessing',
        'urllib.request',
    ]

    class BlockListFinder:
        def find_spec(self, fullname, *args):
            for lib in blocklist:
                if fullname == lib:
                    raise ImportError('module %s was imported!' % fullname)
            return None
        find_module = find_spec  # Python 2

    monkeypatch.setattr('sys.meta_path', [BlockListFinder()] + sys.meta_path)

    for mod in sys.modules.copy():
        if mod in blocklist or mod.startswith('datadog'):
            del sys.modules[mod]

    import datadog
