"""Theme tokens are the *only* runtime-variable branding.

These three registry records are the answer to "the majority of
per-commune needs without touching markup". So the one thing that must be true is
that changing a record changes the rendered mail. If it does not, every commune
gets iMio blue and the documented override story quietly has two levels, not
three.

Phase 0's caveat A1 is the reason this is not obvious: the original form,
``style="background-color: ${theme/primary_color}"``, produced a *broken literal*
(``${theme/primary_color`` -- closing brace eaten by Juice) **and** killed CSS
inlining document-wide, with the build reporting success. The token therefore has
to arrive via ``tal:attributes``, and the only way to know it did is to read the
rendered output.
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
        """Verbatim: the record names are part of the public API --
        a site's ``registry.xml`` refers to them by string."""
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)

        assert support.THEME_RECORDS[token] in registry.records


class TestPrimaryColor:
    def test_changing_the_record_changes_the_output(
        self, integration, set_record, template
    ):
        """Phase 1 test-plan gate 9."""
        set_record("primary_color", PROBE_COLOR)
        first = _render(template)

        set_record("primary_color", OTHER_COLOR)
        second = _render(template)

        assert PROBE_COLOR in first, (
            f"{PROBE_COLOR} never reached the output: the theme token is not "
            "rendered (Phase 0 caveat A1 -- it must arrive via tal:attributes, "
            "not a literal style attribute)"
        )
        assert OTHER_COLOR in second
        assert PROBE_COLOR not in second, "the render cached the old token value"
        assert first != second

    def test_the_token_lands_in_a_well_formed_attribute(
        self, integration, set_record, template
    ):
        """Not merely present somewhere in the document.

        Caveat A1's broken form put the token in the output too, as
        ``style="background-color:${theme/primary_color"`` -- present, and useless.
        So what is checked is that the value sits inside a *closed, quoted*
        attribute, plus (below) that no ``${`` survived anywhere.

        Deliberately not restricted to ``style``: ``bgcolor`` is the Outlook
        fallback for a background and is exactly where a kit is right to put a
        colour. Which attribute the kit chooses is its business; that the value
        arrives intact is not.
        """
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
        """Caveat A1's *other* half: the bad form did not only break the token,
        it stopped Juice inlining for the whole document -- 31 inline styles down
        to 6, build green."""
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
        """The logo/``Img`` component: "enforced ``alt``".

        An image-only header with no ``alt`` is a mail that says nothing at all
        to a screen reader or to a client that blocks remote images -- which
        is most corporate clients by default.
        """
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
        """The rule: "``structure`` is reserved for the shell's ``body_html``
        slot and ``footer_html``, nothing else".

        Escaped markup in the footer is the visible symptom of the wrong idiom,
        and it reaches every mail the site sends.
        """
        set_record("footer_html", PROBE_FOOTER)

        html = _render(template)

        assert "probe-footer-marker" in html
        assert "&lt;span&gt;" not in html, (
            "footer_html was HTML-escaped: it must be rendered with `structure`"
        )
