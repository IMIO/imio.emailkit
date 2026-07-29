"""Init and utils."""

from zope.i18nmessageid import MessageFactory

import logging


__version__ = "1.0.0a0"

PACKAGE_NAME = "imio.emailkit"

_ = MessageFactory(PACKAGE_NAME)

logger = logging.getLogger(PACKAGE_NAME)


# SPEC §4: imio.emailkit is its own first consumer -- it registers its own
# templates through exactly the mechanism external addons use. ``pyproject.toml``
# points the ``imio.emailkit.templates`` entry point at this dict.
#
# ``directory`` is relative to this package. ``subject`` is an i18n msgid
# translated per recipient language at send time; ``preheader`` is the optional
# hidden inbox-preview line the kit layout renders (SPEC §3).
#
# The restyled Plone default mails of SPEC §8 are deliberately NOT registered
# here. They are rendered by a *stock Plone view*, which means two things:
# their subject is emitted by the template as its own ``Subject:`` header, and
# their body speaks the hosting view's dialect (``options/...`` plus ``python:``
# expressions, because ``MemberData`` cannot be path-traversed at all). A
# registration would therefore resolve to a template ``render()`` can never
# render -- ``render()`` supplies a flat context. See docs/DECISIONS.md.
#
# §8's claim that those mails are "authored, compiled, discovered, tested and
# shipped exactly like consumer templates" holds for every verb except
# *discovered*, and cannot hold for that one while a stock view renders them.
# The dogfooding intent is intact: they use the same kit, the same build, the
# same staleness gate and the same golden tests.
#
# ``notification`` is the template that exercises the ordinary consumer flow --
# flat dialect, discovered, rendered through ``render()``.
emailkit = {
    "directory": "templates",
    "templates": {
        "notification": {
            "subject": _(
                "email_subject_notification",
                default="Notification",
            ),
            "preheader": _(
                "email_preheader_notification",
                default="You have a new notification.",
            ),
        },
    },
}


# SPEC §6.1 spells the public API as ``from imio.emailkit import render``.
#
# This import is LAST on purpose and must stay last: ``render`` -> ``discovery``
# -> ``interfaces`` imports ``_`` back from this module, so every name above has
# to be bound before we get here. Moving it to the top re-introduces a circular
# import. Keeping the module body above dependency-free also keeps
# ``[tool.setuptools.dynamic] version = {attr = "imio.emailkit.__version__"}``
# cheap: setuptools reads ``__version__`` statically and never has to import
# Plone at build time.
from imio.emailkit.render import render  # noqa: E402, F401  (see comment above)
