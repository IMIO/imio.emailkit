"""Test-only layers, kept out of the shipped ``imio.emailkit.testing``.

Consumers reuse the shipped module, so it must not import from ``tests/``.
The layer needing a test-only package lives here instead.
"""

from imio.emailkit.testing import FIXTURE
from imio.emailkit.testing import Layer as EmailkitLayer
from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer

import sitelayer


class SendingLayer(EmailkitLayer):
    """``imio.emailkit:default`` on a site with the Dexterity content types.

    Not the plain ``FIXTURE``: the builder needs the ``File``/``Image`` FTIs
    for attachment tests, and reading a queued message needs a real
    ``transaction.commit()``, which only a functional layer allows.
    """

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)


SENDING_FIXTURE = SendingLayer()

#: No ``WSGI_SERVER_FIXTURE``: views are exercised through traversal, which
#: also gets a real ``Unauthorized`` instead of a login redirect.
SENDING_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(SENDING_FIXTURE,),
    name="Imio.EmailkitSendingLayer:FunctionalTesting",
)


class SiteOverrideLayer(PloneSandboxLayer):
    """``imio.emailkit:default`` plus a site package's own jbot directory."""

    # Bases on the default-profile fixture, not PLONE_FIXTURE: proves a site
    # layer beats an emailkit override that would otherwise win.
    defaultBases = (FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=sitelayer)


SITE_OVERRIDE_FIXTURE = SiteOverrideLayer()

SITE_OVERRIDE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(SITE_OVERRIDE_FIXTURE,),
    name="Imio.EmailkitSiteOverrideLayer:IntegrationTesting",
)
