import os
import sys


# ``support``, ``layers`` and the ``sitelayer`` test package are imported by bare
# name from modules in ``tests/`` and ``tests/setup/``. pytest's ``prepend``
# import mode inserts a collected module's basedir on ``sys.path``, but only for
# that directory -- doing it here once is explicit and order independent.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pytest_plone import fixtures_factory

import pytest


pytest_plugins = ["pytest_plone"]


# The Phase 1 runtime (workstream W2: ``discovery.py``, ``render()``,
# ``interfaces.py``, ``profiles/``) is written in parallel with this suite. While
# it is missing, the layers cannot even be constructed -- so tolerate that here
# and let each test module skip itself through ``support.require_runtime()``,
# which prints why. Once the runtime lands this branch is dead code and every
# test runs unchanged.
RUNTIME_IMPORT_ERROR = None

try:
    from imio.emailkit.testing import ACCEPTANCE_TESTING
    from imio.emailkit.testing import BASE_FUNCTIONAL_TESTING
    from imio.emailkit.testing import BASE_INTEGRATION_TESTING
    from imio.emailkit.testing import FUNCTIONAL_TESTING
    from imio.emailkit.testing import INTEGRATION_TESTING
    from layers import SITE_OVERRIDE_INTEGRATION_TESTING
except ImportError as exc:  # pragma: no cover - only before W2 lands
    RUNTIME_IMPORT_ERROR = exc
else:
    globals().update(
        fixtures_factory((
            (ACCEPTANCE_TESTING, "acceptance"),
            (FUNCTIONAL_TESTING, "functional"),
            (INTEGRATION_TESTING, "integration"),
            # SPEC §8.2 level 3: the opt-out profile gets its own layer, because
            # an opt-out nobody exercises is an opt-out nobody notices breaking.
            (BASE_INTEGRATION_TESTING, "base"),
            (BASE_FUNCTIONAL_TESTING, "base_functional"),
            # SPEC §8.2 level 1: a site package's layer extending IEmailkitLayer.
            # Not named "site": that would collide with
            # ``zope.component.hooks.site`` in this module's namespace, and
            # ``globals().update`` would silently win -- the resulting error
            # ("Fixture 'site' called directly") points nowhere near the cause.
            (SITE_OVERRIDE_INTEGRATION_TESTING, "site_override"),
        ))
    )


@pytest.fixture
def package_name():
    return "imio.emailkit"


# ---------------------------------------------------------------------------
# pytest_plone binds ``portal`` / ``http_request`` / ``browser_layers`` to the
# fixture literally named ``integration``, so the two extra layers need their
# own accessors.
# ---------------------------------------------------------------------------


@pytest.fixture
def base_portal(base):
    """The portal of a site with ``imio.emailkit:base`` applied."""
    return base["portal"]


@pytest.fixture
def base_request(base):
    return base["request"]


@pytest.fixture
def site_portal(site_override):
    """The portal of a site that also has a site package's jbot directory."""
    return site_override["portal"]


@pytest.fixture
def site_request(site_override):
    return site_override["request"]


@pytest.fixture
def make_member():
    """``make_member(portal)`` -> the test user with a fullname and an address.

    A factory rather than a fixture so the three layers (``:default``, ``:base``
    and the site-override one) can all use it.
    """

    def make(portal, fullname=None, email=None):
        from plone.app.testing import TEST_USER_ID

        import support

        mtool = portal.portal_membership
        mtool.getMemberById(TEST_USER_ID).setMemberProperties({
            "fullname": fullname or support.MEMBER_FULLNAME,
            "email": email or support.MEMBER_EMAIL,
        })
        return mtool.getMemberById(TEST_USER_ID)

    return make


@pytest.fixture
def layers_of():
    """``layers_of(portal)`` -> the browser layers registered in that portal.

    ``plone.browserlayer.utils.registered_layers`` reads the *current* site, so
    the lookup is wrapped explicitly instead of relying on whichever portal the
    layer happened to leave active.
    """

    def registered(portal):
        from plone.browserlayer.utils import registered_layers
        from zope.component.hooks import site

        with site(portal):
            return registered_layers()

    return registered
