"""``render_shell(subject, body_html, language=None)``.

Wraps a legacy HTML body in the kit layout without redesigning it.
``tests/test_golden.py`` covers the golden output, and
``tests/test_shell_send.py`` covers sending it through the builder.

For the shell's own markup, a surviving ``${...}`` is a defect. For the
injected legacy body, it is required: the body must render verbatim,
never evaluated, never sanitised. The cleanliness checks therefore run
on the html with the injected body removed.
"""

import pytest
import re
import support


render_shell = support.require_shell()

from imio.emailkit import render  # noqa: E402


# ---------------------------------------------------------------------------
# Identities. Chosen so that finding one in the output can only mean one thing.
# ---------------------------------------------------------------------------

#: A subject with characters that must be escaped. Only the body slot uses
#: ``structure``; everything else, including the heading, uses Chameleon's
#: default escaping.
SUBJECT_WITH_MARKUP = 'Séance <script>alert("x")</script> & suite'

#: A subject that cannot collide with anything in the kit, for counting.
SUBJECT_SENTINEL = "SUJET-SENTINELLE-3f9a"

#: The simplest possible legacy body, rendered verbatim.
SIMPLE_BODY = "<p>Body</p>"

#: A marker that appears in no template, no stylesheet and no translation.
BODY_SENTINEL = "CORPS-SENTINELLE-8c21"

#: Theme probes. Nothing in the kit, in Tailwind's palette or in Plone's chrome
#: uses these, so finding one in the output can only mean the record was read.
PROBE_COLOR = "#7f00ff"
OTHER_COLOR = "#00ff7f"
PROBE_LOGO = "https://probe.example.be/logo-probe.png"
OTHER_LOGO = "https://probe.example.be/logo-other.png"
PROBE_FOOTER = "<span>Pied de page sonde &mdash; probe-footer-marker</span>"

#: A hidden element whose content is not a comment: a preheader. The kit
#: renders one for an authored template, and none for the shell.
HIDDEN_ELEMENT = re.compile(
    r"<(?P<tag>div|span|p)[^>]*display:\s*none[^>]*>(?P<inner>.*?)</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)

#: An HTML comment, including Outlook's conditional blocks -- the *only* thing the
#: shell's one hidden element is allowed to contain.
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@pytest.fixture
def shell(integration):
    """``shell(subject, body, language="fr")`` returns ``(html, text)``.

    Needs the ``integration`` layer: theme tokens come from
    ``plone.app.registry`` and the subject is translated through
    ``zope.i18n``.
    """

    def make(subject=SUBJECT_SENTINEL, body=SIMPLE_BODY, language="fr"):
        return render_shell(subject, body, language=language)

    return make


@pytest.fixture
def authored(integration):
    """The same kit layout with authored content, for parity checks.

    Renders the real registered template in the same language and
    registry state as the shell, so the two can be compared directly.
    """

    def make(language="fr"):
        return render(
            support.qualified(support.NOTIFICATION),
            context=support.load_fixture(support.NOTIFICATION),
            language=language,
        )

    return make


@pytest.fixture
def set_record(integration):
    """Set one theme record, asserting the profile installed it first."""
    from plone.registry.interfaces import IRegistry
    from zope.component import getUtility

    def setter(name, value):
        registry = getUtility(IRegistry)
        record = support.THEME_RECORDS[name]
        assert record in registry.records, (
            f"{record} is not in the registry -- the {support.PACKAGE_NAME} "
            "profile did not install the theme tokens"
        )
        registry[record] = value

    return setter


def without_body(html, body):
    """``html`` with the injected body removed, for the cleanliness checks.

    The injected body may contain ``${...}`` and ``tal:`` attributes
    verbatim; the shell around it may not. Removing the body lets both
    rules be checked separately.
    """
    assert body in html, "the injected body is not in the output verbatim"
    return html.replace(body, "")


def visible_hidden_text(html):
    """The non-comment text inside every ``display: none`` element.

    Empty means no preheader. Comments are stripped first, since the
    shell keeps one hidden element for an Outlook conditional comment.
    """
    return [
        stripped
        for match in HIDDEN_ELEMENT.finditer(html)
        if (stripped := COMMENT.sub("", match.group("inner")).strip())
    ]


# ===========================================================================
# Return value: (html, text); the body appears unescaped inside the shell
# ===========================================================================


class TestReturnValue:
    def test_returns_html_and_text(self, shell):
        """Returns ``(html, text)``, like ``render()``."""
        result = shell()

        assert isinstance(result, tuple)
        assert len(result) == 2

        html, text = result

        assert isinstance(html, str)
        assert isinstance(text, str)
        assert html.strip()
        assert text.strip()

    def test_the_html_is_a_whole_document_and_the_text_is_not(self, shell):
        html, text = shell()

        assert html.lstrip().lower().startswith("<!doctype html>")
        assert "</html>" in html
        assert "<html" not in text.lower()

    def test_the_body_is_injected_unescaped(self, shell):
        """The body slot uses ``structure``, so the body must not be escaped.

        An escaped body would turn every migrated notification into a
        mail full of ``&lt;p&gt;``.
        """
        html, _text = shell(body=f"<p>{BODY_SENTINEL}</p>")

        assert f"<p>{BODY_SENTINEL}</p>" in html
        assert "&lt;p&gt;" not in html

    def test_the_body_appears_exactly_once(self, shell):
        """The body must render exactly once, not duplicated by a second slot."""
        body = f"<p>{BODY_SENTINEL}</p>"

        html, _text = shell(body=body)

        assert html.count(BODY_SENTINEL) == 1, (
            f"the injected body appears {html.count(BODY_SENTINEL)} times; the "
            "layout must render the body_html slot exactly once"
        )

    def test_the_body_sits_inside_the_document_body(self, shell):
        """The body must sit inside ``<body>``, not ``<head>``, where it would
        be invisible."""
        body = f"<p>{BODY_SENTINEL}</p>"

        html, _text = shell(body=body)

        assert html.index("<body") < html.index(BODY_SENTINEL) < html.index("</body>")

    def test_the_shell_around_the_body_is_clean(self, shell):
        """The shell's own markup must be clean: no unsubstituted ``${...}``,
        no leftover ``tal:``/``i18n:``."""
        body = f"<p>{BODY_SENTINEL}</p>"

        html, text = shell(body=body)

        support.assert_render_is_clean(without_body(html, body), "the shell html")
        support.assert_render_is_clean(
            text.replace(BODY_SENTINEL, ""), "the shell text"
        )

    def test_the_subject_is_escaped(self, shell):
        """The subject must be escaped, unlike the body.

        A subject is often computed from an item title, so it can carry
        user-entered content.
        """
        html, _text = shell(subject=SUBJECT_WITH_MARKUP)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "&amp; suite" in html

    def test_an_empty_subject_collapses_the_heading(self, shell):
        """An empty subject renders a mail with no heading, not an error."""
        html, _text = shell(subject="", body=f"<p>{BODY_SENTINEL}</p>")

        assert BODY_SENTINEL in html
        assert "<h1" not in html
        support.assert_render_is_clean(
            html.replace(BODY_SENTINEL, ""), "the headless shell"
        )

    def test_an_empty_body_collapses_the_slot(self, shell):
        """An empty body must still render a valid, complete document."""
        html, text = shell(subject=SUBJECT_SENTINEL, body="")

        assert SUBJECT_SENTINEL in html
        assert "</html>" in html
        assert SUBJECT_SENTINEL in text
        support.assert_render_is_clean(html.replace(SUBJECT_SENTINEL, ""), "empty body")


class TestTheCompiledShellRequiresASubject:
    """The compiled ``shell.pt`` template, checked directly.

    ``render_shell`` always passes a subject, but ``shell.pt`` is a
    shipped file that ``z3c.jbot`` can override. Its
    ``tal:condition="subject"`` must keep raising a loud ``KeyError`` on
    a missing name, not render a silently headless mail.
    """

    def test_a_missing_subject_name_raises(self, integration):
        from imio.emailkit.render import build_namespace
        from imio.emailkit.render import render_file
        from imio.emailkit.render import SHELL_TEMPLATE

        namespace = build_namespace({"body_html": SIMPLE_BODY}, "fr")

        with pytest.raises(KeyError):
            render_file(SHELL_TEMPLATE, namespace)

    def test_a_missing_body_html_name_renders_a_shell_with_no_body(self, integration):
        """Not symmetrical with the missing-subject case: a mail with a
        heading and no body is degraded, not broken."""
        from imio.emailkit.render import build_namespace
        from imio.emailkit.render import render_file
        from imio.emailkit.render import SHELL_TEMPLATE

        namespace = build_namespace({"subject": SUBJECT_SENTINEL}, "fr")

        html = render_file(SHELL_TEMPLATE, namespace)

        assert SUBJECT_SENTINEL in html
        assert "</html>" in html


# ===========================================================================
# Kit defaults around a legacy body: inlined CSS, a11y defaults, lang, layout
# ===========================================================================


class TestKitDefaultsAroundALegacyBody:
    """The shell is the kit layout with a legacy body swapped in. Every kit
    default must survive that swap."""

    def test_the_document_head_is_identical_to_an_authored_templates(
        self, shell, authored
    ):
        """The shell's ``<head>`` must equal an authored template's ``<head>``.

        The head holds charset, viewport, the colour-scheme meta pair,
        the dark-mode ``<style>`` block, and the ``<html>`` attributes;
        only the layout controls it.
        """
        shell_html, _ = shell()
        authored_html, _ = authored()

        assert support.head_of(shell_html) == support.head_of(authored_html)

    def test_layout_tables_are_marked_presentational(self, shell):
        """``role="presentation"`` on all layout tables. Without it a screen
        reader announces the mail cell by cell."""
        html, _text = shell()

        assert support.A11Y_TABLE_MARKER in html

    def test_every_table_in_the_shell_is_presentational(self, shell):
        """Every layout table in the shell must be presentational.

        Only the shell's own tables count; a legacy body's data tables
        must not carry this role. ``role="none"`` counts too: it is an
        ARIA synonym for ``role="presentation"``.
        """
        body = f"<p>{BODY_SENTINEL}</p>"

        html, _text = shell(body=body)
        shell_only = without_body(html, body)

        tables = re.findall(r"<table\b[^>]*>", shell_only)
        assert tables, "the shell renders no layout table at all"
        unmarked = [
            tag
            for tag in tables
            if 'role="presentation"' not in tag and 'role="none"' not in tag
        ]
        assert unmarked == [], f"layout tables with no presentational role: {unmarked}"

    def test_the_logo_has_an_alt_attribute(self, shell, set_record):
        """The logo image must carry an ``alt`` attribute.

        The token is set first, since the logo only renders when it is
        set.
        """
        set_record("logo_url", PROBE_LOGO)

        html, _text = shell()

        index = html.find(PROBE_LOGO)
        assert index != -1, f"{PROBE_LOGO} never reached the shell"
        tag = html[html.rfind("<", 0, index) : html.find(">", index) + 1]
        assert "alt=" in tag, f"logo <img> has no alt attribute: {tag}"

    def test_lang_is_emitted_on_html(self, shell):
        """The layout emits ``lang`` on ``<html>``."""
        html, _text = shell(language="fr")

        match = support.LANG_ATTRIBUTE.search(html)

        assert match, "no lang attribute on <html> (a11y default)"
        assert match.group(1).lower().startswith("fr")

    def test_css_was_inlined(self, shell):
        """CSS must be inlined in the shell too.

        The shell is a separate build output, so it can lose inlining on
        its own. A ``${...}`` in a literal ``style`` attribute stops
        inlining for the whole document while the build still succeeds.
        """
        html, _text = shell()

        count = support.count_inline_styles(html)

        assert count >= support.MIN_INLINE_STYLES, (
            f"only {count} inline style attributes in the shell: CSS inlining is "
            "probably dead"
        )

    def test_dark_mode_survives(self, shell, authored):
        """Dark mode needs both the head stylesheet and ``data-dark`` hooks in
        the body. Head parity covers the stylesheet; this covers the hooks."""
        shell_html, _ = shell()
        authored_html, _ = authored()

        assert "data-dark=" in shell_html
        assert shell_html.count("data-dark=") == authored_html.count("data-dark=")

    def test_the_shell_renders_no_preheader(self, shell, authored):
        """The shell renders no preheader, unlike an authored template.

        A hidden preheader would repeat the subject and use up the inbox
        snippet before reaching the legacy body. Both halves are
        checked: the authored template's preheader path works, and the
        shell uses none of it.
        """
        shell_html, _ = shell()
        authored_html, _ = authored(language="en")

        assert visible_hidden_text(authored_html), (
            "the authored template renders no preheader at all: the "
            "registration msgid never reached the layout's hidden div"
        )
        assert visible_hidden_text(shell_html) == [], (
            "the shell rendered a preheader: "
            f"{visible_hidden_text(shell_html)}. See emails/src/templates/"
            "shell.vue for why it deliberately does not."
        )


# ===========================================================================
# Theme tokens apply to the shell around a legacy body
# ===========================================================================


class TestThemeTokens:
    """The three theme records must apply to the shell too, or a commune
    cannot brand its migrated mails."""

    def test_changing_the_logo_token_changes_the_shell(self, shell, set_record):
        set_record("logo_url", PROBE_LOGO)
        first, _ = shell()

        set_record("logo_url", OTHER_LOGO)
        second, _ = shell()

        assert PROBE_LOGO in first, (
            f"{PROBE_LOGO} never reached the shell: the theme token is not rendered"
            " (pass it through tal:attributes, not a literal style attribute)"
        )
        assert OTHER_LOGO in second
        assert PROBE_LOGO not in second, "the render cached the old token value"

    def test_primary_color_has_no_surface_left_in_the_shell(self, shell, set_record):
        """The shell has no surface painted with ``primary_color``.

        The token reaches every other template through ``KitCard`` and
        ``KitButton``, but a shell around a legacy body has neither.
        """
        set_record("primary_color", PROBE_COLOR)

        html, _text = shell(body=f"<p>{BODY_SENTINEL}</p>")

        assert PROBE_COLOR not in html

    def test_the_token_lands_in_a_closed_attribute(self, shell, set_record):
        """The logo token must land inside a closed attribute, not a broken
        one like ``style="background-image:${theme/logo_url"``."""
        set_record("logo_url", PROBE_LOGO)

        html, _text = shell(body=f"<p>{BODY_SENTINEL}</p>")

        attribute = re.compile(r'[a-zA-Z-]+="[^"]*' + re.escape(PROBE_LOGO) + r'[^"]*"')
        assert attribute.findall(html), (
            f"{PROBE_LOGO} is in the shell but not inside a closed attribute"
        )

    def test_the_logo_token_reaches_the_shell(self, shell, set_record):
        set_record("logo_url", PROBE_LOGO)

        html, _text = shell()

        assert PROBE_LOGO in html

    def test_the_footer_token_is_injected_as_structure(self, shell, set_record):
        """``footer_html`` uses ``structure``, like the body slot, so it must
        not be escaped."""
        set_record("footer_html", PROBE_FOOTER)

        html, _text = shell()

        assert "probe-footer-marker" in html
        assert "&lt;span&gt;" not in html, (
            "footer_html was HTML-escaped: it must be rendered with `structure`"
        )

    def test_tokens_do_not_disturb_the_legacy_body(self, shell, set_record):
        """Theme tokens apply around the body, not to it."""
        body = f'<p style="color: #123456;">{BODY_SENTINEL}</p>'
        set_record("logo_url", PROBE_LOGO)
        set_record("footer_html", PROBE_FOOTER)

        html, _text = shell(body=body)

        assert body in html
        assert html.count(BODY_SENTINEL) == 1
        assert PROBE_LOGO in html

    def test_inlining_still_works_with_a_token_and_a_body(self, shell, set_record):
        """A broken token form kills CSS inlining for the whole document
        while the build still succeeds."""
        set_record("logo_url", PROBE_LOGO)

        html, _text = shell(body=f"<p>{BODY_SENTINEL}</p>")

        assert support.count_inline_styles(html) >= support.MIN_INLINE_STYLES


# ===========================================================================
# ${...} inside body_html is emitted literally, never evaluated
# ===========================================================================


class TestNoTemplateInjection:
    """``structure`` must never evaluate ``${...}`` inside an injected body.

    Legacy bodies are built by string concatenation and can contain
    ``${...}`` by accident or from user input. If Chameleon evaluated it,
    the injected string would run as template code with the full render
    namespace in scope: a template-injection vulnerability.

    Each test makes evaluation visible if it happens:

    * ``${subject}`` resolves to a known value, so evaluation adds an
      extra occurrence;
    * ``${python:...}`` reads an environment variable the test sets, so
      evaluation reveals a specific value;
    * every render-namespace name gets its own ``${...}``, so a partial
      evaluation cannot hide behind an absent one.
    """

    def test_a_path_placeholder_survives_verbatim(self, shell):
        body = "<p>Bonjour ${member/fullname}, voici ${item/title}.</p>"

        html, _text = shell(body=body)

        assert "${member/fullname}" in html
        assert "${item/title}" in html
        assert body in html

    def test_a_placeholder_that_would_resolve_is_not_resolved(self, shell):
        """``${subject}`` is a real namespace name.

        Evaluated, it would appear twice: once in the heading, once in
        the body. Emitted as data, it appears once.
        """
        html, _text = shell(subject=SUBJECT_SENTINEL, body="<p>${subject}</p>")

        assert html.count(SUBJECT_SENTINEL) == 1, (
            "the injected ${subject} was evaluated: the sentinel appears "
            f"{html.count(SUBJECT_SENTINEL)} times instead of once (heading only)"
        )
        assert "<p>${subject}</p>" in html

    def test_a_python_expression_is_not_executed(self, shell, monkeypatch):
        """A ``${python:...}`` expression in the body must not execute.

        Reads an environment variable the test sets, so its presence in
        the output is the only possible evidence of execution.
        """
        readable_only_by_execution = "environ-probe-9c1f"
        monkeypatch.setenv("EMAILKIT_PROBE_VALUE", readable_only_by_execution)
        body = '<p>${python:__import__("os").environ["EMAILKIT_PROBE_VALUE"]}</p>'

        html, text = shell(body=body)

        assert readable_only_by_execution not in html, (
            "a python: expression in body_html was executed"
        )
        assert readable_only_by_execution not in text
        assert body in html

    def test_no_name_in_the_render_namespace_can_be_reached(self, shell, set_record):
        """No render-namespace name may resolve inside the body, checked
        for all of them at once.

        Theme records are set to probe values first, so a resolved
        ``${theme/primary_color}`` would produce a recognisable string.
        """
        set_record("primary_color", PROBE_COLOR)
        set_record("logo_url", PROBE_LOGO)
        placeholders = [f"${{{name}}}" for name in support.RENDER_NAMESPACE_NAMES]
        body = "<p>" + " | ".join(placeholders) + "</p>"

        html, _text = shell(body=body)

        unresolved = [
            placeholder for placeholder in placeholders if placeholder not in html
        ]
        assert unresolved == [], (
            f"these placeholders did not survive the injected body: {unresolved} "
            "-- something re-parsed body_html as a template"
        )
        assert body in html

    def test_a_tal_attribute_in_the_body_is_not_executed(self, shell):
        """``tal:content`` and ``tal:replace`` attributes in the body must
        not execute either.

        Checked on the element's own content, using the same counting
        trick as ``${subject}``: execution would put the subject
        sentinel in the body too.
        """
        body = (
            '<p tal:content="subject">original text</p>'
            '<span tal:replace="string:remplace">kept</span>'
        )

        html, _text = shell(subject=SUBJECT_SENTINEL, body=body)

        assert html.count(SUBJECT_SENTINEL) == 1, (
            "an injected tal:content was executed: the subject sentinel appears "
            f"{html.count(SUBJECT_SENTINEL)} times instead of once (heading only)"
        )
        assert "original text" in html, "an injected tal:content replaced the text"
        assert "kept" in html, "an injected tal:replace dropped the element"
        assert body in html

    def test_the_shell_itself_is_still_clean_around_an_injected_placeholder(
        self, shell
    ):
        """The shell around an injected placeholder must still be fully
        substituted.

        The body surviving verbatim must not mean the render engine
        stopped substituting elsewhere.
        """
        body = "<p>${member/fullname} ${python:1 + 1}</p>"

        html, _text = shell(body=body)

        support.assert_render_is_clean(
            without_body(html, body), "the shell around an injected placeholder"
        )


# ===========================================================================
# Pathological input: renders sanely, or fails loudly
# ===========================================================================


class TestPathologicalBodies:
    """The shell does not sanitise or rewrite ``body_html``: it wraps it.

    Every pathological body here renders verbatim, and nothing raises,
    even when the result is a degraded mail the shell does not repair.
    """

    def test_an_unclosed_tag_renders_verbatim_and_does_not_raise(self, shell):
        """An unclosed tag in the body renders verbatim; the shell does not
        raise or fix it.

        The body is never parsed, so the malformed markup reaches the
        client as given. The shell only guarantees that its own wrapper
        stays intact.
        """
        body = f"<p>Unclosed <b>{BODY_SENTINEL} and <table><tr><td>cell"

        html, text = shell(body=body)

        assert body in html
        assert html.rstrip().endswith("</html>")
        support.assert_render_is_clean(without_body(html, body), "the shell wrapper")
        assert BODY_SENTINEL in text
        assert support.HTML_TAG.findall(text) == [], (
            f"tags survived into the plaintext part: {support.HTML_TAG.findall(text)}"
        )

    def test_a_style_block_in_the_body_renders_verbatim(self, shell):
        """A ``<style>`` block in the body lands in the document body, not
        ``<head>``. The shell does not hoist or fix it.

        Checks that the shell's own head stylesheet is untouched, the
        injected block stays out of the head, and its CSS text does not
        leak into the plaintext part.
        """
        body = f"<style>.legacy{{color:#ff0000}}</style><p>{BODY_SENTINEL}</p>"

        html, text = shell(body=body)

        assert body in html
        head = support.head_of(html)
        assert "prefers-color-scheme" in head, "the shell lost its own head stylesheet"
        assert ".legacy" not in head, "the injected <style> was hoisted into the head"
        assert BODY_SENTINEL in text
        assert "#ff0000" not in text, "CSS leaked into the plaintext part"

    def test_a_whole_html_document_pasted_in_renders_nested(self, shell):
        """A pasted whole HTML document renders nested inside the shell: two
        ``<html>`` elements, one inside the other.

        Checks that the outer document is still ours: our doctype comes
        first, our ``lang`` wins over the pasted one, and our wrapper
        closes last.
        """
        body = (
            '<!DOCTYPE html><html lang="nl"><head><title>Document collé</title>'
            "<style>body{margin:0}</style></head><body>"
            f"<p>{BODY_SENTINEL}</p></body></html>"
        )

        html, text = shell(body=body, language="fr")

        assert body in html
        assert html.lower().count("<html") == 2, "the pasted document did not survive"
        assert html.lstrip().lower().startswith("<!doctype html>")
        assert html.rstrip().endswith("</html>")

        languages = support.LANG_ATTRIBUTE.findall(html)
        assert languages[0].lower() == "fr", (
            f"the outer document declares {languages[0]!r}: the pasted lang won"
        )
        assert BODY_SENTINEL in text

    def test_a_pasted_documents_head_does_not_leak_into_the_plaintext(self, shell):
        """A nested ``<head>``'s ``<title>`` must not reach the plaintext
        part.

        The extraction strips ``<style>``, ``<script>``, comments, and
        hidden elements, and must strip ``<head>`` too.
        """
        title = "Document collé"
        body = (
            f'<!DOCTYPE html><html lang="nl"><head><title>{title}</title></head>'
            f"<body><p>{BODY_SENTINEL}</p></body></html>"
        )

        _html, text = shell(body=body)

        assert title not in text, (
            f"the pasted <title> reached the plaintext part: {text.splitlines()[:4]}"
        )


# ===========================================================================
# The plaintext part of an injected body
# ===========================================================================


class TestPlaintextPart:
    """There is no ``shell.txt.pt`` twin. The plaintext part is instead a
    naive extraction from the rendered html.

    Uses a real fixture body, not a toy one, to check what happens to
    real legacy markup: nested tables, ``&nbsp;``, entities, a bare
    ``<br>``.
    """

    @pytest.fixture
    def fixture_body(self):
        return support.load_shell_fixture(support.SHELL_FIXTURES[0])

    @pytest.fixture
    def rendered(self, shell, fixture_body):
        subject, body = fixture_body
        return shell(subject=subject, body=body)

    def test_no_tags_survive(self, rendered):
        _html, text = rendered

        assert support.HTML_TAG.findall(text) == [], (
            f"tags in the plaintext part: {support.HTML_TAG.findall(text)[:5]}"
        )

    def test_the_visible_text_of_the_body_survives(self, rendered):
        """Every sentence of the legacy body must survive, not a sampled
        one."""
        _html, text = rendered

        for phrase in (
            "Bonjour,",
            "Approbation du budget 2026",
            "Décision",
            "Budget 2026",
            "Approuvé",
            "réfection de la voirie",
            "Reporté",
            "2 documents",
            "Le secrétariat communal",
            "Conseil communal",
        ):
            assert phrase in text, f"{phrase!r} was lost in the plaintext extraction"

    def test_table_cells_are_separated_not_concatenated(self, rendered):
        """Table cells get a `` | `` separator in the plaintext part, not run
        together.

        Checks both that the separator is present and that cells are
        not concatenated.
        """
        _html, text = rendered

        assert "Point | Décision" in text
        assert "PointDécision" not in text
        assert "2026 | Approuvé" in text
        assert "2026Approuvé" not in text

    def test_a_row_stays_on_one_line(self, rendered):
        """A table row must stay on one line, not split across lines."""
        _html, text = rendered

        rows = [line for line in text.splitlines() if "Reporté" in line]
        assert len(rows) == 1, f"'Reporté' is on {len(rows)} lines, expected one row"
        assert "Marché public" in rows[0], (
            f"the row split across lines: {rows[0]!r} lost its first cell"
        )

    def test_no_trailing_separator_is_left_at_end_of_line(self, rendered):
        """A line must not end with a dangling cell separator."""
        _html, text = rendered

        dangling = [line for line in text.splitlines() if line.rstrip().endswith("|")]
        assert dangling == [], f"lines ending in a cell separator: {dangling}"

    def test_the_subject_opens_the_plaintext_part(self, rendered, fixture_body):
        """The subject is the first thing a text-only client sees."""
        subject, _body = fixture_body
        _html, text = rendered

        assert text.lstrip().startswith(subject)

    def test_entities_are_decoded_not_left_literal(self, rendered):
        """HTML entities like ``&nbsp;`` and ``&laquo;`` must be decoded, not
        left literal."""
        _html, text = rendered

        assert "&nbsp;" not in text
        assert "&laquo;" not in text
        assert "&amp;" not in text
        assert "«" in text

    def test_there_is_no_invisible_filler(self, rendered):
        """Invisible characters, such as figure spaces and ``&zwj;``, must
        not reach the plaintext part."""
        _html, text = rendered

        found = support.INVISIBLE_CHARACTERS.findall(text)
        assert found == [], f"invisible characters in the plaintext part: {found!r}"

    def test_block_structure_became_line_breaks(self, rendered):
        """Block elements must become line breaks, not run together on one
        line."""
        _html, text = rendered

        lines = [line for line in text.splitlines() if line.strip()]
        assert len(lines) >= 8, f"the whole body collapsed onto {len(lines)} line(s)"
        assert not re.search(r"\n{3,}", text), (
            "runs of blank lines survived the extraction"
        )

    def test_the_css_and_the_dark_mode_stylesheet_are_gone(self, rendered):
        """The shell's head ``<style>`` block and mso comment must not reach
        the plaintext part."""
        _html, text = rendered

        assert "prefers-color-scheme" not in text
        assert "!important" not in text
        assert "<!--" not in text

    def test_the_plaintext_part_carries_no_placeholder(self, rendered):
        _html, text = rendered

        support.assert_render_is_clean(text, "the shell plaintext part")

    def test_there_is_no_plaintext_twin_and_none_is_warned_about(
        self, integration, caplog, fixture_body
    ):
        """The shell ships no ``.txt.pt`` twin, and rendering it logs no
        deprecation for a missing twin.

        A twin's only content would be ``body_html``, which is HTML, so
        adding one would put tags in the plaintext part.
        """
        from imio.emailkit.discovery import TEXT_SUFFIX
        from imio.emailkit.render import SHELL_TEMPLATE

        import logging

        twin = SHELL_TEMPLATE.parent / f"{SHELL_TEMPLATE.stem}{TEXT_SUFFIX}"
        assert not twin.exists(), (
            f"{twin.name} was added: a plaintext twin of the shell can only "
            "contain body_html, which is HTML"
        )

        subject, body = fixture_body
        with caplog.at_level(logging.WARNING, logger="imio.emailkit.render"):
            render_shell(subject, body, language="fr")

        deprecations = [
            record.getMessage()
            for record in caplog.records
            if "DEPRECATION" in record.getMessage()
        ]
        assert deprecations == [], (
            f"render_shell logged the missing-twin deprecation: {deprecations}"
        )


# ===========================================================================
# Language: subject msgid translated, lang correct, FR != NL
# ===========================================================================


class TestLanguage:
    """``subject`` accepts a msgid or a literal. The shell shares
    ``render()``'s namespace, theme tokens, and locale helpers.

    Expected subjects are computed through ``zope.i18n``, not hardcoded,
    so a catalog edit cannot silently break these tests.
    """

    #: A msgid whose FR and NL translations genuinely differ, so a
    #: passed-through msgid can be told apart from a translated one.
    MSGID = support.OVERRIDE_SUBJECT_MSGID

    @pytest.fixture
    def msgid(self):
        return support.message_id(self.MSGID, default="Password reset request")

    @pytest.mark.parametrize("language", ["fr", "nl", "en"])
    def test_the_subject_msgid_is_translated(self, shell, msgid, language):
        expected = support.translated(msgid, language)

        html, text = shell(subject=msgid, language=language)

        assert expected != self.MSGID, (
            f"{self.MSGID} has no {language} translation, so this test cannot "
            "distinguish a translated subject from a passed-through msgid"
        )
        assert expected in html, f"the {language} subject is not in the shell heading"
        assert expected in text
        assert self.MSGID not in html, "the bare msgid reached the output"

    def test_a_literal_subject_is_passed_through_unchanged(self, shell):
        """A literal subject must pass through unchanged; no catalog may
        touch it."""
        html, _text = shell(subject=SUBJECT_SENTINEL, language="nl")

        assert SUBJECT_SENTINEL in html

    @pytest.mark.parametrize("language", ["fr", "nl", "de", "en"])
    def test_lang_matches_the_requested_language(self, shell, language):
        html, _text = shell(language=language)

        match = support.LANG_ATTRIBUTE.search(html)

        assert match, "no lang attribute on <html>"
        assert match.group(1).lower().startswith(language)

    def test_fr_and_nl_differ(self, shell, msgid):
        """The whole point of the per-language send, at the shell's level."""
        fr_html, fr_text = shell(subject=msgid, language="fr")
        nl_html, nl_text = shell(subject=msgid, language="nl")

        assert fr_html != nl_html
        assert fr_text != nl_text

    def test_the_legacy_body_is_not_translated(self, shell, msgid):
        """The legacy body must render identically in every language, byte
        for byte."""
        body = f"<p>{BODY_SENTINEL} &laquo;&nbsp;texte&nbsp;&raquo;<br></p>"

        fr_html, _ = shell(subject=msgid, body=body, language="fr")
        nl_html, _ = shell(subject=msgid, body=body, language="nl")

        assert body in fr_html
        assert body in nl_html
        assert fr_html.count(BODY_SENTINEL) == nl_html.count(BODY_SENTINEL) == 1

    def test_rendering_twice_in_two_languages_does_not_leak(self, shell, msgid):
        """The compiled shell is cached and shared by every caller. A cached
        language must not leak into a later render in another language."""
        first, _ = shell(subject=msgid, language="fr")
        _dutch, _ = shell(subject=msgid, language="nl")
        again, _ = shell(subject=msgid, language="fr")

        assert first == again

    def test_omitting_the_language_uses_the_negotiated_one(self, shell, integration):
        """Omitting the language uses the request's negotiated language.

        Compared against the request's own ``LANGUAGE``, not a hardcoded
        code.
        """
        request = integration["request"]
        negotiated = request.get("LANGUAGE", None)
        assert negotiated, "this layer's request has no negotiated LANGUAGE to check"

        default_html, _ = render_shell(SUBJECT_SENTINEL, SIMPLE_BODY)
        explicit_html, _ = render_shell(
            SUBJECT_SENTINEL, SIMPLE_BODY, language=negotiated
        )

        assert default_html == explicit_html


class TestPureFunction:
    """``render_shell`` must be pure, like ``render()``, since it shares the
    same code path."""

    def test_render_shell_is_repeatable(self, shell):
        assert shell() == shell()

    def test_two_bodies_do_not_bleed_into_each_other(self, shell):
        """The shell is one cached template shared by every caller. A body
        must not leak from one render into the next."""
        first, _ = shell(body=f"<p>{BODY_SENTINEL}</p>")
        second, _ = shell(body="<p>autre corps</p>")

        assert BODY_SENTINEL in first
        assert BODY_SENTINEL not in second
        assert "autre corps" in second
        assert "autre corps" not in first
