"""Test layers for ``imio.emailkit`` -- shipped in the egg, not in ``tests/``.

Consumer add-ons reuse :data:`FIXTURE` as a base for their own sandbox layer, so
these live inside the distribution as a provided test base class. The
same reasoning puts :func:`install_recording_mailhost` here: every consumer that
sends through the ``Email`` builder needs to assert on queued messages, and the
stock Plone mock cannot tell a queued send from an immediate one (see the long
comment above it).

Two fixtures, on purpose:

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


# ---------------------------------------------------------------------------
# A transaction-honest MailHost stand-in
# ---------------------------------------------------------------------------
#
# Transaction safety is a *guarantee*: "delivery via ``IMailHost`` queued
# send -- an aborted transaction sends nothing", with
# ``.send(immediate=True)`` the only escape, and the test names it explicitly.
#
# The usual Plone test double, ``Products.CMFPlone.tests.utils.MockMailHost``,
# **cannot test that**, and would report a pass no matter what. It overrides
# ``_send`` -- the very method that decides between the transaction-joined path
# and the immediate one:
#
#     if immediate:                       # -> mailer.send() right now
#         self._makeMailer().send(...)
#     else:                               # -> MailDataManager joined to the txn,
#         DirectMailDelivery(...).send()  #    delivered in tpc_finish
#
# Replacing ``_send`` throws that fork away, so the message lands in the mock's
# list immediately and stays there across an abort. A suite built on it cannot
# tell queued from immediate, and "abort -> queue empty" becomes untestable
# while looking tested.
#
# So this double replaces ``_makeMailer`` instead -- one level *below* the fork.
# Everything above stays real Products.MailHost and real zope.sendmail code:
# ``DirectMailDelivery`` joins a ``MailDataManager`` to the current transaction,
# ``tpc_finish`` calls ``mailer.send()`` and ``abort`` calls ``mailer.abort()``.
# Which means the double can assert on all three states a queued mail has --
# pending, delivered, cancelled -- instead of only "something was handed over".


@dataclass(frozen=True)
class SentMail:
    """One message exactly as the SMTP layer received it.

    ``raw`` is what ``Products.MailHost`` serialised (headers munged, ``Bcc``
    stripped) and ``recipients`` is the *envelope*, which is where a dropped
    ``Bcc`` recipient shows up -- it can never appear in the headers.
    """

    sender: str
    recipients: tuple
    raw: bytes

    @property
    def message(self):
        """The parsed message as an ``email.message.EmailMessage``.

        Parsed with ``policy.default`` so headers come back decoded and
        ``iter_attachments`` / ``get_content`` are available: assertions are
        about structure and substituted values, never about the wire bytes.
        """
        return message_from_bytes(self.raw, policy=policy.default)


class RecordingMailer:
    """A ``zope.sendmail`` mailer that records instead of reaching an MTA.

    The three methods are the whole contract ``DirectMailDelivery`` needs --
    ``send`` for ``tpc_finish``, ``vote`` for ``tpc_vote`` and ``abort`` for
    ``MailDataManager.abort``. Counting aborts is what makes the abort test
    a *positive* assertion: an empty inbox proves nothing on its own (a builder
    that never queued anything also has an empty inbox), while
    ``sent == [] and aborted == 1`` proves a delivery was really queued and
    really cancelled.
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
        # Cleared in place, never rebound: tests hold a reference to this list.
        self.sent.clear()
        self.aborted = 0
        self.voted = 0


class RecordingMailHost(MailHost):
    """A real ``MailHost`` whose only fake part is the SMTP connection."""

    #: ``MailBase.smtp_queue`` default, restated because it selects the delivery
    #: strategy: ``False`` means ``DirectMailDelivery``, i.e. joined to the
    #: transaction. ``True`` would write a maildir to ``smtp_queue_directory``
    #: and start a processor thread -- a real queue on disk, not what
    #: "queued send" means here.
    smtp_queue = False

    def __init__(self, identifier="MailHost", mailer=None):
        MailHost.__init__(self, identifier)
        # Volatile on purpose: the double is assigned onto the (persistent)
        # portal, and a test that commits would otherwise pickle the recorded
        # mail into the layer's storage.
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

    Registered *and* set as an attribute, because both lookups are in live use:
    ``getUtility(IMailHost)`` and ``getToolByName(portal, "MailHost")``. Leaving
    either one pointing at the real MailHost would either miss the messages or
    try to open an SMTP connection.

    Nothing is restored: every layer in this package aborts the transaction
    between tests, and the two writes here are both persistent.
    """
    mailhost = RecordingMailHost("MailHost")
    portal.MailHost = mailhost
    manager = getSiteManager(portal)
    manager.unregisterUtility(provided=IMailHost)
    manager.registerUtility(mailhost, provided=IMailHost)
    return mailhost
