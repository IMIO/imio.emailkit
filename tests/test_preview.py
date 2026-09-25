"""``@@emailkit-preview`` and the send-test button.

Manager-only view. It lists every registered template, renders each in an
iframe with committed fixture data, and offers a language switcher and a
theme-token panel. A Send test button mails the previewed template,
fixture, and language to the logged-in user's own address.

Assertions here check behaviour, not markup: who may look, what is
listed, what renders, that the switcher switches, and where the test mail
goes. Each iframe's ``src`` is followed and its response is checked.

Two request keys are pinned in ``tests/support.py``:
``PREVIEW_LANGUAGE_PARAM`` (``language``) and ``SEND_TEST_FORM`` /
``SEND_TEST_METHOD`` (``form.button.send_test``, POST).

``test_it_uses_the_previewed_language`` is marked ``xfail(strict=True)``:
the builder groups recipients by their own language and takes no
language argument, so the send-test cannot yet honour the switcher.
"""

from AccessControl import Unauthorized

import contextlib
import html
import pytest
import support


support.require_runtime()


PREVIEW = f"@@{support.PREVIEW_VIEW}"


@pytest.fixture
def as_manager(mail_portal, grant_roles):
    """The preview is Manager-only, the role a developer previewing templates
    has."""
    grant_roles(mail_portal, ["Manager"])
    return mail_portal


@pytest.fixture
def preview(mail_portal, mail_request, as_manager):
    """``preview(language=None, method="GET", **form)`` returns the rendered page.

    Traverses the view so the security check runs.
    """
    support.require_preview(mail_portal, mail_request)

    def render_preview(language=None, method="GET", **form):
        mail_request.form.clear()
        if language is not None:
            mail_request.form[support.PREVIEW_LANGUAGE_PARAM] = language
        mail_request.form.update(form)
        mail_request.environ["REQUEST_METHOD"] = method
        try:
            return mail_portal.restrictedTraverse(PREVIEW)()
        finally:
            mail_request.environ["REQUEST_METHOD"] = "GET"

    return render_preview


def parse_query(source):
    """Parses the query string of an ``href``/``src`` into a form dict.

    Unescapes HTML entities first, then percent-decodes the values. Skip
    either step and a colon in a template name stays as ``%3A``, which
    resolves to nothing.
    """
    import html
    import urllib.parse

    _path, _, query = html.unescape(source).partition("?")
    return {
        key: values[0]
        for key, values in urllib.parse.parse_qs(query, keep_blank_values=True).items()
    }


@pytest.fixture
def previewed_bodies(mail_portal, mail_request, preview):
    """``previewed_bodies(language=None)`` returns each rendered mail body.

    Follows every iframe ``src``. Falls back to the page itself when there
    is no iframe, so an inline preview is still checked.
    """

    def bodies(language=None, **form):
        page = preview(language=language, **form)
        sources = support.IFRAME_SRC.findall(page)
        if not sources:
            return [page]

        rendered = []
        for source in sources:
            form = parse_query(source)
            if language is not None:
                form.setdefault(support.PREVIEW_LANGUAGE_PARAM, language)
            mail_request.form.clear()
            mail_request.form.update(form)
            target = html.unescape(source).partition("?")[0].rstrip("/").split("/")[-1]
            rendered.append(str(mail_portal.restrictedTraverse(target)()))
        return rendered

    return bodies


class TestItIsManagerOnly:
    """The preview is a developer tool that also mails on demand. Manager is
    the required role."""

    def test_anonymous_gets_unauthorized(self, mail_portal, mail_request):
        support.require_preview(mail_portal, mail_request)

        from plone.app.testing import logout

        logout()

        with pytest.raises(Unauthorized):
            mail_portal.restrictedTraverse(PREVIEW)()

    def test_a_plain_member_gets_unauthorized(self, mail_portal, mail_request):
        """Manager-only is stronger than "not anonymous". The test user is a
        Member by default, so this checks that a Member is still refused."""
        support.require_preview(mail_portal, mail_request)

        with pytest.raises(Unauthorized):
            mail_portal.restrictedTraverse(PREVIEW)()

    def test_a_manager_may_render_it(self, preview):
        page = preview()

        assert page and page.strip()


class TestItListsTheRegisteredTemplates:
    def test_every_registered_template_is_listed(self, preview):
        """Driven by discovery, so a registered template the preview forgets
        shows up here."""
        from imio.emailkit.discovery import available_templates

        page = preview()
        missing = [name for name in available_templates() if name not in page]

        assert missing == [], f"registered templates absent from the preview: {missing}"

    def test_the_default_mails_are_listed_too(self, preview):
        """The preview also lists the two Plone default mails.

        Their own views (``browser/default_mails.py``) register them for
        discovery, so the preview can offer them too.
        """
        page = preview()
        missing = [
            name
            for name in support.DEFAULT_MAIL_TEMPLATES
            if support.qualified(name) not in page
        ]

        assert missing == [], (
            f"{missing} are not offered in the preview, although the package "
            "renders them through render() like every other template"
        )


class TestItRendersWithTheCommittedFixtures:
    """The preview renders with the golden files' fixture data."""

    def test_the_fixture_values_reach_the_rendered_preview(self, previewed_bodies):
        """Checks the preview shows the fixture's data, not lorem ipsum or an
        empty context that renders without error."""
        context = support.load_fixture(support.NOTIFICATION)
        expected = context["title"]
        # Name the template explicitly. The preview otherwise defaults to
        # the first registered template alphabetically.
        bodies = previewed_bodies(
            language="fr", template=support.qualified(support.NOTIFICATION)
        )

        assert any(expected in body for body in bodies), (
            f"no previewed body contains the committed fixture's title "
            f"{expected!r}; the preview renders "
            "with the committed fixture data"
        )

    def test_the_preview_has_no_unresolved_placeholder(self, previewed_bodies):
        """The fallback engine lets ``${...}`` pass through unrendered without
        raising. Checks no such placeholder reaches the preview."""
        for body in previewed_bodies(language="fr"):
            support.assert_render_is_clean(body, "previewed body")


class TestTheLanguageSwitcher:
    """The preview offers a language switcher."""

    def test_switching_changes_the_rendered_language(self, previewed_bodies):
        fr_bodies = previewed_bodies(language="fr")
        nl_bodies = previewed_bodies(language="nl")

        fr_langs = {
            m.group(1).lower()
            for body in fr_bodies
            for m in [support.LANG_ATTRIBUTE.search(body)]
            if m
        }
        nl_langs = {
            m.group(1).lower()
            for body in nl_bodies
            for m in [support.LANG_ATTRIBUTE.search(body)]
            if m
        }

        assert fr_langs == {"fr"}, (
            f"asked for fr, the preview rendered {fr_langs or 'no lang attribute'}"
        )
        assert nl_langs == {"nl"}, (
            f"asked for nl, the preview rendered {nl_langs or 'no lang attribute'}. "
            f"support.PREVIEW_LANGUAGE_PARAM is {support.PREVIEW_LANGUAGE_PARAM!r} -- "
            "a GUESS; reconcile there if the view names it differently."
        )

    def test_the_two_languages_render_differently(self, previewed_bodies):
        """A switcher that changes only the ``lang`` attribute, not the
        translated content, does not work."""
        fr = "\n".join(previewed_bodies(language="fr"))
        nl = "\n".join(previewed_bodies(language="nl"))

        assert fr != nl, "the language switcher produced identical output"


class TestSendTest:
    """Send test mails the previewed template, fixture, and language to the
    logged-in user's own address."""

    @pytest.fixture
    def me(self, mail_portal, as_manager, make_member):
        """The logged-in user, with an address set.

        Logs in again after setting the email: the security manager caches
        the user's property sheet at login, so an email change made after
        login is invisible until the next login.
        """
        from plone.app.testing import login
        from plone.app.testing import TEST_USER_NAME

        member = make_member(mail_portal)
        login(mail_portal, TEST_USER_NAME)
        return member

    @pytest.fixture
    def send_test(self, preview):
        """``send_test(language=...)`` presses the Send test button.

        Uses POST. The view refuses GET on purpose, since a URL that sends
        mail when fetched will get fetched.
        """

        def press(language=None):
            return preview(
                language=language,
                method=support.SEND_TEST_METHOD,
                **support.SEND_TEST_FORM,
            )

        return press

    def test_it_delivers_to_the_logged_in_user(
        self, send_test, me, mailhost, site_sender, deliver
    ):
        send_test(language="fr")
        deliver()

        assert len(mailhost.sent) == 1, (
            f"the send-test produced {len(mailhost.sent)} message(s). "
            f"support.SEND_TEST_FORM is {support.SEND_TEST_FORM!r} and the method "
            f"is {support.SEND_TEST_METHOD}; reconcile in tests/support.py if the "
            "view names the control differently."
        )
        record = support.sole(mailhost.sent)

        assert support.envelope(record) == [support.MEMBER_EMAIL.lower()]

    def test_it_delivers_nowhere_else(
        self, send_test, me, mailhost, site_sender, deliver
    ):
        """The test mail must go only to the logged-in user.

        The fixture context has no other addresses, so the button must not
        pick up the site's contact address or a hardcoded address instead.
        """
        send_test(language="fr")
        deliver()

        message = support.sole(mailhost.sent).message

        assert support.addresses(message, "To") == [support.MEMBER_EMAIL.lower()]
        assert support.addresses(message, "Cc") == []
        assert message["Bcc"] is None

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "The preview's own send-test behaviour and the builder's frozen API "
            "contradict each other and the frozen builder API wins. The button is "
            "meant to mail 'the currently previewed template + fixture + "
            "LANGUAGE'. But the builder takes no language argument, "
            "and .send() groups recipients by THEIR OWN resolved language "
            "(falling back to the site default). With a single recipient -- the "
            "logged-in user -- the sent language is therefore that user's "
            "preferred language, never the switcher's. The view computes and "
            "displays the discrepancy rather than faking it, and declines to "
            "rewrite the user's language preference behind their back. "
            "The assertion is kept, running and strict: it encodes the intended "
            "send-test behaviour as written, so if anyone makes it pass, that is "
            "a deliberate resolution of the conflict and this marker has to come "
            "off with a recorded decision. NEEDS A MAINTAINER DECISION: either "
            "amend the intended behaviour, or give the preview a way to pin the "
            "render language that does not add a method to the frozen builder."
        ),
    )
    def test_it_uses_the_previewed_language(
        self, send_test, me, mailhost, site_sender, deliver, set_default_language
    ):
        """The test mail must show the previewed language, not a fixed one.

        The site default is ``fr`` and the user has no preferred language,
        so ``nl`` can only come from the switcher.
        """
        set_default_language("fr")
        me.setMemberProperties({"language": ""})

        send_test(language="nl")
        deliver()

        message = support.sole(mailhost.sent).message

        assert support.lang_of(message) == "nl", (
            "the send-test rendered in "
            f"{support.lang_of(message)!r}, not the previewed 'nl'"
        )

    def test_it_sends_the_real_thing(
        self, send_test, me, mailhost, site_sender, deliver
    ):
        """The test mail must be the same message the builder would send: both
        MIME parts, substituted, not a screenshot of the preview."""
        send_test(language="fr")
        deliver()

        message = support.sole(mailhost.sent).message
        text, html = support.bodies(message)

        assert "<html" in html.lower()
        assert text.strip()
        support.assert_message_is_clean(message)

    def test_it_is_manager_only_too(self, mail_portal, mail_request, mailhost):
        """A GET with the send-test parameter, from a non-Manager, must not
        send mail. It must not rely on the page's own check running first."""
        support.require_preview(mail_portal, mail_request)
        mail_request.form.clear()
        mail_request.form.update(support.SEND_TEST_FORM)

        with pytest.raises(Unauthorized):
            mail_portal.restrictedTraverse(PREVIEW)()

        assert mailhost.sent == []

    def test_a_manager_without_an_address_mails_nobody(
        self, mail_portal, as_manager, mailhost, site_sender, send_test, deliver
    ):
        """A Manager with no address set on a fresh site must trigger no mail.

        The send-test must not fall back to the site's contact address, the
        ``From`` address, or a hardcoded address. Raising or returning are
        both accepted outcomes.
        """
        from plone.app.testing import TEST_USER_ID

        mail_portal.portal_membership.getMemberById(TEST_USER_ID).setMemberProperties({
            "email": ""
        })

        with contextlib.suppress(Exception):
            # Raising here is an accepted outcome.
            send_test(language="fr")

        deliver()

        assert mailhost.sent == [], (
            "the send-test mailed somebody although the logged-in user has no "
            f"address: {[r.recipients for r in mailhost.sent]}"
        )
