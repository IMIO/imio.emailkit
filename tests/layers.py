"""Test-only layers, kept out of the shipped ``imio.emailkit.testing``.

``imio.emailkit.testing`` is part of the egg and consumers reuse it, so it must
not import anything from ``tests/``. The one layer that needs a test-only package
-- the site/client stand-in for a jbot override -- therefore lives here.
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

    The one layer every builder/render test in this suite runs on. Two reasons
    it is not the Phase 1 ``FIXTURE``:

    1. **Content types.** The builder accepts "a Plone File/Image content object" among
       the attachment sources, and there is no way to build one without the
       ``File``/``Image`` FTIs. ``imio.emailkit.testing.Layer`` bases on the bare
       ``PLONE_FIXTURE`` on purpose -- Phase 1 renders against fixture *data*,
       never content -- so the content types come in here rather than being
       charged to every other test's setup. This is exactly the swap
       ``imio.emailkit.testing``'s own docstring recommends to consumers whose
       fixtures carry content objects, so it doubles as a worked example.
    2. **Commits.** ``plone.testing``'s integration lifecycle replaces
       ``transaction.commit`` with a hard error to protect test isolation, and
       the builder's default delivery is *queued*: the message only reaches the MTA in
       the mail data manager's ``tpc_finish``. Reading a queued message
       therefore needs a real commit, which only a functional layer allows -- and
       the alternative, poking at ``transaction.get()._resources`` to run that
       phase by hand, would replace the thing under test with an imitation of it.
    """

    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)


SENDING_FIXTURE = SendingLayer()

#: No ``WSGI_SERVER_FIXTURE``: nothing here browses over HTTP, and a server
#: thread per layer is pure cost. Views are exercised through traversal, which
#: is also the only way to get a real ``Unauthorized`` out of the security
#: machinery rather than a 302 to a login form.
SENDING_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(SENDING_FIXTURE,),
    name="Imio.EmailkitSendingLayer:FunctionalTesting",
)


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
