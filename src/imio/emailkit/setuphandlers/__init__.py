from plone.base.interfaces.installable import INonInstallable
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles:
    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller.

        ``imio.emailkit:base`` is deliberately NOT hidden: installing it
        instead of ``:default`` is the documented opt-out, so it has
        to be offered.
        """
        return [
            "imio.emailkit:uninstall",
        ]

    def getNonInstallableProducts(self):
        """Hide the upgrades package from site-creation and quickinstaller."""
        return [
            "imio.emailkit.upgrades",
        ]
