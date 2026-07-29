"""SPEC §8.2 level 1 -- a site package's jbot directory beats ours.

> Replace the template markup per site/client: register a jbot directory on a
> *more specific* browser layer (the site package's own layer). z3c.jbot layer
> precedence applies -- the most specific layer wins.

**Why the test double extends ``IEmailkitLayer`` and could not do otherwise.**
Phase 0 measured this against the request's ``__sro__`` and found §8.2 as written
is only true for a layer that *subclasses* ``IEmailkitLayer``. For a **sibling**
layer, precedence follows ``getAllUtilitiesRegisteredFor(ILocalBrowserLayerType)``
registration order, which is effectively arbitrary -- so a sibling-layer test
would pass or fail depending on ZCML load order and prove nothing either way.
``docs/DECISIONS.md`` (2026-07-29, "§8.2 override story requires extending
``IEmailkitLayer``") turns that into the documented rule, and this module is the
executable form of it: ``tests/sitelayer/interfaces.py`` extends our layer, and
the docs must keep saying so.

Only ``mail_password_template`` is covered. The mechanism is per-layer, not
per-template -- a second identical case would cost a fixture and buy nothing.
"""

import support


support.require_runtime()

SITE_MARKER = "data-sitelayer-override=mail_password_template"
SITE_SUBJECT = "SITE LAYER WINS"
TEMPLATE = support.MAIL_PASSWORD


class TestTheSiteLayerExtendsOurs:
    def test_it_really_is_a_subclass(self):
        """Guard the premise. If someone "simplifies" the test double into a
        sibling layer, the win below becomes a coin flip that happens to land
        right on the machine it was written on."""
        from imio.emailkit.interfaces import IEmailkitLayer
        from sitelayer.interfaces import ISiteLayer

        assert ISiteLayer.extends(IEmailkitLayer)

    def test_both_layers_are_available(self, site_portal, layers_of):
        """Ours must be installed for the contest to mean anything: a site layer
        beating a *missing* override is not precedence, it is the only candidate.
        """
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer in layers_of(site_portal)


class TestTheSiteLayerWins:
    def _view(self, portal, request):
        from sitelayer.interfaces import ISiteLayer

        support.mark_request(request, ISiteLayer)
        return support.stock_mail_view(portal, request, TEMPLATE)

    def test_the_site_file_wins_at_lookup(self, site_portal, site_request):
        view = self._view(site_portal, site_request)
        resolved = support.resolved_template(view)
        path = resolved.filename.replace("\\", "/")

        assert "/sitelayer/overrides/" in path, (
            f"the site package's override did not win: {resolved.filename!r}"
        )

    def test_the_site_markup_renders(self, site_portal, site_request, make_member):
        """The assertion that actually matters -- see ``test_jbot_wiring.py`` for
        why a filename on its own proves nothing."""
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
        assert SITE_SUBJECT in rendered
        # The site template reads the member through the hosting view's dialect,
        # so this also proves it was really executed rather than resolved.
        assert member.getProperty("email") in rendered

    def test_our_markup_does_not_render(self, site_portal, site_request, make_member):
        """The negative half: ours lost, rather than both being concatenated or
        ours winning while the site file merely appeared in a lookup table."""
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
