"""The username-reminder mail sent by Plone's login-help form.

The other two default mails are ``z3c.jbot`` overrides, so ``test_default_mails.py``
tests them through the *stock view* that renders them. This one has no stock
template at all -- Plone's version is a hardcoded plaintext string in
``login_help.py`` -- so ``imio.emailkit`` overrides the **view**, and the tests
here are correspondingly different in kind:

* the template itself is an ordinary discovered template and is covered by the
  golden harness in ``test_golden.py`` like ``notification`` is;
* what needs its own module is the *view swap* and the *send*, plus the
  anti-enumeration behaviour inherited from stock that must not regress.

The one test here that is not about our code is
:meth:`TestUpstreamDrift.test_stock_update_is_what_we_forked_from`. It exists
because ``LoginHelpForm.update`` is forked rather than extended (there is no seam:
stock names ``RequestUsername`` directly and sends inside the subform's own
``update()``), and a silent upstream change would silently un-style the mail.
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
    """A **fresh** request carrying the add-on's browser layer.

    The layer is applied by hand because ``plone.browserlayer`` marks requests from
    an ``IBeforeTraverseEvent`` subscriber and an integration test never traverses.

    Built here rather than taken from the layer fixture, and that matters: marking
    inserts the layer into the request's interface *declaration*, where
    ``noLongerProvides`` will not take it back out, and the test layers hand out a
    shared request object. Marking that shared request leaks the layer into every
    later test that needs an unmarked one -- which is precisely what
    ``tests/test_optout.py``'s ``unmarked_request`` guard exists to catch, and it
    fails as an *error in another module*, a long way from the cause.

    A request built on the spot is disposable, so nothing leaks and the lookup is
    still the real ZCA lookup.
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
    """A PAS ``searchUsers`` record, shaped the way stock passes it on.

    Built from a real member rather than hand-written, so the keys this code reads
    (``userid``, ``login``, ``title``, ``email``) stay the ones PAS actually
    produces.
    """
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
    """The whole point of the view override (the note above).

    The two jbot mails are deliberately *not* discovered, and
    ``test_golden.py::test_the_default_mails_are_not_registered_for_discovery``
    keeps them that way. This one is the opposite case and is asserted as such, so
    a future reader does not "tidy" it into ``DEFAULT_MAIL_TEMPLATES``.
    """

    def test_it_is_registered_for_discovery(self, integration):
        from imio.emailkit.discovery import get_templates

        assert QUALIFIED in get_templates()

    def test_it_renders_through_the_flat_context(self, integration):
        from imio.emailkit import render

        context = support.load_fixture(TEMPLATE)
        html, text = render(QUALIFIED, context=context, language="en")

        # Assert on the fixture's *values*: a marker-shaped assertion would pass
        # against a template that emitted the placeholder literally.
        assert context["login"] in html
        assert context["login"] in text
        assert context["client_addr"] in html

    def test_the_subject_comes_from_the_registration(self, integration):
        from imio.emailkit.discovery import get_template

        assert get_template(QUALIFIED).subject is not None

    def test_the_plaintext_part_is_the_hand_authored_twin(self, integration):
        """Not ``naive_text()`` of the HTML.

        The entire payload of this mail is one string the recipient has to read
        and retype, so the generated-plaintext fallback is not good enough here. The twin is
        recognisable by carrying the label and the value on one line, which the
        HTML-derived fallback cannot produce.
        """
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
        """A site that opted out keeps stock Plone's view, and so its stock mail.

        The negative control for the test above. Without it, a registration that
        accidentally landed on ``IDefaultBrowserLayer`` would pass everything else
        in this module while quietly removing the opt-out.

        The request is built here rather than taken from the opted-out layer's
        fixture, and that is not fussiness: ``plone.app.testing``'s layers share one
        request object, and marking it with a browser layer inserts the layer into
        its *declaration*, where it survives a ``noLongerProvides``. So the shared
        request arrives here already carrying the layer and this assertion silently
        inverts -- it passes alone and fails after any test that marked a request. A
        request constructed on the spot provides ``IDefaultBrowserLayer`` and nothing
        else, which is the actual condition on an opted-out site.
        """
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
        """We override the mail, not the page.

        ``index`` points at CMFPlone's own ``login_help.pt`` by absolute path, so
        a site that already jbot-overrides the login-help *form* keeps winning.
        """
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
        # A kit marker plus the payload: either alone would be satisfiable by a
        # template that lost the other half.
        assert support.A11Y_TABLE_MARKER in parts["text/html"]
        assert userinfo["login"] in parts["text/html"]
        assert userinfo["login"] in parts["text/plain"]

    def test_it_is_not_plones_plaintext_string(
        self, mail_portal, mailhost, site_sender, subform, userinfo, sent
    ):
        """The negative control: stock's body must be gone, not merely wrapped.

        Uses stock's own English default text, not a msgid -- a msgid-shaped
        assertion would pass even when the stock template rendered.
        """
        subform.send_username(mail_portal, userinfo)

        body = sent[0].message.as_string()

        assert "You requested to be reminded of your username" not in body

    def test_the_client_address_reaches_the_mail(
        self, mail_portal, mail_request, mailhost, site_sender, subform, userinfo, sent
    ):
        """The origin IP must arrive in the mail, and not as an empty string.

        Deliberately run against a request with **no** ``X-Forwarded-For``, which is
        the configuration that breaks the expression stock Plone uses -- see
        ``TestClientAddressSemantics`` below for that mechanism on its own.

        ``_client_addr`` is assigned directly because ``getClientAddr`` has no
        setter: the value is computed once in ``HTTPRequest.__init__`` from
        ``REMOTE_ADDR``, and the test layers build a request that has none, so a
        later ``environ`` edit would not be picked up.
        """
        assert "HTTP_X_FORWARDED_FOR" not in mail_request.environ
        mail_request._client_addr = "81.240.17.203"

        subform.send_username(mail_portal, userinfo)
        html = payload(sent[0].message)["text/html"]

        assert "81.240.17.203" in html

    def test_it_goes_to_the_member_in_their_own_language(
        self, mail_portal, mailhost, site_sender, subform, userinfo, sent, fr_member
    ):
        """Resolved as a *member*, not as a userid string.

        the ``str`` recipient adapter reads any string containing "@" as an address and
        never looks a member up, so passing the userid would misdeliver on a site
        whose userids look like addresses. Passing the member also carries the
        language, which is what this asserts.
        """
        subform.send_username(mail_portal, userinfo)

        message = sent[0].message

        assert fr_member.getProperty("email") in message["To"]
        # The FR member's language, so the mail must not be in English.
        text = payload(message)["text/plain"]
        assert "You asked to be reminded" not in text


class TestClientAddressSemantics:
    """Why both login-help mails read ``getClientAddr`` and not the header chain.

    Stock Plone writes ``request/HTTP_X_FORWARDED_FOR|request/REMOTE_ADDR``, and it
    renders *empty* whenever the header is absent. Two behaviours combine:

    * ``HTTPRequest.get`` special-cases CGI and ``HTTP_`` keys and returns ``''``
      for a missing one instead of raising;
    * a TAL ``|`` chain falls through only on a traversal *exception*, never on a
      falsy value.

    So the first subexpression succeeds with ``''`` and the ``REMOTE_ADDR`` fallback
    is unreachable. These are plain unit assertions -- no Plone, no site -- because
    the claim is about Zope's request object and should fail here, loudly, if a Zope
    upgrade ever changes it.
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
        """The half nobody expects: ``''``, not a ``KeyError``."""
        request = self.request_with()

        assert request.get("HTTP_X_FORWARDED_FOR") == ""
        assert request["HTTP_X_FORWARDED_FOR"] == ""

    def test_get_client_addr_falls_back_where_the_chain_cannot(self):
        request = self.request_with()

        assert request.getClientAddr() == "10.1.2.3"

    def test_the_templates_do_not_use_the_broken_chain(self):
        """Both login-help mails, asserted on the committed build output.

        The compiled ``.pt`` is what production renders, so that is what this reads
        -- a source-level check would pass while a stale build shipped the old
        expression.
        """
        import imio.emailkit

        package = pathlib.Path(imio.emailkit.__file__).parent
        files = [
            package / "templates" / f"{TEMPLATE}.pt",
            package
            / "browser"
            / "overrides"
            / support.JBOT_OVERRIDE_FILENAMES[support.MAIL_PASSWORD],
        ]

        for path in files:
            body = path.read_text(encoding="utf-8")
            assert "HTTP_X_FORWARDED_FOR" not in body, (
                f"{path.name} still reads the forwarded header directly; it renders "
                f"empty when the header is absent"
            )


class TestAntiEnumeration:
    """Stock's paranoia behaviour, inherited and asserted so it cannot regress.

    The login-help form must not become an oracle for which addresses are
    registered. Stock achieves that by sending nothing and *still* reporting
    success; all three outcomes are indistinguishable to the submitter. This is a
    security property, not a missing feature -- see the class docstring of
    ``imio.emailkit.browser.login_help.RequestUsername``.
    """

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
        """The positive half, driven through the *button handler* rather than
        through ``send_username`` -- otherwise nothing proves the handler reaches
        our override at all."""
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
    """Put a login-help username submission on the request.

    ``form.`` is z3c.form's default prefix and ``get_username`` is the button name
    stock declares (``login_help.py:127``).
    """
    request.form.clear()
    request.form.update({
        "form.widgets.recover_username": address,
        "form.buttons.get_username": "Get your username",
    })
    return request


class TestReachability:
    """``use_email_as_login`` decides whether this mail exists at all.

    Stock hides the username subform when it is on (``login_help.py:242``). Both
    states are asserted so that the missing form is never read as a bug in
    ``imio.emailkit.browser.login_help``.
    """

    @pytest.fixture
    def form(self, mail_portal, mail_request):
        from imio.emailkit.browser.login_help import LoginHelpForm

        view = LoginHelpForm(mail_portal, mail_request)
        view.request = mail_request
        return view

    @pytest.fixture(autouse=True)
    def restore_login_setting(self, mail_portal):
        """Put ``use_email_as_login`` back, whatever the test did to it.

        The layer rolls the database back between tests, so this is belt and
        braces -- but a registry record that silently stays flipped changes which
        mails the *rest* of the suite thinks exist, and that failure would surface
        somewhere unrelated.
        """
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
    """The price of forking ``LoginHelpForm.update``, made loud instead of silent.

    ``update()`` is forked because stock offers no seam: it names
    ``RequestUsername`` directly (``login_help.py:243``) and the mail is sent
    inside the subform's own ``update()``, so ``super().update()`` would already
    have sent the plaintext mail. The fork is twelve lines; the risk is that a
    Plone upgrade changes the original and our copy quietly stops matching.

    **When this fails:** read the current upstream ``update()``, re-fork it in
    ``imio/emailkit/browser/login_help.py``, and update the expectation here. Do
    not delete or loosen the test -- it is the only thing standing between a Plone
    upgrade and a silently unstyled mail.
    """

    def test_stock_update_is_what_we_forked_from(self):
        from Products.CMFPlone.browser.login import login_help as stock

        source = inspect.getsource(stock.LoginHelpForm.update)
        normalised = " ".join(source.split())

        # The three facts our fork depends on, each asserted separately so the
        # failure names which one moved.
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
