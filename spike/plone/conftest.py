import os
import sys


# Make the throwaway addon importable without packaging it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from emailkit_spike.testing import FUNCTIONAL_TESTING
from emailkit_spike.testing import INTEGRATION_TESTING
from pytest_plone import fixtures_factory


pytest_plugins = ["pytest_plone"]


globals().update(
    fixtures_factory((
        (FUNCTIONAL_TESTING, "functional"),
        (INTEGRATION_TESTING, "integration"),
    ))
)
