"""A site package's jbot directory beats ours.

A site package can restyle a template by registering a jbot directory on a
more specific browser layer; z3c.jbot's precedence rule picks that one. The
test double must extend ``IEmailkitLayer``, not sit beside it as a sibling:
sibling precedence follows arbitrary registration order and would prove
nothing. Only ``mail_password_template`` is covered, since the mechanism
works per layer, not per template.
"""

import support


support.require_runtime()

SITE_MARKER = "data-sitelayer-override=mail_password_template"
TEMPLATE = support.MAIL_PASSWORD


class TestTheSiteLayerExtendsOurs:
    def test_it_really_is_a_subclass(self):
        """A sibling layer would make the win below a coin flip."""
        from imio.emailkit.interfaces import IEmailkitLayer
        from sitelayer.interfaces import ISiteLayer

        assert ISiteLayer.extends(IEmailkitLayer)

    def test_both_layers_are_available(self, site_portal, layers_of):
        """A site layer beating a missing override is not precedence."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer in layers_of(site_portal)


def _site_layer():
    from sitelayer.interfaces import ISiteLayer

    return ISiteLayer


class TestTheSiteLayerWins:
    def _view(self, portal, request):
        support.mark_request(request, _site_layer())
        return support.stock_mail_view(portal, request, TEMPLATE)

    def test_the_site_file_wins_at_lookup(self, site_portal, site_request):
        """The filename alone does not prove the override took effect;
        see the render assertions below."""
        from imio.emailkit.render import _page_template
        from imio.emailkit.discovery import get_template

        support.mark_request(site_request, _site_layer())
        template = get_template(support.qualified(TEMPLATE))
        resolved = _page_template(template.html_path)
        path = resolved.filename.replace("\\", "/")

        assert "/sitelayer/overrides/" in path, (
            f"the site package's override did not win: {resolved.filename!r}"
        )

    def test_the_site_markup_renders(self, site_portal, site_request, make_member):
        """The assertion that actually matters."""
        member = make_member(site_portal)
        view = self._view(site_portal, site_request)
        reset = site_portal.portal_password_reset.requestReset(member.getId())

        rendered = view(
            member=member,
            reset=reset,
            password=member.getPassword(),
            charset="utf-8",
        )

        assert SITE_MARKER in rendered
        # The site template reads `site_name` from render()'s context, so this
        # proves the template executed rather than just resolved.
        assert "Site name :" in rendered

    def test_our_markup_does_not_render(self, site_portal, site_request, make_member):
        """The negative half: our markup lost, not just got concatenated."""
        member = make_member(site_portal)
        view = self._view(site_portal, site_request)
        reset = site_portal.portal_password_reset.requestReset(member.getId())

        rendered = view(
            member=member,
            reset=reset,
            password=member.getPassword(),
            charset="utf-8",
        )

        assert support.A11Y_TABLE_MARKER not in rendered, (
            "kit markup is in the output: the emailkit override rendered too"
        )
        assert support.count_inline_styles(rendered) == 0

    def test_the_stock_template_did_not_win_either(
        self, site_portal, site_request, make_member
    ):
        member = make_member(site_portal)
        view = self._view(site_portal, site_request)
        reset = site_portal.portal_password_reset.requestReset(member.getId())

        rendered = view(
            member=member,
            reset=reset,
            password=member.getPassword(),
            charset="utf-8",
        )

        assert support.STOCK_BODY_MARKERS[TEMPLATE] not in rendered
