"""Uninstalling must leave nothing behind that a later request can trip over."""

import pytest
import support


support.require_runtime()

PACKAGE_NAME = support.PACKAGE_NAME


class TestSetupUninstall:
    @pytest.fixture(autouse=True)
    def uninstalled(self, installer):
        installer.uninstall_product(PACKAGE_NAME)

    def test_addon_uninstalled(self, installer):
        assert installer.is_product_installed(PACKAGE_NAME) is False

    def test_browserlayer_not_registered(self, browser_layers):
        """A leftover ``IEmailkitLayer`` would keep jbot swapping the stock mail
        templates for files whose add-on is gone."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer not in browser_layers

    def test_theme_records_removed(self, portal):
        """The three theme tokens must go with the add-on.

        A record whose defining interface is no longer importable makes the
        registry control panel raise. Requires a ``profiles/uninstall`` shipping
        ``registry.xml`` with ``remove="true"`` -- the Phase 1 plan lists the two
        install profiles only, so a failure here is a genuine gap, not a
        mis-specified test.
        """
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        leftovers = [
            record
            for record in support.THEME_RECORDS.values()
            if record in registry.records
        ]

        assert leftovers == []
