import os
import sys


# pytest's `prepend` import mode puts a collected module's own directory on
# `sys.path`, not this one, so bare imports of `support`/`layers`/`sitelayer`
# need this insert.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pytest_plone import fixtures_factory

import inspect
import pytest


# `keep_session=True` (the `pytest_plone` 1.1.0 default) keeps every layer up
# for the whole session, which leaks `imio.emailkit:default` into a `:base`
# site: both stack on the same `PLONE_FIXTURE`, and the opt-out's own guard
# then fails. So this suite opts out. Guarded on the signature: 1.0.0 does
# not take the argument.
_FACTORY_OPTIONS = (
    {"keep_session": False}
    if "keep_session" in inspect.signature(fixtures_factory).parameters
    else {}
)


pytest_plugins = ["pytest_plone"]


# While the runtime is not importable, the layers cannot be constructed.
# Each test module then skips itself through `support.require_runtime()`.
RUNTIME_IMPORT_ERROR = None

try:
    from imio.emailkit.testing import ACCEPTANCE_TESTING
    from imio.emailkit.testing import BASE_FUNCTIONAL_TESTING
    from imio.emailkit.testing import BASE_INTEGRATION_TESTING
    from imio.emailkit.testing import FUNCTIONAL_TESTING
    from imio.emailkit.testing import INTEGRATION_TESTING
    from layers import SENDING_FUNCTIONAL_TESTING
    from layers import SITE_OVERRIDE_INTEGRATION_TESTING
except ImportError as exc:  # pragma: no cover - only before the runtime lands
    RUNTIME_IMPORT_ERROR = exc
else:
    globals().update(
        fixtures_factory(
            (
                (ACCEPTANCE_TESTING, "acceptance"),
                (FUNCTIONAL_TESTING, "functional"),
                (INTEGRATION_TESTING, "integration"),
                (BASE_INTEGRATION_TESTING, "base"),
                (BASE_FUNCTIONAL_TESTING, "base_functional"),
                # Not named "site": collides with
                # `zope.component.hooks.site` in this module.
                (SITE_OVERRIDE_INTEGRATION_TESTING, "site_override"),
                # Functional: a queued send only reaches the MTA at commit
                # time. Includes content types for File/Image attachments.
                (SENDING_FUNCTIONAL_TESTING, "sending"),
            ),
            **_FACTORY_OPTIONS,
        )
    )


@pytest.fixture
def package_name():
    return "imio.emailkit"


@pytest.fixture(scope="session")
def grant_roles():
    """``grant_roles(context, ["Manager"])`` for the default test user.

    Defined here, not taken from ``pytest_plone``: an older Plone can
    resolve a version with no ``grant_roles`` fixture.
    """

    def granter(context, roles):
        from plone import api
        from plone.app.testing import TEST_USER_ID

        api.user.grant_roles(username=TEST_USER_ID, roles=roles, obj=context)

    return granter


# ---------------------------------------------------------------------------
# pytest_plone binds ``portal``/``http_request``/``browser_layers`` to the
# fixture named ``integration``, so the extra layers need their own accessors.
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
    """``make_member(portal)`` -> the test user with a fullname and an address."""

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
    """``layers_of(portal)`` -> the browser layers registered in that portal."""

    def registered(portal):
        from plone.browserlayer.utils import registered_layers
        from zope.component.hooks import site

        with site(portal):
            return registered_layers()

    return registered


# ---------------------------------------------------------------------------
# The ``Email`` builder and its preview view, on the functional ``sending``
# layer (``tests/layers.py``), so a queued send can be committed and read.
# ---------------------------------------------------------------------------


@pytest.fixture
def mail_portal(sending):
    """The portal every builder/preview test sends from."""
    return sending["portal"]


@pytest.fixture
def mail_request(sending):
    return sending["request"]


@pytest.fixture
def mailhost(mail_portal):
    """The recording MailHost serving ``mail_portal``.

    Not ``Products.CMFPlone.tests.utils.MockMailHost``: that stock mock
    cannot distinguish a queued send from an immediate one.
    """
    from imio.emailkit.testing import install_recording_mailhost

    return install_recording_mailhost(mail_portal)


@pytest.fixture
def deliver():
    """Commit, so queued mail is actually handed to the mailer."""
    import transaction

    return transaction.commit


@pytest.fixture
def sent(mailhost):
    """The recorded messages. Empty until ``deliver()`` or an immediate send."""
    return mailhost.sent


@pytest.fixture
def site_sender(mail_portal):
    """Give the site the configured sender ``From`` defaults to."""
    from plone import api

    import support

    api.portal.set_registry_record(
        support.SENDER_ADDRESS_RECORD, support.SITE_SENDER_ADDRESS
    )
    api.portal.set_registry_record(support.SENDER_NAME_RECORD, support.SITE_SENDER_NAME)
    return support.SITE_SENDER_ADDRESS


@pytest.fixture
def set_default_language(mail_portal):
    """``set_default_language("nl")`` -- the fallback for a recipient whose
    ``IEmailRecipient.language`` is ``None``."""
    from plone import api

    import support

    def setter(language):
        api.portal.set_registry_record(support.DEFAULT_LANGUAGE_RECORD, language)
        tool = getattr(mail_portal, "portal_languages", None)
        if tool is not None:
            tool.setDefaultLanguage(language)
        return language

    return setter


@pytest.fixture
def make_recipient_member(mail_portal):
    """``make_recipient_member(support.FR_MEMBER)`` -> a member with a language."""
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
            "the stock `language` member property did not round-trip; "
            "IEmailRecipient.language has no other source for a member"
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
    """The committed fixture data for ``imio.emailkit:notification``."""
    import support

    return support.load_fixture(support.NOTIFICATION)


@pytest.fixture
def mail(mail_portal, mailhost, site_sender, notification_context):
    """``mail()`` -> a fresh ``Email`` for the one registered template.

    Pre-wired with the fixture context, so each test states only the
    recipients/attachments/subject it is about.
    """
    import support

    email_class = support.require_builder()

    def make(**context):
        data = dict(notification_context)
        data.update(context)
        return email_class(support.qualified(support.NOTIFICATION)).with_context(**data)

    return make
