"""Test-only layers, kept out of the shipped ``imio.emailkit.testing``.

``imio.emailkit.testing`` is part of the egg and consumers reuse it, so it must
not import anything from ``tests/``. The one layer that needs a test-only package
-- the site/client stand-in for SPEC §8.2 level 1 -- therefore lives here.
"""

from imio.emailkit.testing import FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer

import sitelayer


class SiteOverrideLayer(PloneSandboxLayer):
    """``imio.emailkit:default`` **plus** a site package's own jbot directory."""

    # Bases on our own default-profile fixture rather than on PLONE_FIXTURE: the
    # point of the test is that a site layer beats an emailkit override that is
    # genuinely installed and would otherwise win.
    defaultBases = (FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=sitelayer)


SITE_OVERRIDE_FIXTURE = SiteOverrideLayer()

SITE_OVERRIDE_INTEGRATION_TESTING = IntegrationTesting(
    bases=(SITE_OVERRIDE_FIXTURE,),
    name="Imio.EmailkitSiteOverrideLayer:IntegrationTesting",
)
