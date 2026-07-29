"""SPEC §8.2 level 3 -- opting out entirely with the ``:base`` profile.

"``:base`` provides the runtime (API, discovery, kit) without the Plone-default
overrides; stock Plone mails remain untouched."

This module is entirely negative assertions, which is why it exists as its own
file rather than as two extra cases elsewhere. An opt-out is the one feature
nobody exercises by accident: everyone installs ``:default``, the escape hatch is
used by one client six months from now, and if it never worked the failure lands
on a production site with no warning. The gate is cheap; the discovery is not.

Note what makes the opt-out work: the ``browser:jbot`` directive is in ZCML and
therefore *always* loaded -- ``:base`` opts out by **not installing the browser
layer**, which is what leaves the overrides inert. So the test asserts on both
halves: the layer is absent, and the stock mails really do render.
"""

import pytest
import support


support.require_runtime()


@pytest.fixture(
    params=support.DEFAULT_MAIL_TEMPLATES, ids=support.DEFAULT_MAIL_TEMPLATES
)
def template(request):
    return request.param


@pytest.fixture
def member(base_portal, make_member):
    return make_member(base_portal)


@pytest.fixture
def unmarked_request(base_request):
    """Deliberately **not** marked with ``IEmailkitLayer``.

    That is the real condition on a ``:base`` site: the profile never registered
    the layer, so ``plone.browserlayer`` never applies it to a request.
    """
    from imio.emailkit.interfaces import IEmailkitLayer

    assert not IEmailkitLayer.providedBy(base_request), (
        "the request leaked IEmailkitLayer from another test -- this suite's "
        "negative assertions would be meaningless"
    )
    return base_request


class TestBaseProfileDoesNotInstallTheLayer:
    def test_the_base_profile_was_really_applied(self, base_portal):
        """``:base`` is a real install, not "nothing happened".

        Checked through ``portal_setup`` rather than through the quickinstaller,
        because ``get_installer(portal).is_product_installed(...)`` answers
        "*has the ``default`` profile been applied?*" -- so on a ``:base`` site it
        returns ``False`` even though the add-on is installed and working. That is
        a Plone quirk worth knowing about (Site Setup will list the add-on as
        available, not installed), not a bug in the opt-out; it belongs in the
        README, and asserting on the quickinstaller here would have encoded the
        wrong expectation.
        """
        setup_tool = base_portal.portal_setup
        version = setup_tool.getLastVersionForProfile(f"{support.PACKAGE_NAME}:base")

        assert version and version != "unknown", (
            f"{support.PACKAGE_NAME}:base was not applied: {version!r}"
        )

    def test_the_default_profile_was_not_applied(self, base_portal):
        """The opt-out has to be a real opt-out: if ``:default`` were pulled in
        by a dependency somewhere, the overrides would be back and every
        assertion below would be testing the wrong site."""
        setup_tool = base_portal.portal_setup
        version = setup_tool.getLastVersionForProfile(f"{support.PACKAGE_NAME}:default")

        assert not version or version == "unknown", (
            f"{support.PACKAGE_NAME}:default leaked into a :base site: {version!r}"
        )

    def test_the_browser_layer_is_absent(self, base_portal, layers_of):
        """§8.2: the whole opt-out hinges on this one line."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer not in layers_of(base_portal)

    def test_the_runtime_is_still_there(self, base_portal):
        """ "``:base`` provides the runtime (API, discovery, kit)". Opting out of
        the restyled defaults must not opt out of the package."""
        from imio.emailkit import render

        html, text = render(
            support.qualified(support.NOTIFICATION),
            context=support.load_fixture(support.NOTIFICATION),
            language="fr",
        )

        assert html
        assert text is not None

    def test_the_theme_records_are_still_there(self, base_portal):
        """The three tokens are §8.2 *level 2* -- branding without markup
        changes. A site on ``:base`` still wants them."""
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)

        for record in support.THEME_RECORDS.values():
            assert record in registry.records


class TestStockMailsAreUntouched:
    def test_the_stock_template_file_wins(
        self, base_portal, unmarked_request, template
    ):
        view = support.stock_mail_view(base_portal, unmarked_request, template)
        resolved = support.resolved_template(view)

        assert resolved.filename.endswith(support.STOCK_TEMPLATE_TAILS[template]), (
            f"jbot swapped a template on a :base site: {resolved.filename!r}"
        )

    def test_the_stock_body_renders(
        self, base_portal, unmarked_request, template, member
    ):
        """The positive half of the negative test: not merely "our markup is
        absent" (which an exception would also satisfy) but "Plone's own mail
        came out, intact"."""
        rendered = support.call_stock_mail(
            base_portal, unmarked_request, template, member
        )

        assert support.STOCK_BODY_MARKERS[template] in rendered

    def test_our_markup_is_absent(
        self, base_portal, unmarked_request, template, member
    ):
        rendered = support.call_stock_mail(
            base_portal, unmarked_request, template, member
        )

        assert support.A11Y_TABLE_MARKER not in rendered
        assert support.count_inline_styles(rendered) == 0, (
            "the stock plaintext mail came out with inlined CSS -- a kit template "
            "rendered"
        )
