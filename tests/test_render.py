"""``render()``.

Every assertion here checks a substituted value, never a marker string.
Without the ``IPageTemplateEngine`` utility, ``zope.pagetemplate`` falls
back to ``zope.tal``, where ``${...}`` passes through unrendered and
raises nothing. ``assert_render_is_clean`` catches any such leftover.
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
        """Every fixture string value must reach the html, not a chosen few."""
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
        """The plaintext part must carry fixture data too, not just the html."""
        _html, text = rendered

        strings = [v for v in fixture_data.values() if isinstance(v, str)]
        longest = max(strings, key=len)

        assert longest in text, (
            f"the text part carries none of the fixture: {longest[:40]!r} absent"
        )

    def test_a_url_survived_into_an_attribute(self, rendered, fixture_data):
        """A URL in a non-``class``/``style`` attribute must render as a real
        value, not literal ``${cta_url}``."""
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
        """The render language must appear as ``lang`` on ``<html>``, for
        screen-reader pronunciation."""
        html, _text = render(
            support.qualified(template),
            context=support.load_fixture(template),
            language="fr",
        )

        match = support.LANG_ATTRIBUTE.search(html)

        assert match, "no lang attribute on <html> (kit accessibility default)"
        assert match.group(1).lower().startswith("fr")

    def test_the_language_argument_is_honoured(self, integration, template):
        """The ``lang`` attribute must match the requested language, not just
        be present."""
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
        """Templates are cached. A cached language must not leak into a later
        render done in another language."""
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
        """``render()`` is pure: same inputs, same output.

        Previews and golden files depend on this. A timestamp or random id
        in the output would make every golden file fail on the second run.
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
        """Injecting ``theme``, ``lang``, and helpers must not write into the
        caller's context dict."""
        given = dict(fixture_data)
        before = dict(given)

        render(support.qualified(template), context=given, language="fr")

        assert given == before


class TestKitDefaults:
    """What the kit does so that no author has to remember it."""

    def test_layout_tables_are_marked_presentational(self, rendered):
        """RGAA requires this. Without it, screen readers read a layout table
        cell by cell."""
        html, _text = rendered

        assert support.A11Y_TABLE_MARKER in html

    def test_css_was_inlined(self, rendered):
        """CSS must be inlined by the build.

        A Chameleon placeholder in a literal ``style`` attribute stops Juice
        inlining for the whole document, while the build still reports
        success.
        """
        html, _text = rendered

        count = support.count_inline_styles(html)

        assert count >= support.MIN_INLINE_STYLES, (
            f"only {count} inline style attributes: CSS inlining is probably "
            "dead (a ${...} in a literal style attribute stops it)"
        )
