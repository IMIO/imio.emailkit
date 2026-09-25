"""Theme tokens are the only runtime-variable branding.

Each of these three registry records must change the rendered mail when
changed, or a commune cannot brand its mails without touching markup.

The token must arrive via ``tal:attributes``, not a literal style
attribute: a literal ``${...}`` there can produce a broken attribute and
stop CSS inlining for the whole document while the build still succeeds.
"""

import pytest
import support


support.require_runtime()

from imio.emailkit import render  # noqa: E402


#: Nothing in the kit, in Tailwind's palette or in Plone's chrome uses these, so
#: finding one in the output can only mean the record was read.
PROBE_COLOR = "#7f00ff"
OTHER_COLOR = "#00ff7f"
PROBE_LOGO = "https://probe.example.be/logo-probe.png"
PROBE_FOOTER = "<span>Pied de page sonde &mdash; probe-footer-marker</span>"


@pytest.fixture
def set_record():
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


@pytest.fixture(params=support.RENDERABLE_TEMPLATES, ids=support.RENDERABLE_TEMPLATES)
def template(request):
    return request.param


def _render(template):
    return render(
        support.qualified(template),
        context=support.load_fixture(template),
        language="fr",
    )[0]


class TestRecordsExist:
    @pytest.mark.parametrize("token", sorted(support.THEME_RECORDS))
    def test_record_is_installed(self, integration, token):
        """The record names are public API: a site's ``registry.xml`` refers
        to them by string."""
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)

        assert support.THEME_RECORDS[token] in registry.records


class TestPrimaryColor:
    def test_changing_the_record_changes_the_output(
        self, integration, set_record, template
    ):
        set_record("primary_color", PROBE_COLOR)
        first = _render(template)

        set_record("primary_color", OTHER_COLOR)
        second = _render(template)

        assert PROBE_COLOR in first, (
            f"{PROBE_COLOR} never reached the output: the theme token is not rendered"
            " (pass it through tal:attributes, not a literal style attribute)"
        )
        assert OTHER_COLOR in second
        assert PROBE_COLOR not in second, "the render cached the old token value"
        assert first != second

    def test_the_token_lands_in_a_well_formed_attribute(
        self, integration, set_record, template
    ):
        """The token must sit inside a closed, quoted attribute, not just
        appear somewhere in the document. Not restricted to ``style``:
        ``bgcolor`` is a valid Outlook fallback for a colour."""
        import re

        set_record("primary_color", PROBE_COLOR)

        html = _render(template)
        attribute = re.compile(
            r'[a-zA-Z-]+="[^"]*' + re.escape(PROBE_COLOR) + r'[^"]*"'
        )
        found = attribute.findall(html)

        assert found, (
            f"{PROBE_COLOR} is in the output but not inside a closed attribute: "
            f"{[m for m in html.split() if PROBE_COLOR in m][:3]}"
        )
        support.assert_render_is_clean(html, "the themed render")

    def test_inlining_still_works_with_a_token_present(
        self, integration, set_record, template
    ):
        """A broken token form can also stop CSS inlining for the whole
        document while the build still succeeds."""
        set_record("primary_color", PROBE_COLOR)

        html = _render(template)

        assert support.count_inline_styles(html) >= support.MIN_INLINE_STYLES


class TestLogoUrl:
    def test_changing_the_record_changes_the_output(
        self, integration, set_record, template
    ):
        set_record("logo_url", PROBE_LOGO)

        html = _render(template)

        assert PROBE_LOGO in html

    def test_the_logo_has_an_alt_attribute(self, integration, set_record, template):
        """The logo image must carry an ``alt`` attribute, for screen
        readers and clients that block remote images."""
        set_record("logo_url", PROBE_LOGO)

        html = _render(template)

        index = html.find(PROBE_LOGO)
        assert index != -1
        # The enclosing tag: back to the previous '<', forward to the next '>'.
        start = html.rfind("<", 0, index)
        end = html.find(">", index)
        tag = html[start : end + 1]

        assert "alt=" in tag, f"logo <img> has no alt attribute: {tag}"


class TestFooterHtml:
    def test_the_footer_is_injected_as_structure(
        self, integration, set_record, template
    ):
        """``footer_html`` uses ``structure``, so it must not be escaped."""
        set_record("footer_html", PROBE_FOOTER)

        html = _render(template)

        assert "probe-footer-marker" in html
        assert "&lt;span&gt;" not in html, (
            "footer_html was HTML-escaped: it must be rendered with `structure`"
        )
