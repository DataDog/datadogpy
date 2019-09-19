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
