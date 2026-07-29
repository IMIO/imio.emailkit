"""Installing ``imio.emailkit:default`` registers what SPEC §8 says it does."""

import support


support.require_runtime()

PACKAGE_NAME = support.PACKAGE_NAME


class TestSetupInstall:
    def test_addon_installed(self, installer):
        assert installer.is_product_installed(PACKAGE_NAME) is True

    def test_browserlayer(self, browser_layers):
        """§8.1: the jbot directory is registered on a dedicated browser layer,
        and that layer is installed by the ``:default`` profile."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer in browser_layers

    def test_latest_version(self, profile_last_version):
        assert profile_last_version(f"{PACKAGE_NAME}:default") == "1000"

    def test_default_profile_extends_base(self, profile_last_version):
        """§8.2: "``:default`` extends ``:base``".

        Applying ``:default`` alone must therefore leave ``:base`` recorded as
        applied. If this fails, the two profiles are siblings and a site that
        installed ``:default`` never got the runtime records -- while every test
        that only ever looks at ``:default`` stays green.
        """
        assert profile_last_version(f"{PACKAGE_NAME}:base") == "1000"
