"""``@@emailkit_theme`` -- the theme tokens for templates we do not render.

SPEC §8.2 level 2 promises that a site can restyle its mails through the three
``imio.emailkit.theme.*`` registry records alone. ``render()`` delivers them as
the ``theme`` name in its namespace, but the two Plone default mails (§8) are
rendered by a *stock CMFPlone view*, which knows nothing about us: neither
``theme`` nor ``options/theme`` exists there. The kit layout's last fallback is
this view, and without it those two mails silently fall back to the hard-coded
kit colour and ignore the registry entirely -- the promise would hold for every
template except the two the package ships.

Returns a plain mapping on purpose. A view *instance* would need AccessControl
declarations before ``theme/primary_color`` could traverse it from a template;
a dict needs nothing and cannot grow behaviour.
"""

from imio.emailkit.render import get_theme
from Products.Five.browser import BrowserView


class EmailkitThemeView(BrowserView):
    """Return SPEC §3's theme tokens as a mapping."""

    def __call__(self):
        return get_theme()
