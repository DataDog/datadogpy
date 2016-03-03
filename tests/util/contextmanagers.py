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
