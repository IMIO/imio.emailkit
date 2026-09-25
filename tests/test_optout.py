"""Opting out entirely with the ``:base`` profile.

``:base`` installs the runtime (API, discovery, kit) but not the
Plone-default overrides. Stock Plone mails stay untouched.

The ``browser:jbot`` directive always loads from ZCML. ``:base`` opts out
by not installing the browser layer, so the overrides never apply. This
suite checks both halves: the layer is absent, and the stock mails render.
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
    """Not marked with ``IEmailkitLayer``.

    On a ``:base`` site the profile never registers the layer, so
    ``plone.browserlayer`` never applies it to a request.
    """
    from imio.emailkit.interfaces import IEmailkitLayer

    assert not IEmailkitLayer.providedBy(base_request), (
        "the request leaked IEmailkitLayer from another test -- this suite's "
        "negative assertions would be meaningless"
    )
    return base_request


class TestBaseProfileDoesNotInstallTheLayer:
    def test_the_base_profile_was_really_applied(self, base_portal):
        """Checks the install through ``portal_setup``, not the quickinstaller.

        ``is_product_installed()`` checks for the ``default`` profile, so it
        returns ``False`` here even though the add-on works.
        """
        setup_tool = base_portal.portal_setup
        version = setup_tool.getLastVersionForProfile(f"{support.PACKAGE_NAME}:base")

        assert version and version != "unknown", (
            f"{support.PACKAGE_NAME}:base was not applied: {version!r}"
        )

    def test_the_default_profile_was_not_applied(self, base_portal):
        """The ``:default`` profile must not have run.

        Otherwise the overrides would be back.
        """
        setup_tool = base_portal.portal_setup
        version = setup_tool.getLastVersionForProfile(f"{support.PACKAGE_NAME}:default")

        assert not version or version == "unknown", (
            f"{support.PACKAGE_NAME}:default leaked into a :base site: {version!r}"
        )

    def test_the_browser_layer_is_absent(self, base_portal, layers_of):
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer not in layers_of(base_portal)

    def test_the_runtime_is_still_there(self, base_portal):
        """Opting out of the restyled defaults must not disable the runtime."""
        from imio.emailkit import render

        html, text = render(
            support.qualified(support.NOTIFICATION),
            context=support.load_fixture(support.NOTIFICATION),
            language="fr",
        )

        assert html
        assert text is not None

    def test_the_theme_records_are_still_there(self, base_portal):
        """The three tokens control branding only. They stay on ``:base`` too."""
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
        """Checks that Plone's own mail body renders, not just that ours is
        absent."""
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
