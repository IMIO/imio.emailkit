"""The username-reminder mail sent by Plone's login-help form.

The other two default mails are ``z3c.jbot`` overrides, tested in
``test_default_mails.py`` through the stock view. This mail has no stock
template: Plone's version is a hardcoded string in ``login_help.py``, so
``imio.emailkit`` overrides the view instead. This module tests the view
swap, the send, and the anti-enumeration behaviour inherited from stock.
"""

import inspect
import os
import pathlib
import pytest
import support


support.require_runtime()


TEMPLATE = support.GET_USERNAME
QUALIFIED = support.qualified(TEMPLATE)


@pytest.fixture
def marked_request():
    """A fresh request marked with the add-on's browser layer by hand.

    Built fresh, not reused: marking is permanent, and a shared request
    would leak the layer into later tests.
    """
    from imio.emailkit.interfaces import IEmailkitLayer
    from zope.interface import alsoProvides
    from zope.publisher.browser import TestRequest

    request = TestRequest()
    alsoProvides(request, IEmailkitLayer)
    return request


def os_path_of(module):
    return os.path.dirname(module.__file__).replace("\\", "/")


def payload(message):
    """The text and html parts of a sent message, as decoded strings."""
    parts = {}
    for part in message.walk():
        ctype = part.get_content_type()
        if ctype in ("text/plain", "text/html"):
            parts[ctype] = part.get_payload(decode=True).decode(
                part.get_content_charset() or "utf-8"
            )
    return parts


@pytest.fixture
def userinfo(fr_member):
    """A PAS ``searchUsers`` record, built from a real member."""
    return {
        "userid": fr_member.getId(),
        "login": fr_member.getId(),
        "title": fr_member.getProperty("fullname"),
        "email": fr_member.getProperty("email"),
        "pluginid": "source_users",
    }


@pytest.fixture
def subform(mail_portal, mail_request):
    from imio.emailkit.browser.login_help import RequestUsername

    return RequestUsername(None, mail_request)


class TestTheTemplateIsRenderable:
    """Unlike the two jbot mails, this is a normal discovered template, so
    it stays out of ``DEFAULT_MAIL_TEMPLATES``."""

    def test_it_is_registered_for_discovery(self, integration):
        from imio.emailkit.discovery import get_templates

        assert QUALIFIED in get_templates()

    def test_it_renders_through_the_flat_context(self, integration):
        from imio.emailkit import render

        context = support.load_fixture(TEMPLATE)
        html, text = render(QUALIFIED, context=context, language="en")

        assert context["login"] in html
        assert context["login"] in text
        assert context["client_addr"] in html

    def test_the_subject_comes_from_the_registration(self, integration):
        from imio.emailkit.discovery import get_template

        assert get_template(QUALIFIED).subject is not None

    def test_the_plaintext_part_is_the_hand_authored_twin(self, integration):
        """Not the auto-generated fallback: the recipient must read and
        retype this value."""
        from imio.emailkit.discovery import get_template

        template = get_template(QUALIFIED)

        assert template.text_path is not None, "no .txt.pt twin was discovered"
        assert template.text_path.exists()


class TestTheViewSwap:
    """The layer story, on the login-help view rather than on a jbot directory."""

    def test_our_form_wins_on_the_emailkit_layer(self, portal, marked_request):
        from imio.emailkit.browser.login_help import LoginHelpForm
        from zope.component import getMultiAdapter

        view = getMultiAdapter((portal, marked_request), name="login-help")

        assert isinstance(view, LoginHelpForm)

    def test_stock_wins_without_the_layer(self, base_portal):
        """Built fresh, not from a shared fixture: a shared request stays
        marked and would pass this negative control falsely."""
        from imio.emailkit.browser.login_help import LoginHelpForm
        from imio.emailkit.interfaces import IEmailkitLayer
        from zope.component import getMultiAdapter
        from zope.publisher.browser import TestRequest

        request = TestRequest()
        assert not IEmailkitLayer.providedBy(request), (
            "a freshly built request already carries the layer; this negative "
            "control cannot mean anything"
        )

        view = getMultiAdapter((base_portal, request), name="login-help")

        assert not isinstance(view, LoginHelpForm)

    def test_the_form_markup_is_still_plones(self, portal, marked_request):
        """Only the mail is overridden: ``index`` still points at CMFPlone's
        own ``login_help.pt``."""
        from Products.CMFPlone.browser.login import login_help as stock
        from zope.component import getMultiAdapter

        view = getMultiAdapter((portal, marked_request), name="login-help")
        resolved = support.resolved_template(view).filename

        assert resolved.endswith("login_help.pt")
        assert os_path_of(stock) in resolved.replace("\\", "/")


class TestTheMail:
    """The send itself, through the method the view actually calls."""

    def test_it_sends_the_styled_template(
        self, mail_portal, mailhost, site_sender, subform, userinfo, sent
    ):
        subform.send_username(mail_portal, userinfo)

        assert len(sent) == 1
        parts = payload(sent[0].message)
        assert "text/html" in parts, "the styled mail must have an HTML part"
        assert support.A11Y_TABLE_MARKER in parts["text/html"]
        assert userinfo["login"] in parts["text/html"]
        assert userinfo["login"] in parts["text/plain"]

    def test_it_is_not_plones_plaintext_string(
        self, mail_portal, mailhost, site_sender, subform, userinfo, sent
    ):
        """Checks stock's English text, not a msgid, which would pass even
        if the stock template rendered."""
        subform.send_username(mail_portal, userinfo)

        body = sent[0].message.as_string()

        assert "You requested to be reminded of your username" not in body

    def test_the_client_address_reaches_the_mail(
        self, mail_portal, mail_request, mailhost, site_sender, subform, userinfo, sent
    ):
        """Run with no ``X-Forwarded-For`` header, the case that breaks
        stock Plone's expression. ``_client_addr`` is set directly since
        ``getClientAddr`` has no setter.
        """
        assert "HTTP_X_FORWARDED_FOR" not in mail_request.environ
        mail_request._client_addr = "81.240.17.203"

        subform.send_username(mail_portal, userinfo)
        html = payload(sent[0].message)["text/html"]

        assert "81.240.17.203" in html

    def test_it_goes_to_the_member_in_their_own_language(
        self, mail_portal, mailhost, site_sender, subform, userinfo, sent, fr_member
    ):
        """Resolved as a member object, not a userid string, so the member's
        language is also carried."""
        subform.send_username(mail_portal, userinfo)

        message = sent[0].message

        assert fr_member.getProperty("email") in message["To"]
        text = payload(message)["text/plain"]
        assert "You asked to be reminded" not in text


class TestClientAddressSemantics:
    """Why the login-help mails read ``getClientAddr``, not the header
    chain: stock Plone's TAL fallback (``|``) only triggers on an
    exception, but ``HTTPRequest.get`` returns ``''`` for a missing key
    instead of raising, so the ``REMOTE_ADDR`` fallback never runs.
    """

    @staticmethod
    def request_with(**extra):
        from ZPublisher.HTTPRequest import HTTPRequest
        from ZPublisher.HTTPResponse import HTTPResponse

        import io

        environ = {
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "REQUEST_METHOD": "GET",
            "REMOTE_ADDR": "10.1.2.3",
        }
        environ.update(extra)
        return HTTPRequest(io.BytesIO(b""), environ, HTTPResponse())

    def test_a_missing_forwarded_header_reads_as_empty_string(self):
        """``''``, not a ``KeyError``."""
        request = self.request_with()

        assert request.get("HTTP_X_FORWARDED_FOR") == ""
        assert request["HTTP_X_FORWARDED_FOR"] == ""

    def test_get_client_addr_falls_back_where_the_chain_cannot(self):
        request = self.request_with()

        assert request.getClientAddr() == "10.1.2.3"

    def test_the_templates_do_not_use_the_broken_chain(self):
        """Reads the compiled ``.pt`` files, since that is what production
        renders."""
        import imio.emailkit

        package = pathlib.Path(imio.emailkit.__file__).parent
        files = [
            package / "templates" / f"{TEMPLATE}.pt",
            package / "templates" / f"{support.MAIL_PASSWORD}.pt",
        ]

        for path in files:
            body = path.read_text(encoding="utf-8")
            assert "HTTP_X_FORWARDED_FOR" not in body, (
                f"{path.name} still reads the forwarded header directly; it renders "
                f"empty when the header is absent"
            )


class TestAntiEnumeration:
    """The form must not reveal which addresses are registered: an unknown
    address sends nothing but still reports success, like stock Plone."""

    def test_an_unknown_address_sends_nothing(
        self, mail_portal, mail_request, mailhost, site_sender, sent
    ):
        from imio.emailkit.browser.login_help import RequestUsername

        form = RequestUsername(None, mail_request)
        submit(mail_request, "nobody-here@example.invalid")
        form.update()

        assert sent == []

    def test_a_known_address_sends_one_mail(
        self, mail_portal, mail_request, mailhost, site_sender, sent, fr_member
    ):
        """Driven through the button handler, not ``send_username`` directly."""
        from imio.emailkit.browser.login_help import RequestUsername

        form = RequestUsername(None, mail_request)
        submit(mail_request, fr_member.getProperty("email"))
        form.update()

        assert len(sent) == 1
        html = payload(sent[0].message)["text/html"]
        assert fr_member.getId() in html

    def test_both_outcomes_report_the_same_thing(
        self, mail_portal, mail_request, mailhost, site_sender, fr_member
    ):
        from imio.emailkit.browser.login_help import RequestUsername
        from Products.statusmessages.interfaces import IStatusMessage

        messages = []
        for address in (fr_member.getProperty("email"), "nobody@example.invalid"):
            form = RequestUsername(None, mail_request)
            submit(mail_request, address)
            form.update()
            shown = IStatusMessage(mail_request).show()
            messages.append([(m.message, m.type) for m in shown])

        assert messages[0] == messages[1], (
            "the known and unknown address produced different status messages; "
            "the form is now an oracle for registered addresses"
        )


def submit(request, address):
    """Fill in a login-help username submission."""
    request.form.clear()
    request.form.update({
        "form.widgets.recover_username": address,
        "form.buttons.get_username": "Get your username",
    })
    return request


class TestReachability:
    """``use_email_as_login`` decides whether this mail exists: stock hides
    the username subform when it is on."""

    @pytest.fixture
    def form(self, mail_portal, mail_request):
        from imio.emailkit.browser.login_help import LoginHelpForm

        view = LoginHelpForm(mail_portal, mail_request)
        view.request = mail_request
        return view

    @pytest.fixture(autouse=True)
    def restore_login_setting(self, mail_portal):
        """A record left flipped would break other tests' expectations."""
        from plone import api

        before = api.portal.get_registry_record("plone.use_email_as_login")
        yield
        api.portal.set_registry_record("plone.use_email_as_login", before)

    def _set(self, value):
        from plone import api

        api.portal.set_registry_record("plone.use_email_as_login", value)

    def test_the_subform_is_present_with_userid_login(self, form):
        from imio.emailkit.browser.login_help import RequestUsername

        self._set(False)
        form.update()

        assert any(isinstance(sub, RequestUsername) for sub in form.subforms)

    def test_the_subform_is_absent_with_email_as_login(self, form):
        from imio.emailkit.browser.login_help import RequestUsername

        self._set(True)
        form.update()

        assert not any(isinstance(sub, RequestUsername) for sub in form.subforms)


class TestUpstreamDrift:
    """Guards against drift in the upstream ``update()`` this fork depends
    on. If this fails, re-fork ``update()`` in
    ``imio/emailkit/browser/login_help.py`` and update these assertions.
    """

    def test_stock_update_is_what_we_forked_from(self):
        from Products.CMFPlone.browser.login import login_help as stock

        source = inspect.getsource(stock.LoginHelpForm.update)
        normalised = " ".join(source.split())

        # Each fact is asserted separately, so a failure names which one moved.
        assert "RequestResetPassword(None, self.request)" in normalised, (
            "upstream no longer builds the reset-password subform this way"
        )
        assert "RequestUsername(None, self.request)" in normalised, (
            "upstream no longer builds the username subform this way; the fork in "
            "imio/emailkit/browser/login_help.py must be re-derived"
        )
        assert (
            "if not self.use_email_as_login() and self.can_retrieve_username():"
            in normalised
        ), "upstream changed the condition that decides whether this mail exists"

    def test_our_fork_still_subclasses_stock(self):
        from imio.emailkit.browser.login_help import LoginHelpForm
        from Products.CMFPlone.browser.login import login_help as stock

        assert issubclass(LoginHelpForm, stock.LoginHelpForm)

    def test_our_subform_still_subclasses_stock(self):
        from imio.emailkit.browser.login_help import RequestUsername
        from Products.CMFPlone.browser.login import login_help as stock

        assert issubclass(RequestUsername, stock.RequestUsername)
