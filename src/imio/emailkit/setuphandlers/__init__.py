from plone.base.interfaces.installable import INonInstallable
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles:
    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller.

        ``imio.emailkit:base`` stays visible: installing it instead of
        ``:default`` is how a site opts out.
        """
        return [
            "imio.emailkit:uninstall",
        ]

    def getNonInstallableProducts(self):
        """Hide the upgrades package from site-creation and quickinstaller."""
        return [
            "imio.emailkit.upgrades",
        ]
