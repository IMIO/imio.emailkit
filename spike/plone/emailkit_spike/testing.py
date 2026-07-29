from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing.zope import WSGI_SERVER_FIXTURE

import emailkit_spike


class Layer(PloneSandboxLayer):
    # The real PLONE_FIXTURE on purpose: the ``${...}`` interpolation we are
    # testing depends on the IPageTemplateEngine utility that only the full
    # Plone ZCML stack registers.
    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=emailkit_spike)


FIXTURE = Layer()

INTEGRATION_TESTING = IntegrationTesting(
    bases=(FIXTURE,),
    name="EmailkitSpikeLayer:IntegrationTesting",
)

FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE, WSGI_SERVER_FIXTURE),
    name="EmailkitSpikeLayer:FunctionalTesting",
)
