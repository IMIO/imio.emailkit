"""Test layers for ``imio.emailkit``, shipped in the egg, not in ``tests/``.

Consumer add-ons reuse :data:`FIXTURE` as their sandbox layer's base.
:data:`BASE_FIXTURE` applies ``imio.emailkit:base`` instead, the runtime
without the restyled Plone default mails.
"""

from dataclasses import dataclass
from email import message_from_bytes
from email import policy
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.testing.zope import WSGI_SERVER_FIXTURE
from Products.MailHost.interfaces import IMailHost
from Products.MailHost.MailHost import MailHost
from zope.component import getSiteManager

import imio.emailkit


class Layer(PloneSandboxLayer):
    """Loads the add-on's ZCML and applies one GenericSetup profile."""

    defaultBases = (PLONE_FIXTURE,)

    #: Profile applied by :meth:`setUpPloneSite`. Subclasses swap it.
    profile = "imio.emailkit:default"

    def setUpZope(self, app, configurationContext):
        # z3c.autoinclude is disabled in PLONE_FIXTURE, so the add-on's own
        # ZCML must be loaded explicitly here, including z3c.jbot's include.
        self.loadZCML(package=imio.emailkit)

    def setUpPloneSite(self, portal):
        applyProfile(portal, self.profile)


class BaseLayer(Layer):
    """Runtime only, without the restyled Plone default mails."""

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


# ---------------------------------------------------------------------------
# A transaction-honest MailHost stand-in
# ---------------------------------------------------------------------------
#
# The stock Plone double, ``MockMailHost``, overrides ``_send`` and so cannot
# tell a queued send from an immediate one: it records the message right
# away, even across an abort. This double replaces ``_makeMailer`` instead,
# one level below that choice, so real Products.MailHost/zope.sendmail code
# still decides between them.


@dataclass(frozen=True)
class SentMail:
    """One message as the SMTP layer received it.

    ``recipients`` is the envelope, the only place a ``Bcc`` recipient shows up.
    """

    sender: str
    recipients: tuple
    raw: bytes

    @property
    def message(self):
        """The parsed message as an ``email.message.EmailMessage``."""
        return message_from_bytes(self.raw, policy=policy.default)


class RecordingMailer:
    """A ``zope.sendmail`` mailer that records instead of reaching an MTA.

    ``sent == [] and aborted == 1`` proves a delivery was queued and
    cancelled, not just that nothing was ever sent.
    """

    def __init__(self):
        self.sent = []
        self.aborted = 0
        self.voted = 0

    def send(self, fromaddr, toaddrs, message):
        self.sent.append(SentMail(fromaddr, tuple(toaddrs), bytes(message)))

    def vote(self, fromaddr, toaddrs, message):
        self.voted += 1

    def abort(self):
        self.aborted += 1

    def reset(self):
        # Cleared in place: tests hold a reference to this list.
        self.sent.clear()
        self.aborted = 0
        self.voted = 0


class RecordingMailHost(MailHost):
    """A real ``MailHost`` whose only fake part is the SMTP connection."""

    #: Selects ``DirectMailDelivery``, joined to the transaction.
    smtp_queue = False

    def __init__(self, identifier="MailHost", mailer=None):
        MailHost.__init__(self, identifier)
        # Volatile: must not pickle recorded mail into the persistent portal.
        self._v_mailer = mailer if mailer is not None else RecordingMailer()

    @property
    def mailer(self):
        mailer = getattr(self, "_v_mailer", None)
        if mailer is None:
            mailer = self._v_mailer = RecordingMailer()
        return mailer

    def _makeMailer(self):
        return self.mailer

    # -- what tests read ---------------------------------------------------

    @property
    def sent(self):
        """Messages actually handed to the MTA, i.e. after a commit."""
        return self.mailer.sent

    @property
    def aborted(self):
        """How many queued deliveries a transaction abort cancelled."""
        return self.mailer.aborted

    def reset(self):
        self.mailer.reset()


def install_recording_mailhost(portal):
    """Swap ``portal``'s MailHost for a :class:`RecordingMailHost`.

    Registered as a utility and set as an attribute: code looks it up both
    ways.
    """
    mailhost = RecordingMailHost("MailHost")
    portal.MailHost = mailhost
    manager = getSiteManager(portal)
    manager.unregisterUtility(provided=IMailHost)
    manager.registerUtility(mailhost, provided=IMailHost)
    return mailhost
