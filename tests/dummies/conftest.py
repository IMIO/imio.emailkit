"""Makes the two dummy add-ons discoverable for everything collected under here.

A real consumer add-on is pip-installed, so Zope's autoinclude executes its
``configure.zcml`` at startup and its test suite needs none of this. These two are
not installed -- they are directories in another package's test tree -- so this
conftest puts ``tests/dummies/`` on ``sys.path`` and executes their ZCML through
``imio.emailkit.scan``, into a snapshotted registry.

Autouse and function-scoped: see ``tests/dummyaddons.py`` for why the registration
is scoped rather than global.
"""

import dummyaddons
import pytest


@pytest.fixture(autouse=True)
def dummy_addons_installed():
    with dummyaddons.installed() as addons:
        yield addons
