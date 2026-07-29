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
    from layers import SENDING_FUNCTIONAL_TESTING
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
            # SPEC §6.2/§6.3: the one layer the Phase 2 tests run on. Functional
            # because a queued send only reaches the MTA at commit time, and
            # content-typed because one attachment source is a Plone File/Image.
            (SENDING_FUNCTIONAL_TESTING, "sending"),
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


# ---------------------------------------------------------------------------
# Phase 2 -- SPEC §6.2's ``Email`` builder and §6.3's preview view
# ---------------------------------------------------------------------------
#
# All of these hang off the ``sending`` layer (``tests/layers.py``), which is
# functional so that a *queued* send can be committed and read. ``pytest_plone``
# binds ``portal``/``http_request`` to the fixture literally named
# ``integration``, so this layer needs its own accessors.


@pytest.fixture
def mail_portal(sending):
    """The portal every SPEC §6.2/§6.3 test sends from."""
    return sending["portal"]


@pytest.fixture
def mail_request(sending):
    return sending["request"]


@pytest.fixture
def mailhost(mail_portal):
    """The recording MailHost serving ``mail_portal``.

    See ``imio.emailkit.testing.install_recording_mailhost`` for why this is not
    ``Products.CMFPlone.tests.utils.MockMailHost``: the stock mock overrides the
    one method that chooses between the queued and the immediate path, so it
    cannot tell the two apart and §6.2's transaction guarantee becomes
    untestable while looking tested.
    """
    from imio.emailkit.testing import install_recording_mailhost

    return install_recording_mailhost(mail_portal)


@pytest.fixture
def deliver():
    """Commit, so queued mail is actually handed to the mailer.

    §6.2's default delivery joins a mail data manager to the transaction and
    hands the message over in ``tpc_finish``. A test that inspects a message
    therefore has to end the transaction -- and doing that through the real
    ``transaction.commit()`` is the point: it is the same code path production
    takes, and it is why these tests live in a functional layer.
    """
    import transaction

    return transaction.commit


@pytest.fixture
def sent(mailhost):
    """The recorded messages. Empty until ``deliver()`` or an immediate send."""
    return mailhost.sent


@pytest.fixture
def site_sender(mail_portal):
    """Give the site the configured sender SPEC §6.2 makes ``From`` default to.

    Set explicitly rather than trusting the test fixture's value: "``From``
    defaults to the site's configured sender" is only testable against a sender
    we know, and ``Products.MailHost`` raises outright on a message with no
    ``From`` -- which would surface as a builder bug rather than as an
    unconfigured site.
    """
    from plone import api

    import support

    api.portal.set_registry_record(
        support.SENDER_ADDRESS_RECORD, support.SITE_SENDER_ADDRESS
    )
    api.portal.set_registry_record(support.SENDER_NAME_RECORD, support.SITE_SENDER_NAME)
    return support.SITE_SENDER_ADDRESS


@pytest.fixture
def set_default_language(mail_portal):
    """``set_default_language("nl")`` -- the site default §6.2's grouping falls
    back to for a recipient whose ``IEmailRecipient.language`` is ``None``
    (``docs/plans/phase-2.md`` §4)."""
    from plone import api

    import support

    def setter(language):
        api.portal.set_registry_record(support.DEFAULT_LANGUAGE_RECORD, language)
        tool = getattr(mail_portal, "portal_languages", None)
        if tool is not None:
            # Belt and braces: which of the two a negotiator reads is not ours
            # to assume, and the tool caches.
            tool.setDefaultLanguage(language)
        return language

    return setter


@pytest.fixture
def make_recipient_member(mail_portal):
    """``make_recipient_member(support.FR_MEMBER)`` -> a member with a language.

    §6.2's ``IEmailRecipient`` carries a "preferred language code"; for a Plone
    member the stock source of that is the ``language`` member property, which
    is what Plone's own "language of the user" negotiator reads. It is asserted
    to round-trip here, so a Plone that stopped shipping the property fails with
    that message instead of as a mysterious grouping bug.
    """
    from plone.app.testing import TEST_USER_PASSWORD

    def make(spec):
        mail_portal.portal_registration.addMember(
            spec["userid"],
            TEST_USER_PASSWORD,
            properties={
                "username": spec["userid"],
                "fullname": spec["fullname"],
                "email": spec["email"],
                "language": spec["language"],
            },
        )
        member = mail_portal.portal_membership.getMemberById(spec["userid"])
        assert member is not None, f"{spec['userid']} was not created"
        assert member.getProperty("email") == spec["email"]
        assert member.getProperty("language") == spec["language"], (
            "the stock `language` member property did not round-trip; SPEC "
            "§6.2's IEmailRecipient.language has no other source for a member"
        )
        return member

    return make


@pytest.fixture
def fr_member(make_recipient_member):
    import support

    return make_recipient_member(support.FR_MEMBER)


@pytest.fixture
def nl_member(make_recipient_member):
    import support

    return make_recipient_member(support.NL_MEMBER)


@pytest.fixture
def notification_context():
    """The committed fixture data for ``imio.emailkit:notification`` (§7)."""
    import support

    return support.load_fixture(support.NOTIFICATION)


@pytest.fixture
def mail(mail_portal, mailhost, site_sender, notification_context):
    """``mail()`` -> a fresh ``Email`` for the one registered template.

    Pre-wired with the §7 fixture context and nothing else, so each test states
    only the recipients/attachments/subject it is about. The MailHost double and
    the site sender are pulled in as dependencies rather than left to each test
    to remember: forgetting the sender raises inside ``Products.MailHost``, and
    forgetting the double would try to open an SMTP connection.
    """
    import support

    email_class = support.require_builder()

    def make(**context):
        data = dict(notification_context)
        data.update(context)
        return email_class(support.qualified(support.NOTIFICATION)).with_context(**data)

    return make
