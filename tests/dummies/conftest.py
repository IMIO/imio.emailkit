"""Makes the two dummy add-ons discoverable for everything collected under here.

These are directories in another package's test tree, not pip-installed, so
this conftest puts them on ``sys.path`` and runs their ZCML itself. See
``tests/dummyaddons.py`` for why the registration is scoped, not global.
"""

import dummyaddons
import pytest


@pytest.fixture(autouse=True)
def dummy_addons_installed():
    with dummyaddons.installed() as addons:
        yield addons
