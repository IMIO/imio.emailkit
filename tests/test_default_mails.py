"""Installing ``:default`` restyles Plone's stock transactional mails.

This is the package's first visible value, so it is tested through the **real call
site**: ``getMultiAdapter((portal_registration, request), name=...)`` called with
exactly the keyword arguments ``Products/CMFPlone/RegistrationTool.py`` passes.
Anything less would test a code path production never takes.

Two assertions per mail, and both are required (Phase 0, caveat D1):

* the *file* jbot resolved is ours -- necessary, and on its own **worthless**,
  because with ``z3c.jbot``'s patches missing the path mapping is still correct
  while the stock template renders;
* the *rendered output* is ours and is not the stock one -- which is the only
  evidence that the swap had an effect.
"""

from email import message_from_string

import pytest
import support


support.require_runtime()


@pytest.fixture(
    params=support.DEFAULT_MAIL_TEMPLATES, ids=support.DEFAULT_MAIL_TEMPLATES
)
def template(request):
    return request.param


@pytest.fixture
def marked_request(portal, http_request):
    """A request carrying ``IEmailkitLayer``.

    Applied by hand because ``plone.browserlayer`` marks requests from an
    ``IBeforeTraverseEvent`` subscriber and an integration test never traverses.
    That the profile *registers* the layer is a separate assertion, in
    ``tests/setup/test_setup_install.py`` -- conflating the two would let a
    missing ``browserlayer.xml`` pass here.
    """
    from imio.emailkit.interfaces import IEmailkitLayer

    return support.mark_request(http_request, IEmailkitLayer)


@pytest.fixture
def member(portal, make_member):
    return make_member(portal)


@pytest.fixture
def view(portal, marked_request, template):
    return support.stock_mail_view(portal, marked_request, template)


@pytest.fixture
def rendered(portal, marked_request, template, member):
    return support.call_stock_mail(portal, marked_request, template, member)


class TestWeOwnTheStockViews:
    """The stock view *names* must resolve to our classes, on our layer.

    ``RegistrationTool`` looks these up by name on ``portal_registration``; if our
    registration does not win, everything below this class would still pass while
    stock Plone's mail went out.
    """

    def test_the_view_is_ours(self, view):
        from imio.emailkit.browser.default_mails import DefaultMailView

        assert isinstance(view, DefaultMailView), (
            f"{type(view).__module__}.{type(view).__name__} rendered the mail, "
            "so our registration did not win the lookup"
        )

    def test_it_renders_a_registered_template(self, view):
        """The whole point of owning the view: these go through discovery and
        ``render()`` like any consumer template, rather than through a
        dialect only these two speak."""
        from imio.emailkit.discovery import get_template

        assert get_template(view.template_name) is not None

    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            ("mailPassword", ("member", "reset")),
            ("registeredNotify", ("member", "reset")),
        ],
    )
    def test_stock_kwargs_are_what_we_build_from(self, method, expected):
        """Drift guard on the one piece of stock Plone we cannot inherit.

        ``build_context`` reads ``member`` and ``reset`` out of the kwargs the
        tool passes. Those names are stock's, not ours, so a Plone upgrade that
        renames or drops one would silently hand us ``None`` and send a mail with
        an empty link. The same guard ``login_help.py`` carries for its fork of
        ``update()``; when it trips, re-read the call site and update
        ``build_context``. Do not weaken it.
        """
        import inspect

        from Products.CMFPlone.RegistrationTool import RegistrationTool

        source = inspect.getsource(getattr(RegistrationTool, method))
        call = source[source.index("_template(") :]
        missing = [name for name in expected if f"{name}=" not in call]

        assert missing == [], (
            f"RegistrationTool.{method} no longer passes {missing} to its mail "
            "view; imio.emailkit.browser.default_mails.build_context reads them"
        )


class TestRenderedOutputIsOurs:
    def test_kit_accessibility_default_is_present(self, rendered):
        """``role="presentation"`` on layout tables. Also the cheapest proof
        that a *kit* template rendered rather than any other file."""
        assert support.A11Y_TABLE_MARKER in rendered

    def test_html_carries_the_language(self, rendered):
        """The layout emits ``lang`` on ``<html>``."""
        assert support.LANG_ATTRIBUTE.search(rendered), "no lang attribute on <html>"

    def test_css_was_inlined(self, rendered):
        """Phase 1's exit criterion, through the jbot path this time.

        Phase 0 caveat A1: a placeholder in a literal ``style`` attribute takes a
        template from 31 inline styles to 6 with the build still green.
        """
        count = support.count_inline_styles(rendered)

        assert count >= support.MIN_INLINE_STYLES, (
            f"only {count} inline style attributes -- CSS inlining is dead"
        )

    def test_no_placeholder_survived(self, rendered):
        """The whole point of Phase 0's engine finding: ``${...}`` reaches the
        inbox verbatim under the zope.tal fallback and nothing raises."""
        support.assert_render_is_clean(rendered, "the rendered mail")

    def test_stock_body_is_gone(self, rendered, template):
        """The negative half. Asserting on the English default text rather than
        on the msgid, because ``i18n:translate`` replaces the msgid either way --
        a msgid-based negative control can never fail."""
        stock = support.STOCK_BODY_MARKERS[template]

        assert stock not in rendered, f"stock template leaked: {stock!r}"

    def test_the_recipient_address_was_substituted(self, rendered, member):
        assert member.getProperty("email") in rendered

    def test_the_mail_says_whose_account_it_is_about(self, rendered, member):
        """Either the fullname or the userid, in the body.

        Not a style preference: a password-reset mail that names no account is
        phishing-shaped, and it is what the stock template does too (it prints the
        userid). Which of the two the author picks is their call, so the test
        accepts either -- what it will not accept is neither.
        """
        identifiers = (member.getProperty("fullname"), member.getId())

        assert any(value and value in rendered for value in identifiers), (
            f"neither {identifiers[0]!r} nor {identifiers[1]!r} is in the mail"
        )


class TestThemeTokensReachTheDefaultMails:
    """Level 2 has to work on *these* two mails above all others.

    "Adjust branding only: theme tokens via ``plone.app.registry`` -- covers the
    majority of per-commune needs without touching markup." The password-reset
    mail is the single most likely thing a commune wants in its own colours, and
    it is rendered by the *stock view*, whose namespace contains no ``theme``:
    view keyword arguments land in ``options`` and nothing else is injected
    (Phase 0, caveat D2).

    So a token that is only wired into ``render()``'s namespace silently does
    nothing here -- level 2 of the documented override story would apply to every
    template except the two that ship. The override has to reach the registry
    itself, the way the stock ``registered_notify_template`` already reaches
    ``context.portal_registry['plone.email_from_name']``.
    """

    PROBE_COLOR = "#7f00ff"

    @pytest.fixture
    def with_probe_color(self, portal):
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        record = support.THEME_RECORDS["primary_color"]
        assert record in registry.records, f"{record} is not installed"
        registry[record] = self.PROBE_COLOR
        return self.PROBE_COLOR

    def test_the_primary_color_reaches_the_default_mail_render(
        self, portal, marked_request, template, member, with_probe_color
    ):
        rendered = support.call_stock_mail(portal, marked_request, template, member)

        assert with_probe_color in rendered, (
            "the theme token did not reach the render: level 2 does not "
            "apply to the two mails :default ships"
        )


class TestTheResultIsStillAParsableMail:
    """``RegistrationTool`` does ``message_from_string(mail_text.strip())`` and
    pulls ``Subject`` / ``To`` / ``From`` back out. A restyled body that loses the
    headers sends a mail to nobody, from nobody, about nothing."""

    def test_headers_round_trip(self, rendered, member):
        message = message_from_string(rendered.strip())

        assert message["To"] is not None
        assert member.getProperty("email") in message["To"]
        assert message["From"]
        assert message["Subject"]

    def test_the_subject_is_our_registered_msgid_translated(
        self, rendered, template, marked_request
    ):
        """Subjects are re-registered as i18n msgids in the
        ``imio.emailkit`` domain.

        They now live in the template's ``<emailkit:templates>`` registration,
        exactly like every other subject in the package, and
        ``DefaultMailView.header_block`` translates that msgid into the
        recipient's language. Before the views were ours the msgid had to be
        emitted by the template itself, on a hand-written ``Subject:`` line with
        ``tal:omit-tag=""`` on the span; one forgotten attribute shipped
        ``Subject: <span>Password reset request</span>``.

        Compared against the translation of the registered msgid rather than
        against a blacklist of stock subject strings: our msgid's English default
        is allowed to read the same as Plone's, so identical text proves nothing.
        What proves it is that the header equals what our own domain returns for
        our own msgid.
        """
        from zope.i18n import translate

        msgid = support.registered_subject(template)

        assert msgid, f"{template} declares no subject in its registration"
        expected = translate(msgid, context=marked_request)
        message = message_from_string(rendered.strip())

        assert message["Subject"] == expected, (
            f"Subject is {message['Subject']!r}, expected the imio.emailkit "
            f"translation of {msgid!r} -> {expected!r}"
        )

    def test_a_content_type_is_declared(self, rendered):
        """The *value* is deliberately not pinned: whether an HTML body needs
        ``multipart/alternative`` with a hand-emitted boundary is an open Phase 2
        question (Phase 0 report, "Flagged for Phase 2"). That a Content-Type is
        declared at all is not open -- without one the mail is ``text/plain`` by
        default and clients show the markup."""
        message = message_from_string(rendered.strip())

        assert message["Content-Type"], "no Content-Type header in the mail"
