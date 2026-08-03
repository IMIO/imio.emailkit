"""SPEC §6.3 -- ``@@emailkit-preview`` and the send-test button.

> ``@@emailkit-preview`` (Manager-only): lists all registered templates, renders
> each in an iframe using **committed fixture data** (see §7), with a language
> switcher and a theme-token panel. A **Send test** button mails the currently
> previewed template + fixture + language to the logged-in user's own address --
> browser previews lie, Outlook doesn't; this closes the loop with real clients
> for the cost of one form.

Two things make this module different from the rest of Phase 2.

**The markup is not the contract.** §6.3 pins *behaviour* -- who may look, what
is listed, what is rendered, that the language switcher switches, where the test
mail goes -- and leaves the layout to whoever writes it. So the assertions here
never look for a chosen class name or heading. Where the rendered previews live
is discovered from the page itself: the ``src`` of each iframe is followed and
what comes back is what gets asserted on. A preview page whose iframes 404, or
which renders raw ``${}`` inside them, is broken however good the outer page
looks.

**Two request keys had to be guessed.** §6.3 mentions "a language switcher" and
"a Send test button" without naming either control. Both live in
``tests/support.py`` (``PREVIEW_LANGUAGE_PARAM``, ``SEND_TEST_FORM``,
``SEND_TEST_METHOD``) and nowhere else, so reconciling them was one edit there.
``language`` was right; the button is ``form.button.send_test`` and ``POST``-only.

**One assertion is a recorded contradiction, not a bug.**
``test_it_uses_the_previewed_language`` encodes §6.3's "+ language" and is marked
``xfail(strict=True)``, because §6.2 -- the frozen section -- gives the builder no
language argument and groups by the *recipient's* language. Its marker carries the
full argument; the assertion still runs, and it flips the suite red if anybody
makes it pass without settling the spec question.
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
    """§6.3 is "Manager-only", which is also the role a developer previewing
    templates actually has."""
    grant_roles(mail_portal, ["Manager"])
    return mail_portal


@pytest.fixture
def preview(mail_portal, mail_request, as_manager):
    """``preview(language=None, method="GET", **form)`` -> the rendered page.

    Traversed rather than adapted, so the security machinery is in the path: a
    view registered with the wrong permission has to fail here.
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
    """The query of an ``href``/``src`` as a form dict.

    Two decodings, both of which cost a debugging session if forgotten: the URL
    lives in an HTML attribute, so ``&`` arrives as ``&amp;``, and the values are
    percent-encoded -- a template name like ``imio.emailkit:notification`` has
    its colon as ``%3A``, which is a perfectly good template name that resolves
    to nothing at all.
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
    """``previewed_bodies(language=None)`` -> the rendered mail(s) on the page.

    Follows every iframe ``src`` and returns what each one renders. Falls back to
    the page itself when there is no iframe, so a preview that renders inline is
    still checked rather than skipped -- §6.3 asks for an iframe, but what the
    assertions are about is the *rendered mail*, and a module that silently
    stopped looking at it would be the worst outcome here.
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
    """§6.3, first three words. A preview page lists every template and renders
    it with fixture data; it is not a secret, but it is a developer tool that
    also mails on demand, and §6.3 chose Manager."""

    def test_anonymous_gets_unauthorized(self, mail_portal, mail_request):
        support.require_preview(mail_portal, mail_request)

        from plone.app.testing import logout

        logout()

        with pytest.raises(Unauthorized):
            mail_portal.restrictedTraverse(PREVIEW)()

    def test_a_plain_member_gets_unauthorized(self, mail_portal, mail_request):
        """ "Manager-only" is a stronger claim than "not anonymous", and it is the
        one §6.3 makes. The test user is a Member by default in this fixture, so
        this is the case a permission of ``zope2.View`` would let through."""
        support.require_preview(mail_portal, mail_request)

        with pytest.raises(Unauthorized):
            mail_portal.restrictedTraverse(PREVIEW)()

    def test_a_manager_may_render_it(self, preview):
        page = preview()

        assert page and page.strip()


class TestItListsTheRegisteredTemplates:
    def test_every_registered_template_is_listed(self, preview):
        """Driven off discovery, so a template added to the §4 registration and
        forgotten by the preview shows up here -- the same reasoning
        ``test_golden.py`` uses for fixtures."""
        from imio.emailkit.discovery import available_templates

        page = preview()
        missing = [name for name in available_templates() if name not in page]

        assert missing == [], f"registered templates absent from the preview: {missing}"

    def test_the_jbot_only_default_mails_are_not_listed(self, preview):
        """They are not registered and ``render()`` cannot render them
        (``docs/DECISIONS.md``), so listing them would offer a link that raises.
        The reverse of ``test_golden.py``'s
        ``test_the_default_mails_are_not_registered_for_discovery``."""
        page = preview()
        leaked = [
            name
            for name in support.DEFAULT_MAIL_TEMPLATES
            if support.qualified(name) in page
        ]

        assert leaked == [], (
            f"{leaked} are offered in the preview but cannot be rendered by "
            "render(); see docs/DECISIONS.md"
        )


class TestItRendersWithTheCommittedFixtures:
    """§6.3: "using **committed fixture data** (see §7)"."""

    def test_the_fixture_values_reach_the_rendered_preview(self, previewed_bodies):
        """The point of reusing §7's fixtures is that the preview shows what the
        golden files pin. A preview built on lorem ipsum -- or on an empty
        context, which renders without error -- would look fine and prove
        nothing."""
        context = support.load_fixture(support.NOTIFICATION)
        expected = context["title"]
        # The template is named explicitly. The preview defaults to the
        # alphabetically first registered one, so relying on the default made this
        # assertion depend on registration order -- it broke the moment a second
        # template was registered whose name sorts earlier.
        bodies = previewed_bodies(
            language="fr", template=support.qualified(support.NOTIFICATION)
        )

        assert any(expected in body for body in bodies), (
            f"no previewed body contains the committed fixture's title "
            f"{expected!r}; §6.3 renders "
            "with the fixture data from §7"
        )

    def test_the_preview_has_no_unresolved_placeholder(self, previewed_bodies):
        """The preview is the loop developers trust to tell them a template
        works. Phase 0: on the fallback engine ``${...}`` passes through
        verbatim and nothing raises -- so a preview that shows raw placeholders
        while claiming success is exactly the failure mode this project keeps
        finding."""
        for body in previewed_bodies(language="fr"):
            support.assert_render_is_clean(body, "previewed body")


class TestTheLanguageSwitcher:
    """§6.3: "with a language switcher"."""

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
        """The guard: a switcher that changes only the ``lang`` attribute and not
        the translated content is a switcher that does not work."""
        fr = "\n".join(previewed_bodies(language="fr"))
        nl = "\n".join(previewed_bodies(language="nl"))

        assert fr != nl, "the language switcher produced identical output"


class TestSendTest:
    """§6.3: "A **Send test** button mails the currently previewed template +
    fixture + language to the logged-in user's own address"."""

    @pytest.fixture
    def me(self, mail_portal, as_manager, make_member):
        """The logged-in user, with an address of their own.

        The re-login is load-bearing, and it cost a debugging session:
        ``plone.app.testing``'s pseudo-login puts a ``PropertiedUser`` in the
        security manager at ``testSetUp`` time and that object caches its
        property sheets. Setting ``email`` afterwards updates ``portal_memberdata``
        but **not** the cached sheet, so ``api.user.get_current().getProperty(
        "email")`` still returns ``""`` -- and the view then correctly refuses to
        send, for a reason invented entirely by the test.
        """
        from plone.app.testing import login
        from plone.app.testing import TEST_USER_NAME

        member = make_member(mail_portal)
        login(mail_portal, TEST_USER_NAME)
        return member

    @pytest.fixture
    def send_test(self, preview):
        """``send_test(language=...)`` -- press the button.

        ``POST``, because the view refuses the same request over ``GET`` on
        purpose (``support.SEND_TEST_METHOD``), and rightly: a URL that sends
        mail when merely fetched gets fetched.
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
        """ "to the logged-in user's own address" is a *closed* list.

        The fixture context contains no addresses, so there is nothing here to
        leak by accident -- which is the point: the button must not acquire a
        recipient from the template, from the site's contact address, or from a
        hardcoded developer address that ships to production.
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
            "SPEC §6.3 and §6.2 contradict each other and §6.2 is the frozen "
            "one. §6.3: the button mails 'the currently previewed template + "
            "fixture + LANGUAGE'. §6.2: the builder takes no language argument, "
            "and .send() groups recipients by THEIR OWN resolved language "
            "(falling back to the site default). With a single recipient -- the "
            "logged-in user -- the sent language is therefore that user's "
            "preferred language, never the switcher's. The view computes and "
            "displays the discrepancy rather than faking it, and declines to "
            "rewrite the user's language preference behind their back. "
            "The assertion is kept, running and strict: it encodes §6.3 as "
            "written, so if anyone makes it pass, that is a deliberate resolution "
            "of the conflict and this marker has to come off with a DECISIONS.md "
            "entry. NEEDS A MAINTAINER DECISION: either amend §6.3, or give the "
            "preview a way to pin the render language that does not add a method "
            "to §6.2's frozen builder."
        ),
    )
    def test_it_uses_the_previewed_language(
        self, send_test, me, mailhost, site_sender, deliver, set_default_language
    ):
        """ "template + fixture + **language**". A test mail that always arrives
        in one language cannot answer the question it exists for -- how the Dutch
        version looks in Outlook.

        The site default is pinned to ``fr`` and the logged-in user is given no
        preferred language, so ``nl`` can only come from the switcher. Without
        that, a user who happened to prefer Dutch would make this pass for a
        reason that has nothing to do with §6.3.
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
        """The whole justification in §6.3 is "browser previews lie, Outlook
        doesn't", so the test mail has to be the *same* message the builder
        would send -- both MIME parts, substituted, not a screenshot of the
        iframe."""
        send_test(language="fr")
        deliver()

        message = support.sole(mailhost.sent).message
        text, html = support.bodies(message)

        assert "<html" in html.lower()
        assert text.strip()
        support.assert_message_is_clean(message)

    def test_it_is_manager_only_too(self, mail_portal, mail_request, mailhost):
        """The button is a mail-sending endpoint. A ``GET`` with the right
        parameter from a non-Manager must not send anything -- and must not need
        the outer page's permission check to have been passed first."""
        support.require_preview(mail_portal, mail_request)
        mail_request.form.clear()
        mail_request.form.update(support.SEND_TEST_FORM)

        with pytest.raises(Unauthorized):
            mail_portal.restrictedTraverse(PREVIEW)()

        assert mailhost.sent == []

    def test_a_manager_without_an_address_mails_nobody(
        self, mail_portal, as_manager, mailhost, site_sender, send_test, deliver
    ):
        """The Manager previewing templates on a fresh site usually has no
        address set, so this is the common case rather than the edge one.

        What is asserted is the part that is unambiguous: **no mail leaves**. A
        send-test with nowhere to send must not fall back to the site's contact
        address, to the ``From`` address, or to a developer address someone left
        in. Whether the refusal surfaces as an exception or as an on-page error is
        W2's call and both honour §6.2's "fail loud" -- which is why the call
        below is allowed to raise or to return.
        """
        from plone.app.testing import TEST_USER_ID

        mail_portal.portal_membership.getMemberById(TEST_USER_ID).setMemberProperties({
            "email": ""
        })

        with contextlib.suppress(Exception):
            # A loud refusal is a valid answer -- see the docstring.
            send_test(language="fr")

        deliver()

        assert mailhost.sent == [], (
            "the send-test mailed somebody although the logged-in user has no "
            f"address: {[r.recipients for r in mailhost.sent]}"
        )
