"""``@@emailkit_theme`` -- the theme tokens for templates rendered by a stock view.

A stock CMFPlone view knows nothing about the ``imio.emailkit.theme.*``
registry records that ``render()`` normally injects as ``theme``. This is the
fallback for templates rendered that way, so they still pick up the registry.

Returns a plain mapping: a view instance would need AccessControl
declarations before ``theme/primary_color`` could traverse it from a
template, while a dict needs nothing.
"""

from imio.emailkit.render import get_theme
from Products.Five.browser import BrowserView


class EmailkitThemeView(BrowserView):
    """Return the theme tokens as a mapping."""

    def __call__(self):
        return get_theme()
