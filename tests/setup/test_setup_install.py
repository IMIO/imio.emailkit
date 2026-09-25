"""Installing ``imio.emailkit:default`` registers what the ``:default`` profile promises."""

import support


support.require_runtime()

PACKAGE_NAME = support.PACKAGE_NAME


class TestSetupInstall:
    def test_addon_installed(self, installer):
        assert installer.is_product_installed(PACKAGE_NAME) is True

    def test_browserlayer(self, browser_layers):
        """``:default`` installs the browser layer the jbot directory needs."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer in browser_layers

    def test_latest_version(self, profile_last_version):
        assert profile_last_version(f"{PACKAGE_NAME}:default") == "1000"

    def test_default_profile_extends_base(self, profile_last_version):
        """``:default`` extends ``:base``, so it also records ``:base`` applied."""
        assert profile_last_version(f"{PACKAGE_NAME}:base") == "1000"
