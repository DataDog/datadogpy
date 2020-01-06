# Unless explicitly stated otherwise all files in this repository are licensed under the BSD-3-Clause License.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2015-Present Datadog, Inc
import os
from contextlib import contextmanager


@contextmanager
def preserve_environment_variable(env_name):
    environ_api_param = os.environ.get(env_name)
    try:
        yield
    finally:
        if environ_api_param is not None:
            os.environ[env_name] = environ_api_param
        else:
            del os.environ[env_name]


# Code copied from - https://github.com/DataDog/integrations-core/blob/de1b684e4e98d06a7b0da3249805de74bb877cea/datadog_checks_dev/datadog_checks/dev/structures.py#L24
class EnvVars(dict):
    def __init__(self, env_vars=None, ignore=None):
        super(EnvVars, self).__init__(os.environ)
        self.old_env = dict(self)

        if env_vars is not None:
            self.update(env_vars)

        if ignore is not None:
            for env_var in ignore:
                self.pop(env_var, None)

    def __enter__(self):
        os.environ.clear()
        os.environ.update(self)

    def __exit__(self, exc_type, exc_value, traceback):
        os.environ.clear()
        os.environ.update(self.old_env)
