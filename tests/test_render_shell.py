"""SPEC §9 phase 3 -- ``render_shell(subject, body_html, language=None)``.

``docs/plans/phase-3.md`` §4's nine gates, minus the two that have their own
modules: gate 4 (the PloneMeeting-shaped golden) lives in ``tests/test_golden.py``
because it *is* the golden harness, and gate 8 (sending shell output through the
frozen builder) lives in ``tests/test_shell_send.py`` because it needs the sending
layer.

**The rule this module exists to enforce**, same as ``tests/test_render.py``:
assert on *substituted values*, never on marker strings. Without the
``IPageTemplateEngine`` utility ``zope.pagetemplate`` falls back to ``zope.tal``,
where ``${...}`` passes through verbatim and raises nothing -- so "our marker is in
the output" can be true while raw placeholders ship.

Phase 3 turns that hazard inside out. For an *authored* template a surviving
``${...}`` is a defect; for an *injected legacy body* it is the required
behaviour, and the two must not be confused. Hence the shape of the tests below:

* the shell's **own** markup is held to the usual standard -- no placeholder, no
  TAL residue, CSS inlined, a11y defaults present;
* the **injected body** is held to the opposite standard -- byte-for-byte verbatim,
  never evaluated, never sanitised (``docs/plans/phase-3.md`` §5: "the shell wraps;
  it does not clean");
* so the cleanliness assertions run on ``html`` with the injected body *removed*,
  which is the only way to make both statements at once.

``docs/DECISIONS.md`` ("``structure`` does NOT evaluate placeholders in an injected
body") records the empirical verification this module is the regression test for.
That entry is why ``structure`` is considered safe here at all; if these tests go
red, that conclusion is what changed.
"""

import pytest
import re
import support


render_shell = support.require_shell()

from imio.emailkit import render  # noqa: E402


# ---------------------------------------------------------------------------
# Identities. Chosen so that finding one in the output can only mean one thing.
# ---------------------------------------------------------------------------

#: A subject with characters that *must* be escaped. §3 rule 4 reserves
#: ``structure`` for the body slot, so everything else -- the heading included --
#: is escaped by Chameleon's default. A subject computed from user-entered content
#: (an item title, say) is exactly where that matters.
SUBJECT_WITH_MARKUP = 'Séance <script>alert("x")</script> & suite'

#: A subject that cannot collide with anything in the kit, for counting.
SUBJECT_SENTINEL = "SUJET-SENTINELLE-3f9a"

#: The simplest possible legacy body -- plan §4 gate 1, verbatim.
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

#: A hidden element whose content is not a comment -- i.e. a preheader. The kit
#: renders one for an authored template (§3, §4) and, per
#: ``emails/src/templates/shell.vue``, deliberately none for the shell.
HIDDEN_ELEMENT = re.compile(
    r"<(?P<tag>div|span|p)[^>]*display:\s*none[^>]*>(?P<inner>.*?)</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)

#: An HTML comment, including Outlook's conditional blocks -- the *only* thing the
#: shell's one hidden element is allowed to contain.
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@pytest.fixture
def shell(integration):
    """``shell(subject, body, language="fr")`` -> ``(html, text)``.

    Bound to the ``integration`` layer because the theme tokens come from
    ``plone.app.registry`` (§3) and the subject is translated through
    ``zope.i18n`` -- both need a site.
    """

    def make(subject=SUBJECT_SENTINEL, body=SIMPLE_BODY, language="fr"):
        return render_shell(subject, body, language=language)

    return make


@pytest.fixture
def authored(integration):
    """The same kit layout with *authored* content, for parity assertions.

    Gate 2 is "exactly as for an authored template", which is a comparison, not a
    marker list. Rendering the real registered template in the same language and
    the same registry state is the only way to make it one.
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
    """Set one SPEC §3 theme record, asserting the profile installed it first."""
    from plone.registry.interfaces import IRegistry
    from zope.component import getUtility

    def setter(name, value):
        registry = getUtility(IRegistry)
        record = support.THEME_RECORDS[name]
        assert record in registry.records, (
            f"{record} is not in the registry -- the {support.PACKAGE_NAME} "
            "profile did not install the theme tokens (SPEC §3)"
        )
        registry[record] = value

    return setter


def without_body(html, body):
    """``html`` with the injected body removed, for the cleanliness assertions.

    The injected body is allowed -- required, even -- to contain ``${...}`` and
    ``tal:`` attributes verbatim. The shell around it is not. Removing the one
    string the caller handed in is what lets both be asserted, and it fails loudly
    if the body was *not* emitted verbatim, which is itself the point.
    """
    assert body in html, "the injected body is not in the output verbatim"
    return html.replace(body, "")


def visible_hidden_text(html):
    """The non-comment text inside every ``display: none`` element.

    Empty means "no preheader". The kit's shell keeps one hidden element for
    Outlook's ``<o:OfficeDocumentSettings>`` conditional comment, which is markup
    for Word and not text for a human, so comments are stripped before looking.
    """
    return [
        stripped
        for match in HIDDEN_ELEMENT.finditer(html)
        if (stripped := COMMENT.sub("", match.group("inner")).strip())
    ]


# ===========================================================================
# Gate 1 -- returns (html, text); the body appears unescaped inside the shell
# ===========================================================================


class TestReturnValue:
    def test_returns_html_and_text(self, shell):
        """Plan §2: "Returns ``(html, text)`` exactly as ``render()`` does"."""
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
        """Gate 1. §3 rule 4's one sanctioned use of ``structure``.

        An escaped body is the visible symptom of the wrong idiom and it would
        turn every migrated notification into a mail full of ``&lt;p&gt;`` -- the
        exact opposite of "zero template redesign".
        """
        html, _text = shell(body=f"<p>{BODY_SENTINEL}</p>")

        assert f"<p>{BODY_SENTINEL}</p>" in html
        assert "&lt;p&gt;" not in html

    def test_the_body_appears_exactly_once(self, shell):
        """``Main.vue`` owns the ``body_html`` slot and ``shell.vue`` adds only the
        heading. A second slot in the shell would duplicate every legacy body --
        which reads as a rendering bug nobody would attribute to the shell.
        """
        body = f"<p>{BODY_SENTINEL}</p>"

        html, _text = shell(body=body)

        assert html.count(BODY_SENTINEL) == 1, (
            f"the injected body appears {html.count(BODY_SENTINEL)} times; the "
            "layout must render the body_html slot exactly once"
        )

    def test_the_body_sits_inside_the_document_body(self, shell):
        """Not merely "present somewhere". A body emitted into ``<head>`` would be
        invisible in every client while every marker assertion still passed."""
        body = f"<p>{BODY_SENTINEL}</p>"

        html, _text = shell(body=body)

        assert html.index("<body") < html.index(BODY_SENTINEL) < html.index("</body>")

    def test_the_shell_around_the_body_is_clean(self, shell):
        """The shell's own markup is held to ``tests/test_render.py``'s standard:
        no unsubstituted ``${...}``, no leftover ``tal:``/``i18n:``."""
        body = f"<p>{BODY_SENTINEL}</p>"

        html, text = shell(body=body)

        support.assert_render_is_clean(without_body(html, body), "the shell html")
        support.assert_render_is_clean(
            text.replace(BODY_SENTINEL, ""), "the shell text"
        )

    def test_the_subject_is_escaped(self, shell):
        """The other half of §3 rule 4: everything that is *not* the body slot is
        escaped. A subject is often computed from an item title, so it is
        user-influenced content in a heading -- and the shell is the one place in
        this package where escaped and unescaped injection sit side by side.
        """
        html, _text = shell(subject=SUBJECT_WITH_MARKUP)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "&amp; suite" in html

    def test_an_empty_subject_collapses_the_heading(self, shell):
        """An empty string is not a missing name: it renders a mail with no
        heading rather than raising, so a caller with nothing to say in the
        heading has a way to say nothing."""
        html, _text = shell(subject="", body=f"<p>{BODY_SENTINEL}</p>")

        assert BODY_SENTINEL in html
        assert "<h1" not in html
        support.assert_render_is_clean(
            html.replace(BODY_SENTINEL, ""), "the headless shell"
        )

    def test_an_empty_body_collapses_the_slot(self, shell):
        """The mirror case: subject, no body. The shell must still be a valid,
        complete document -- an exception here would make ``render_shell`` unusable
        for a notification whose body happens to be empty that day."""
        html, text = shell(subject=SUBJECT_SENTINEL, body="")

        assert SUBJECT_SENTINEL in html
        assert "</html>" in html
        assert SUBJECT_SENTINEL in text
        support.assert_render_is_clean(html.replace(SUBJECT_SENTINEL, ""), "empty body")


class TestTheCompiledShellRequiresASubject:
    """The compiled shell's own contract, asserted directly on the artifact.

    ``render_shell``'s signature makes ``subject`` mandatory, so the public API can
    never omit it. The compiled ``shell.pt`` is nonetheless a *shipped file* that
    ``z3c.jbot`` can override and that a future caller could render another way,
    and its ``tal:condition="subject"`` is what makes a missing name a loud
    ``KeyError`` instead of a silently headless mail. Adding a ``| nothing``
    default to that expression would be a one-character change with no visible
    symptom; this is the test that would object.
    """

    def test_a_missing_subject_name_raises(self, integration):
        from imio.emailkit.render import build_namespace
        from imio.emailkit.render import render_file
        from imio.emailkit.render import SHELL_TEMPLATE

        namespace = build_namespace({"body_html": SIMPLE_BODY}, "fr")

        with pytest.raises(KeyError):
            render_file(SHELL_TEMPLATE, namespace)

    def test_a_missing_body_html_name_renders_a_shell_with_no_body(self, integration):
        """Deliberately *not* symmetrical, and worth pinning as such: a mail with
        a heading and no body is a degraded mail, while a mail with no heading at
        all is a broken one."""
        from imio.emailkit.render import build_namespace
        from imio.emailkit.render import render_file
        from imio.emailkit.render import SHELL_TEMPLATE

        namespace = build_namespace({"subject": SUBJECT_SENTINEL}, "fr")

        html = render_file(SHELL_TEMPLATE, namespace)

        assert SUBJECT_SENTINEL in html
        assert "</html>" in html


# ===========================================================================
# Gate 2 -- inlined CSS, a11y defaults, lang, layout structure: as authored
# ===========================================================================


class TestKitDefaultsAroundALegacyBody:
    """Gate 2. The shell is the kit layout with the content handed in, so every
    §3 default has to survive the swap. Each of these is a feature §3 says
    "the kit does, not authors" -- and a legacy body is precisely the case where
    nobody is watching the markup."""

    def test_the_document_head_is_identical_to_an_authored_templates(
        self, shell, authored
    ):
        """ "Exactly as for an authored template", asserted as an equality.

        The head is what the layout alone owns: charset, viewport, the
        colour-scheme meta pair, the dark-mode ``<style>`` block, the ``<html>``
        attributes. A shell built on a forked layout, or one that lost the
        dark-mode stylesheet, differs here and nowhere a marker would notice.

        If a template ever legitimately contributes head content, this assertion
        is the place to narrow the comparison -- deliberately, with a reason.
        """
        shell_html, _ = shell()
        authored_html, _ = authored()

        assert support.head_of(shell_html) == support.head_of(authored_html)

    def test_layout_tables_are_marked_presentational(self, shell):
        """§3: ``role="presentation"`` on all layout tables. Without it a screen
        reader announces the mail cell by cell."""
        html, _text = shell()

        assert support.A11Y_TABLE_MARKER in html

    def test_every_table_in_the_shell_is_presentational(self, shell):
        """The stronger form, and the one §3 actually says ("*all* layout
        tables"). Only the shell's own tables are counted: a legacy body brings
        its own data tables, and a data table with ``role="presentation"`` would
        be an a11y bug in the other direction.

        ``role="none"`` counts. ARIA 1.1 made it the synonym of
        ``role="presentation"`` -- identical semantics, identical screen-reader
        behaviour -- and the kit uses it on the table inside the ``[if mso]``
        conditional comment. Insisting on one spelling would be a lint rule
        masquerading as an accessibility assertion.
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
        """§3: "enforced ``alt`` on the logo/``Img`` component".

        The logo only renders when the token is set, so the token is set first --
        otherwise this test would pass by finding no image at all.
        """
        set_record("logo_url", PROBE_LOGO)

        html, _text = shell()

        index = html.find(PROBE_LOGO)
        assert index != -1, f"{PROBE_LOGO} never reached the shell"
        tag = html[html.rfind("<", 0, index) : html.find(">", index) + 1]
        assert "alt=" in tag, f"logo <img> has no alt attribute: {tag}"

    def test_lang_is_emitted_on_html(self, shell):
        """§3: "the layout emits ``lang="${lang}"`` on ``<html>``"."""
        html, _text = shell(language="fr")

        match = support.LANG_ATTRIBUTE.search(html)

        assert match, "no lang attribute on <html> (SPEC §3 a11y default)"
        assert match.group(1).lower().startswith("fr")

    def test_css_was_inlined(self, shell):
        """Phase 0 caveat A1: one ``${...}`` in a literal ``style`` attribute stops
        Juice inlining document-wide while the build still reports success. The
        shell is a *separate build output*, so it can lose inlining on its own.
        """
        html, _text = shell()

        count = support.count_inline_styles(html)

        assert count >= support.MIN_INLINE_STYLES, (
            f"only {count} inline style attributes in the shell: CSS inlining is "
            "probably dead (Phase 0 caveat A1)"
        )

    def test_dark_mode_survives(self, shell, authored):
        """``docs/DECISIONS.md``: dark mode is attribute selectors plus
        ``data-dark`` hooks. Head parity covers the stylesheet; this covers the
        hooks, which live in the body and are therefore the half the shell could
        lose on its own."""
        shell_html, _ = shell()
        authored_html, _ = authored()

        assert "data-dark=" in shell_html
        assert shell_html.count("data-dark=") == authored_html.count("data-dark=")

    def test_the_shell_renders_no_preheader(self, shell, authored):
        """Gate 2 as the plan words it says the preheader must be present; the
        shell deliberately renders none, and this test records that.

        ``emails/src/templates/shell.vue``'s reasoning: the first visible text of a
        shell mail is already the subject, so a hidden preheader would spend the
        whole inbox-snippet budget repeating the subject line the client shows
        anyway, and the snippet would stop before it reached a single word of the
        legacy body.

        Asserted as a pair, so that neither half can pass vacuously: the layout's
        preheader path *works* (the authored template's registration msgid is
        rendered into a hidden element) and the shell uses *none* of it. A shell
        that started emitting a preheader, or a layout that lost the feature, each
        fail exactly one half.
        """
        shell_html, _ = shell()
        authored_html, _ = authored(language="en")

        assert visible_hidden_text(authored_html), (
            "the authored template renders no preheader at all: SPEC §4's "
            "registration msgid never reached the layout's hidden div"
        )
        assert visible_hidden_text(shell_html) == [], (
            "the shell rendered a preheader: "
            f"{visible_hidden_text(shell_html)}. See emails/src/templates/"
            "shell.vue for why it deliberately does not."
        )


# ===========================================================================
# Gate 3 -- theme tokens apply to the shell around a legacy body
# ===========================================================================


class TestThemeTokens:
    """Gate 3. §8.2 level 2 makes these three records "the majority of
    per-commune needs without touching markup" -- which has to include the
    migrated PloneMeeting mails, or the shell is the one mail flow where a commune
    cannot be branded."""

    def test_changing_the_logo_token_changes_the_shell(self, shell, set_record):
        set_record("logo_url", PROBE_LOGO)
        first, _ = shell()

        set_record("logo_url", OTHER_LOGO)
        second, _ = shell()

        assert PROBE_LOGO in first, (
            f"{PROBE_LOGO} never reached the shell: the theme token is not "
            "rendered (Phase 0 caveat A1 -- it must arrive via tal:attributes)"
        )
        assert OTHER_LOGO in second
        assert PROBE_LOGO not in second, "the render cached the old token value"

    def test_primary_color_has_no_surface_left_in_the_shell(self, shell, set_record):
        """The v3 design took the flat colour out of the title band.

        It was the one place the shell painted `primary_color`: a magenta band
        holding the subject in white. v3 makes that band #f8f8f8 with ink type
        under the head artwork, and the token moved to `KitCard`'s rail and
        `KitButton`'s fill -- neither of which a shell around a legacy body has.

        So the token reaches every other template and no longer reaches this one,
        and that asymmetry is worth pinning: it is the visible cost of the
        redesign for the PloneMeeting migration path, not an accident, and if a
        later change gives the shell a coloured surface again this test is where
        the decision gets revisited. `tests/test_theme_tokens.py` keeps caveat
        A1's guard on the four templates that do paint with it.
        """
        set_record("primary_color", PROBE_COLOR)

        html, _text = shell(body=f"<p>{BODY_SENTINEL}</p>")

        assert PROBE_COLOR not in html

    def test_the_token_lands_in_a_closed_attribute(self, shell, set_record):
        """Caveat A1's broken form put the token in the output too, as
        ``style="background-image:${theme/logo_url"`` -- present and useless."""
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
        """§3 rule 4 reserves ``structure`` for two things: the body slot and
        ``footer_html``. The shell uses both at once, which is the only render in
        this package where a mistake in one could look like the other."""
        set_record("footer_html", PROBE_FOOTER)

        html, _text = shell()

        assert "probe-footer-marker" in html
        assert "&lt;span&gt;" not in html, (
            "footer_html was HTML-escaped: it must be rendered with `structure`"
        )

    def test_tokens_do_not_disturb_the_legacy_body(self, shell, set_record):
        """The point of gate 3: tokens apply *around* the body, not to it."""
        body = f'<p style="color: #123456;">{BODY_SENTINEL}</p>'
        set_record("logo_url", PROBE_LOGO)
        set_record("footer_html", PROBE_FOOTER)

        html, _text = shell(body=body)

        assert body in html
        assert html.count(BODY_SENTINEL) == 1
        assert PROBE_LOGO in html

    def test_inlining_still_works_with_a_token_and_a_body(self, shell, set_record):
        """Caveat A1's other half: the bad token form did not only break the
        token, it killed inlining for the whole document with the build green."""
        set_record("logo_url", PROBE_LOGO)

        html, _text = shell(body=f"<p>{BODY_SENTINEL}</p>")

        assert support.count_inline_styles(html) >= support.MIN_INLINE_STYLES


# ===========================================================================
# Gate 5 -- ${...} inside body_html is emitted literally, never evaluated
# ===========================================================================


class TestNoTemplateInjection:
    """Gate 5, the load-bearing gate of Phase 3 (plan §6: "the load-bearing risk
    of this phase; the answer determines whether ``structure`` is safe here at
    all").

    Legacy notification bodies are assembled by string concatenation, so one can
    contain ``${...}`` by accident or through user-entered content. If Chameleon
    evaluated it, the injected string would be executable template code with the
    full render namespace in scope -- a template-injection vulnerability, not a
    cosmetic defect.

    ``docs/DECISIONS.md`` records the verification that it does not: ``structure``
    inserts the string as markup *data*, and the compiled template is never
    re-parsed. These are the regression tests for that conclusion, and they are
    written so that an evaluation would be *visible* rather than merely
    unasserted:

    * a placeholder that resolves to a value the test controls (``${subject}``) is
      **counted**, so evaluation shows up as one occurrence too many;
    * a ``${python:...}`` reads an environment variable the test sets, so
      evaluation shows up as a specific secret string in the output;
    * every name the render namespace holds gets its own ``${...}``, so a partial
      evaluation cannot hide behind the ones that happen to be absent.
    """

    def test_a_path_placeholder_survives_verbatim(self, shell):
        body = "<p>Bonjour ${member/fullname}, voici ${item/title}.</p>"

        html, _text = shell(body=body)

        assert "${member/fullname}" in html
        assert "${item/title}" in html
        assert body in html

    def test_a_placeholder_that_would_resolve_is_not_resolved(self, shell):
        """The counting test, and the sharpest one available.

        ``${subject}`` is a name that genuinely *is* in the namespace with a value
        this test chose. Evaluated, the sentinel would appear twice -- once in the
        heading, once in the body. Emitted as data, exactly once. No other
        assertion in this module can distinguish "not evaluated" from "the name
        happened not to resolve".
        """
        html, _text = shell(subject=SUBJECT_SENTINEL, body="<p>${subject}</p>")

        assert html.count(SUBJECT_SENTINEL) == 1, (
            "the injected ${subject} was evaluated: the sentinel appears "
            f"{html.count(SUBJECT_SENTINEL)} times instead of once (heading only)"
        )
        assert "<p>${subject}</p>" in html

    def test_a_python_expression_is_not_executed(self, shell, monkeypatch):
        """The ``${python:...}`` form, reading something only the process knows.

        A literal-survival assertion alone would not settle this: a ``python:``
        expression that raised would also leave no value behind. Reading an
        environment variable the test sets means the *presence* of that value is
        the only possible evidence of execution, and its absence is the only
        possible evidence of none.
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
        """Every documented namespace name at once (§6.1, §3, §4).

        A test that probed one name would pass while another leaked. The theme
        records are set to probe values first, so a ``${theme/primary_color}`` that
        *did* resolve would produce a string this test can recognise instead of a
        colour that also legitimately appears in the shell.
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
        """The other injection surface, and the one nobody thinks of.

        ``${...}`` is not the only template syntax: ``tal:content`` on an injected
        element would replace its text and ``tal:replace`` would drop the element.
        The same mechanism protects both -- the body is data -- so the same test
        proves both.

        Asserted on *what would change*, not on the expression text: an injected
        ``tal:content="python:'X'"`` contains the string ``X`` in its attribute
        whether it ran or not, so the only sound evidence is the element's own
        content. Hence ``tal:content="subject"`` and the counting trick again: the
        sentinel is in the namespace, so execution would put it in the body as
        well as in the heading.
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
        """The half a naive reading would get backwards.

        "``${...}`` survives" must not become "the render engine stopped
        substituting". So with a ``${...}``-carrying body injected, the shell
        *around* it is asserted to be fully substituted -- which is only checkable
        because the body is emitted verbatim and can be removed.
        """
        body = "<p>${member/fullname} ${python:1 + 1}</p>"

        html, _text = shell(body=body)

        support.assert_render_is_clean(
            without_body(html, body), "the shell around an injected placeholder"
        )


# ===========================================================================
# Gate 6 -- pathological input: renders sanely, or fails loudly
# ===========================================================================


class TestPathologicalBodies:
    """Gate 6, and the honest answer is the same for all three: **every one of
    them renders, verbatim, and nothing raises.**

    That is the direct consequence of plan §5's "no sanitising or rewriting of
    ``body_html``. The shell wraps; it does not clean." The tests below therefore
    assert what actually happens rather than what would be nice, and each docstring
    records the consequence -- including the two where the consequence is a
    degraded mail that the shell deliberately does not repair (an unbalanced
    document; a ``<style>`` block most clients drop).

    Writing them turned up one outcome that was neither sane nor loud: a pasted
    whole document leaked its ``<title>`` into the plaintext part. That was a real
    defect rather than a documented trade-off, and it was fixed in the extraction --
    ``test_a_pasted_documents_head_does_not_leak_into_the_plaintext`` is its
    regression test.
    """

    def test_an_unclosed_tag_renders_verbatim_and_does_not_raise(self, shell):
        """**Outcome: renders. The document is malformed, by construction.**

        ``<p>Unclosed <b>bold`` is emitted exactly as given, so the shell's own
        ``</div></td></tr></table>`` trailer closes while the body's ``<b>`` and
        ``<table>`` are still open. No parser sees this at render time -- the body
        is data -- so the malformed markup reaches the client, which auto-closes
        it as browsers and mail clients have always done.

        This is the designed behaviour, not a gap: a shell that "fixed" a
        consumer's markup would be silently changing mails nobody asked it to
        change (plan §5). What the shell does guarantee is that *its own* wrapper
        is intact, which is what the last two assertions check -- the header, the
        footer and the closing tags all survive an unbalanced body.
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
        """**Outcome: renders. The ``<style>`` lands in the document body.**

        Which is invalid placement per the HTML spec and is stripped outright by
        Gmail and by Outlook.com, so a legacy body relying on its own ``<style>``
        block will lose that styling in most clients. Not something the shell can
        fix: hoisting the block into ``<head>`` would mean parsing and rewriting
        the body, and the block might collide with the kit's own inlined CSS.

        What *is* asserted: the shell's own head stylesheet (dark mode) is
        untouched, the injected block did not migrate into the head, and the CSS
        text does not leak into the plaintext part.
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
        """**Outcome: renders. Two ``<html>`` elements, one inside the other.**

        A pasted ``<!DOCTYPE html><html>…</html>`` is emitted verbatim into the
        slot, so the result is a document containing a document: nested ``<html>``,
        ``<head>`` and ``<body>``, plus a second ``lang`` declaration. Every mail
        client tolerates this -- they all normalise, most strip ``<head>`` entirely
        -- and the visible text renders inside the shell.

        The properties that matter, and are asserted, are that the *outer*
        document is still ours: our doctype comes first, our ``lang`` is the render
        language and not the pasted one, and our wrapper closes last. Which is
        also why the pasted ``lang="nl"`` below is written with the same double
        quotes our layout uses -- so that a shell which let the inner declaration
        win would be caught rather than missed on a quoting technicality.
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
        """A nested ``<head>`` must not contribute its ``<title>`` to text/plain.

        Found by gate 6 as a real leak and fixed rather than left as a known gap:
        the extraction stripped ``<style>``, ``<script>``, comments and hidden
        elements but not ``<head>``, so a pasted whole document glued its title to
        the first line of the body. Only ever visible in the plaintext part --
        clients drop the nested head from the HTML one -- which is exactly the kind
        of defect nobody would have noticed in a browser preview.
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
# Gate 7 -- the plaintext part of an injected body
# ===========================================================================


class TestPlaintextPart:
    """Gate 7. There is deliberately no ``shell.txt.pt`` twin -- its only content
    would be ``body_html``, which is HTML -- so the plaintext part is §4's naive
    extraction of the rendered document. That makes it the one part of
    ``render_shell``'s output that is *derived* rather than composed, and the part
    nobody looks at until a client renders only that.

    The fixture body is used rather than a toy one: gate 7 is about what happens to
    real legacy markup -- nested tables, ``&nbsp;``, entities, a bare ``<br>``.
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
        """Every sentence of the legacy body, not a sampled one. A stripper that
        ate table cells or dropped everything after the first ``<table>`` would
        still pass a single-marker check."""
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
        """``docs/DECISIONS.md``, "Plaintext: table cells get a `` | `` separator".

        Legacy notification bodies are table-heavy and ``render_shell`` has no
        plaintext twin to fall back on, so what this extraction does to a ``<tr>``
        *is* the plaintext part of every migrated PloneMeeting mail. Concatenated
        cells produced ``PointDécision`` and ``Budget 2026Approuvé`` -- readable as
        neither a table nor a sentence, and the kind of defect that only ever shows
        up in the one client that renders ``text/plain``.

        Both halves are asserted: the separator is there, and the old
        concatenation is not. The negative half is what keeps this from passing
        again if a future change puts a newline between cells instead.
        """
        _html, text = rendered

        assert "Point | Décision" in text
        assert "PointDécision" not in text
        assert "2026 | Approuvé" in text
        assert "2026Approuvé" not in text

    def test_a_row_stays_on_one_line(self, rendered):
        """The reason the separator was chosen over a line break: a two-cell row
        read as two unrelated lines, so nothing said which decision belonged to
        which point."""
        _html, text = rendered

        rows = [line for line in text.splitlines() if "Reporté" in line]
        assert len(rows) == 1, f"'Reporté' is on {len(rows)} lines, expected one row"
        assert "Marché public" in rows[0], (
            f"the row split across lines: {rows[0]!r} lost its first cell"
        )

    def test_no_trailing_separator_is_left_at_end_of_line(self, rendered):
        """The last cell of a row leaves a separator with nothing after it. A
        plaintext part whose every table line ends in `` |`` looks like a rendering
        accident, which is what it would be."""
        _html, text = rendered

        dangling = [line for line in text.splitlines() if line.rstrip().endswith("|")]
        assert dangling == [], f"lines ending in a cell separator: {dangling}"

    def test_the_subject_opens_the_plaintext_part(self, rendered, fixture_body):
        """The subject is the first thing a text-only client sees, which is the
        stated reason the shell renders no preheader."""
        subject, _body = fixture_body
        _html, text = rendered

        assert text.lstrip().startswith(subject)

    def test_entities_are_decoded_not_left_literal(self, rendered):
        """``&nbsp;``, ``&laquo;`` and friends are French typography in these
        bodies. Left literal they are noise in every line."""
        _html, text = rendered

        assert "&nbsp;" not in text
        assert "&laquo;" not in text
        assert "&amp;" not in text
        assert "«" in text

    def test_there_is_no_invisible_filler(self, rendered):
        """The kit pads its preheader with figure spaces and joins Outlook spacer
        cells with ``&zwj;``. Both are invisible in HTML and mojibake in a
        plaintext part -- and the naive extraction sees them after decoding."""
        _html, text = rendered

        found = support.INVISIBLE_CHARACTERS.findall(text)
        assert found == [], f"invisible characters in the plaintext part: {found!r}"

    def test_block_structure_became_line_breaks(self, rendered):
        """A plaintext part where every table row ran together on one line is
        technically tag-free and unreadable."""
        _html, text = rendered

        lines = [line for line in text.splitlines() if line.strip()]
        assert len(lines) >= 8, f"the whole body collapsed onto {len(lines)} line(s)"
        assert not re.search(r"\n{3,}", text), (
            "runs of blank lines survived the extraction"
        )

    def test_the_css_and_the_dark_mode_stylesheet_are_gone(self, rendered):
        """The shell's head carries a ``<style>`` block and an mso conditional
        comment. Either one reaching the plaintext part would put CSS in front of
        the message."""
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
        """The naive extraction is the shell's *designed* path, not §4's fallback.

        §4 says a template with no ``.txt.pt`` twin gets "a warning at startup" and
        "a logged deprecation" on every render. For the shell that would be a
        deprecation warning nobody can ever act on: a twin's only content would be
        ``body_html``, which is HTML, so the twin would put tags in the plaintext
        part. Both halves are pinned here -- no twin is shipped, and rendering the
        shell logs no deprecation -- because the natural "fix" for the log line
        (adding a ``shell.txt.pt``) would silently make every migrated mail's
        plaintext part worse.
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
            f"render_shell logged §4's missing-twin deprecation: {deprecations}"
        )


# ===========================================================================
# Gate 9 -- language: subject msgid translated, lang correct, FR != NL
# ===========================================================================


class TestLanguage:
    """Gate 9. Plan §2: ``subject`` "accepts a msgid or a literal, like
    ``.subject()``" and the shell shares ``render()``'s "same namespace, theme
    tokens and locale helpers -- one code path, not a parallel one".

    Expected subjects are *computed* through ``zope.i18n``, never typed in: a
    hardcoded French string would fail on any catalog edit and -- worse -- would
    still pass if ``render_shell`` shipped the bare msgid whenever the catalog had
    no entry.
    """

    #: A msgid in this package's own domain whose FR and NL entries genuinely
    #: differ. ``email_subject_notification`` translates to "Notification" in both
    #: FR and EN, so it cannot tell "translated" from "passed through".
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
        """§6.2: "accepts a msgid or literal string". A literal is not a msgid, so
        no catalog may touch it."""
        html, _text = shell(subject=SUBJECT_SENTINEL, language="nl")

        assert SUBJECT_SENTINEL in html

    @pytest.mark.parametrize("language", ["fr", "nl", "de", "en"])
    def test_lang_matches_the_requested_language(self, shell, language):
        html, _text = shell(language=language)

        match = support.LANG_ATTRIBUTE.search(html)

        assert match, "no lang attribute on <html>"
        assert match.group(1).lower().startswith(language)

    def test_fr_and_nl_differ(self, shell, msgid):
        """The whole point of §6.2's per-language send, at the shell's level."""
        fr_html, fr_text = shell(subject=msgid, language="fr")
        nl_html, nl_text = shell(subject=msgid, language="nl")

        assert fr_html != nl_html
        assert fr_text != nl_text

    def test_the_legacy_body_is_not_translated(self, shell, msgid):
        """The body is the consumer's markup in whatever language they built it.
        It must come out identical in every language group -- byte-for-byte, since
        an i18n pass over it would be a silent rewrite of a mail body."""
        body = f"<p>{BODY_SENTINEL} &laquo;&nbsp;texte&nbsp;&raquo;<br></p>"

        fr_html, _ = shell(subject=msgid, body=body, language="fr")
        nl_html, _ = shell(subject=msgid, body=body, language="nl")

        assert body in fr_html
        assert body in nl_html
        assert fr_html.count(BODY_SENTINEL) == nl_html.count(BODY_SENTINEL) == 1

    def test_rendering_twice_in_two_languages_does_not_leak(self, shell, msgid):
        """The compiled shell is cached (one ``PageTemplateFile`` per path). A
        language cached into the compiled program would ship Dutch to French
        communes, and the shell is the *shared* template -- every migrated
        notification in the site goes through this one file."""
        first, _ = shell(subject=msgid, language="fr")
        _dutch, _ = shell(subject=msgid, language="nl")
        again, _ = shell(subject=msgid, language="fr")

        assert first == again

    def test_omitting_the_language_uses_the_negotiated_one(self, shell, integration):
        """§6.1, applied to the sibling: "the negotiated language when omitted".

        Compared against the request's own ``LANGUAGE`` rather than a hardcoded
        code, so the test states the *rule* and not this layer's happenstance.
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
    """§6.1's purity, which the golden files and ``@@emailkit-preview`` both rely
    on. ``render_shell`` shares ``render()``'s code path, so this is a regression
    test for that sharing rather than a second implementation of it."""

    def test_render_shell_is_repeatable(self, shell):
        assert shell() == shell()

    def test_two_bodies_do_not_bleed_into_each_other(self, shell):
        """The shell is one cached compiled template shared by every caller. A
        body retained between renders would mean one commune's notification
        appearing in another's mail -- the worst failure this function could
        have."""
        first, _ = shell(body=f"<p>{BODY_SENTINEL}</p>")
        second, _ = shell(body="<p>autre corps</p>")

        assert BODY_SENTINEL in first
        assert BODY_SENTINEL not in second
        assert "autre corps" in second
        assert "autre corps" not in first
