"""``render()``.

**The rule this module exists to enforce:** assert on *substituted values*, never
on marker strings. Phase 0 measured that without the ``IPageTemplateEngine``
utility, ``zope.pagetemplate`` falls back to ``zope.tal``, where ``${...}``
passes through **verbatim and raises nothing** while ``tal:repeat`` keeps
working. A test that only checks "our marker is in the output" therefore passes
while raw ``${member/fullname}`` ships to a citizen's inbox.

So: every assertion here names a value that only appears *because* an expression
was evaluated, and ``assert_render_is_clean`` closes the door on the rest.
"""

import pytest
import support


support.require_runtime()

from imio.emailkit import render  # noqa: E402


TEMPLATES = support.RENDERABLE_TEMPLATES


@pytest.fixture(params=TEMPLATES, ids=TEMPLATES)
def template(request):
    return request.param


@pytest.fixture
def fixture_data(template):
    return support.load_fixture(template)


@pytest.fixture
def rendered(integration, template, fixture_data):
    return render(
        support.qualified(template), context=dict(fixture_data), language="fr"
    )


class TestReturnValue:
    def test_returns_html_and_text(self, rendered):
        """Returns ``html, text = render(...)``."""
        assert isinstance(rendered, tuple)
        assert len(rendered) == 2

        html, text = rendered

        assert isinstance(html, str)
        assert isinstance(text, str)
        assert html.strip()
        assert text.strip()

    def test_html_is_html_and_text_is_not(self, rendered):
        html, text = rendered

        assert "<html" in html.lower()
        assert "<html" not in text.lower()


class TestPlaceholdersAreSubstituted:
    def test_no_unresolved_placeholder_in_html(self, rendered):
        html, _text = rendered

        support.assert_render_is_clean(html, "html")

    def test_no_unresolved_placeholder_in_text(self, rendered):
        _html, text = rendered

        support.assert_render_is_clean(text, "text")

    def test_every_fixture_value_reached_the_html(self, rendered, fixture_data):
        """The positive half: values that exist only in the fixture.

        *Every* string value, not a chosen few. One fixture is paired with one
        template, so a key nothing renders is either dead data or -- far more
        likely -- a placeholder that stopped resolving. Enumerating the whole
        fixture means adding a placeholder without adding its data, or removing a
        placeholder and leaving its data, both fail here rather than in six months
        in an inbox.
        """
        html, _text = rendered

        missing = [
            key
            for key, value in fixture_data.items()
            if isinstance(value, str) and value not in html
        ]

        assert missing == [], (
            f"fixture keys whose value never reached the html: {missing}"
        )

    def test_fixture_values_reached_the_plaintext_part(self, rendered, fixture_data):
        """A text part whose placeholders quietly stopped resolving is exactly as
        broken as an HTML one, and far less likely to be noticed by eye -- nobody
        reads the ``text/plain`` alternative until a client renders only that.

        Only the longest string value is required here: what a plaintext body
        repeats is the author's call (and with no ``.txt.pt`` twin it is a naive
        extraction), but a text part carrying *none* of the context means it was
        never bound at all.
        """
        _html, text = rendered

        strings = [v for v in fixture_data.values() if isinstance(v, str)]
        longest = max(strings, key=len)

        assert longest in text, (
            f"the text part carries none of the fixture: {longest[:40]!r} absent"
        )

    def test_a_url_survived_into_an_attribute(self, rendered, fixture_data):
        """``${...}`` inside a non-``class``/``style`` attribute -- the case
        Phase 0 confirmed survives the build. A link that renders as literal
        ``${cta_url}`` makes the mail useless while everything else looks
        fine."""
        html, _text = rendered

        urls = [
            value
            for value in fixture_data.values()
            if isinstance(value, str) and value.startswith("http")
        ]
        assert urls, "the fixture has no URL, so this template cannot be checked"

        for url in urls:
            assert f'"{url}"' in html, f"{url} is not in an attribute"


class TestRenderLanguage:
    def test_lang_is_exposed_and_emitted_on_html(self, integration, template):
        """The render language is also exposed as ``lang``, which the
        layout emits on ``<html>``. Screen-reader pronunciation depends on it."""
        html, _text = render(
            support.qualified(template),
            context=support.load_fixture(template),
            language="fr",
        )

        match = support.LANG_ATTRIBUTE.search(html)

        assert match, "no lang attribute on <html> (kit accessibility default)"
        assert match.group(1).lower().startswith("fr")

    def test_the_language_argument_is_honoured(self, integration, template):
        """Not merely "a lang attribute exists" -- it has to be *the* language
        asked for, or ``language=`` is decoration."""
        html_nl, _ = render(
            support.qualified(template),
            context=support.load_fixture(template),
            language="nl",
        )

        match = support.LANG_ATTRIBUTE.search(html_nl)

        assert match
        assert match.group(1).lower().startswith("nl")

    def test_rendering_twice_in_two_languages_does_not_leak(
        self, integration, template
    ):
        """Templates are cached; a language cached into the compiled program
        would silently ship Dutch to French communes."""
        html_fr, _ = render(
            support.qualified(template),
            context=support.load_fixture(template),
            language="fr",
        )
        html_nl, _ = render(
            support.qualified(template),
            context=support.load_fixture(template),
            language="nl",
        )
        html_fr_again, _ = render(
            support.qualified(template),
            context=support.load_fixture(template),
            language="fr",
        )

        assert html_fr == html_fr_again
        assert html_fr != html_nl


class TestPureFunction:
    def test_render_is_repeatable(self, integration, template, fixture_data):
        """A pure function of (template, context, registry state).

        Previews and golden files both depend on this; a timestamp or a random
        id in the output would make every golden file fail on the second run.
        """
        first = render(
            support.qualified(template), context=dict(fixture_data), language="fr"
        )
        second = render(
            support.qualified(template), context=dict(fixture_data), language="fr"
        )

        assert first == second

    def test_render_does_not_mutate_the_context(
        self, integration, template, fixture_data
    ):
        """Injecting ``theme``/``lang``/helpers must not write into the caller's
        dict -- the preview view and the golden harness both reuse one fixture
        across languages."""
        given = dict(fixture_data)
        before = dict(given)

        render(support.qualified(template), context=given, language="fr")

        assert given == before


class TestKitDefaults:
    """What the kit does so that no author has to remember it."""

    def test_layout_tables_are_marked_presentational(self, rendered):
        """Accessibility defaults. RGAA applies to iMio's clients, and a
        layout table without ``role="presentation"`` is read out cell by cell."""
        html, _text = rendered

        assert support.A11Y_TABLE_MARKER in html

    def test_css_was_inlined(self, rendered):
        """Phase 1's exit criterion, and Phase 0's caveat A1.

        A single Chameleon placeholder in a literal ``style`` attribute stops
        Juice inlining **document-wide** while the build still reports success.
        Phase 0 measured 31 inline styles healthy vs 6 with inlining dead on a
        comparable template, which is where the threshold comes from.
        """
        html, _text = rendered

        count = support.count_inline_styles(html)

        assert count >= support.MIN_INLINE_STYLES, (
            f"only {count} inline style attributes: CSS inlining is probably "
            "dead (Phase 0 caveat A1 -- a ${...} in a literal style attribute)"
        )
