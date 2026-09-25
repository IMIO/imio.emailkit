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
        """A leftover layer would keep jbot swapping in a gone add-on's templates."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer not in browser_layers

    def test_theme_records_removed(self, portal):
        """The three theme tokens must go with the add-on, or the registry
        control panel raises on the now-unimportable interface."""
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility

        registry = getUtility(IRegistry)
        leftovers = [
            record
            for record in support.THEME_RECORDS.values()
            if record in registry.records
        ]

        assert leftovers == []
