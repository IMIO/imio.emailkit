from AccessControl.SecurityManagement import newSecurityManager
from imio.emailkit.interfaces import IEmailkitLayer
from Products.CMFPlone.factory import _DEFAULT_PROFILE
from Products.CMFPlone.factory import addPloneSite
from Products.GenericSetup.tool import SetupTool
from Testing.makerequest import makerequest
from zope.interface import directlyProvidedBy
from zope.interface import directlyProvides

import os
import transaction


truthy = frozenset(("t", "true", "y", "yes", "on", "1"))


def asbool(s):
    """Return ``True`` if the lower-cased string ``s`` is a truthy string."""
    if s is None:
        return False
    if isinstance(s, bool):
        return s
    s = str(s).strip()
    return s.lower() in truthy


DELETE_EXISTING = asbool(os.getenv("DELETE_EXISTING"))

# ``:base`` installs the runtime without the Plone default mail overrides.
PROFILE = os.getenv("PROFILE", "default")

app = makerequest(globals()["app"])

request = app.REQUEST

ifaces = [IEmailkitLayer]
for iface in directlyProvidedBy(request):
    ifaces.append(iface)

directlyProvides(request, *ifaces)

admin = app.acl_users.getUserById("admin")
admin = admin.__of__(app.acl_users)
newSecurityManager(None, admin)

site_id = "Plone"
payload = {
    "title": "Emailkit",
    "profile_id": _DEFAULT_PROFILE,
    "distribution_name": "classic",
    "setup_content": False,
    # French: the language iMio's clients receive.
    "default_language": "fr",
    "portal_timezone": "Europe/Brussels",
}

if site_id in app.objectIds() and DELETE_EXISTING:
    app.manage_delObjects([site_id])
    transaction.commit()
    app._p_jar.sync()

if site_id not in app.objectIds():
    site = addPloneSite(app, site_id, **payload)
    transaction.commit()

    portal_setup: SetupTool = site.portal_setup
    portal_setup.runAllImportStepsFromProfile(f"profile-imio.emailkit:{PROFILE}")
    transaction.commit()
