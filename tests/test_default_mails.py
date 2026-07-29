"""SPEC §8.1 -- installing ``:default`` restyles Plone's stock transactional mails.

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


class TestJbotResolvesOurFile:
    def test_the_override_wins_at_lookup(self, view, template):
        resolved = support.resolved_template(view)
        expected = support.JBOT_OVERRIDE_FILENAMES[template]

        assert resolved.filename.endswith(expected), (
            f"jbot resolved {resolved.filename!r}, expected a file named {expected!r}"
        )
        assert support.PACKAGE_NAME.replace(".", "/") in resolved.filename.replace(
            "\\", "/"
        ), f"the winning file is not ours: {resolved.filename!r}"

    def test_the_shadowed_original_is_the_stock_file(self, view, template):
        """jbot stashes what it displaced. If this is not the CMFPlone file, the
        override is shadowing something else entirely."""
        resolved = support.resolved_template(view)

        assert resolved._filename.endswith(support.STOCK_TEMPLATE_TAILS[template])


class TestRenderedOutputIsOurs:
    def test_kit_accessibility_default_is_present(self, rendered):
        """§3: ``role="presentation"`` on layout tables. Also the cheapest proof
        that a *kit* template rendered rather than any other file."""
        assert support.A11Y_TABLE_MARKER in rendered

    def test_html_carries_the_language(self, rendered):
        """§3: the layout emits ``lang`` on ``<html>``."""
        assert support.LANG_ATTRIBUTE.search(rendered), "no lang attribute on <html>"

    def test_css_was_inlined(self, rendered):
        """§9's Phase 1 exit criterion, through the jbot path this time.

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


class TestThemeTokensReachTheJbotPath:
    """§8.2 level 2 has to work on *these* two mails above all others.

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

    def test_the_primary_color_reaches_the_stock_view_render(
        self, portal, marked_request, template, member, with_probe_color
    ):
        rendered = support.call_stock_mail(portal, marked_request, template, member)

        assert with_probe_color in rendered, (
            "the theme token did not reach a jbot-hosted render: §8.2 level 2 "
            "does not apply to the two mails §8.1 ships"
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

    def test_the_subject_is_our_msgid_translated(
        self, rendered, template, marked_request
    ):
        """§8.1: "subjects are re-registered as i18n msgids in the
        ``imio.emailkit`` domain".

        ``docs/DECISIONS.md`` settled the route: the override template emits its
        own ``Subject:`` header, because the stock subjects are Python-side
        methods on ``PasswordResetToolView`` that jbot cannot reach.

        Compared against the *translation of the registered msgid* rather than
        against a list of stock subject strings. A text blacklist cannot work
        here: the registration's msgid default is allowed to read the same as
        Plone's -- ``"Password reset request"`` is simply what that mail is called
        -- so identical text proves nothing either way. What does prove it is that
        the header equals what our own domain returns for our own msgid.
        """
        from zope.i18n import translate

        msgid = support.override_subject_message(template)

        assert msgid, (
            f"{support.override_path(template).name} emits no i18n:translate on "
            "its Subject: line, so the subject is not an imio.emailkit msgid"
        )
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
