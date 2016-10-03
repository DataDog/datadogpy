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
    return open(os.path.join(os.path.dirname(__file__), 'fixtures', '{}'.format(name))).read()
