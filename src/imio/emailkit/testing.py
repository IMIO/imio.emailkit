"""Test layers for ``imio.emailkit`` -- shipped in the egg, not in ``tests/``.

Consumer add-ons reuse :data:`FIXTURE` as a base for their own sandbox layer, so
these live inside the distribution (SPEC §7: "a provided test base class").

Two fixtures, on purpose (SPEC §8.2):

* :data:`FIXTURE` applies ``imio.emailkit:default`` -- the profile that installs
  ``IEmailkitLayer`` and therefore the restyled Plone default mails.
* :data:`BASE_FIXTURE` applies ``imio.emailkit:base`` -- the runtime only. It is
  what proves level 3 of the override story ("opt out entirely"); an opt-out that
  is never exercised is an opt-out nobody knows is broken.

Why ``PLONE_FIXTURE`` and not ``PLONE_APP_CONTENTTYPES_FIXTURE``: Phase 1 renders
templates against fixture *data*, never against content, and the bare Plone
fixture already registers the ``IPageTemplateEngine`` utility that makes
``${...}`` interpolation real rather than verbatim pass-through (Phase 0, caveat
under (a)). Consumers whose fixtures carry content objects should base their own
layer on ``PLONE_APP_CONTENTTYPES_FIXTURE`` instead.

**Deliberately not done here:** this layer does *not* load ``z3c.jbot``'s ZCML
itself. ``PLONE_FIXTURE`` disables ``z3c.autoinclude`` (Phase 0, caveat D1), so
the jbot monkeypatches reach the test run only if ``imio.emailkit``'s own
``configure.zcml`` does ``<include package="z3c.jbot"/>`` -- which is exactly the
line production depends on. Loading jbot from the test layer would paper over a
missing include and turn every override test green for the wrong reason. See
``tests/test_jbot_wiring.py``, which asserts the patches are in place.
"""

from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing.zope import WSGI_SERVER_FIXTURE

import imio.emailkit


class Layer(PloneSandboxLayer):
    """Loads the add-on's ZCML and applies one GenericSetup profile."""

    defaultBases = (PLONE_FIXTURE,)

    #: Profile applied by :meth:`setUpPloneSite`. Subclasses swap it.
    profile = "imio.emailkit:default"

    def setUpZope(self, app, configurationContext):
        # z3c.autoinclude is disabled in the Plone fixture base layer, so the
        # add-on's ZCML has to be loaded explicitly. Everything the add-on needs
        # -- including z3c.jbot's patches -- must come through this one include.
        self.loadZCML(package=imio.emailkit)

    def setUpPloneSite(self, portal):
        applyProfile(portal, self.profile)


class BaseLayer(Layer):
    """``imio.emailkit:base`` -- runtime without the Plone-default overrides."""

    profile = "imio.emailkit:base"


FIXTURE = Layer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name="Imio.EmailkitLayer:IntegrationTesting",
)

FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE, WSGI_SERVER_FIXTURE),
    name="Imio.EmailkitLayer:FunctionalTesting",
)

ACCEPTANCE_TESTING = FunctionalTesting(
    bases=(
        FIXTURE,
        REMOTE_LIBRARY_BUNDLE_FIXTURE,
        WSGI_SERVER_FIXTURE,
    ),
    name="Imio.EmailkitLayer:AcceptanceTesting",
)


BASE_FIXTURE = BaseLayer()

BASE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(BASE_FIXTURE,),
    name="Imio.EmailkitBaseLayer:IntegrationTesting",
)

BASE_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(BASE_FIXTURE, WSGI_SERVER_FIXTURE),
    name="Imio.EmailkitBaseLayer:FunctionalTesting",
)
