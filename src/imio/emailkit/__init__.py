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
# Two of the three restyled Plone default mails are deliberately NOT registered
# here: ``mail_password_template`` and ``registered_notify_template``.
# They are rendered by a *stock Plone view*, which means two things:
# their subject is emitted by the template as its own ``Subject:`` header, and
# their body speaks the hosting view's dialect (``options/...`` plus ``python:``
# expressions, because ``MemberData`` cannot be path-traversed at all). A
# registration would therefore resolve to a template ``render()`` can never
# render -- ``render()`` supplies a flat context. See docs/DECISIONS.md.
#
# For those two, the original claim that the default mails are "authored,
# compiled, discovered, tested and shipped exactly like consumer templates" holds
# for every verb except *discovered*, and cannot hold for that one while a stock
# view renders them. The dogfooding intent is intact: they use the same kit, the
# same build, the same staleness gate and the same golden tests.
#
# ``get_username`` is the third restyled default mail, and it IS registered --
# the exception to the paragraph above. Stock Plone has no template for that mail
# at all: it is a hardcoded plaintext string in ``login_help.py``, so there was
# nothing for z3c.jbot to key on and this package overrides the *view* instead
# (``browser/login_help.py``). Owning the view is what buys the flat dialect back:
# it renders through ``render()``, so unlike its two siblings it is genuinely
# discovered, golden-tested and previewable.
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
        "get_username": {
            "subject": _(
                "email_subject_get_username",
                default="Your username",
            ),
            "preheader": _(
                "email_preheader_get_username",
                default="Here is the username you asked for.",
            ),
        },
    },
}


# SPEC §6.1 spells the public API as ``from imio.emailkit import render``, and
# §6.2 spells it as ``from imio.emailkit import Email``. §9 phase 3 adds
# ``render_shell`` -- a ``render()`` sibling, deliberately *not* a builder method,
# so it belongs in the same namespace as ``render``.
#
# These imports are LAST on purpose and must stay last: ``render`` -> ``discovery``
# -> ``interfaces`` imports ``_`` back from this module, so every name above has
# to be bound before we get here. Moving them to the top re-introduces a circular
# import. Keeping the module body above dependency-free also keeps
# ``[tool.setuptools.dynamic] version = {attr = "imio.emailkit.__version__"}``
# cheap: setuptools reads ``__version__`` statically and never has to import
# Plone at build time.
#
# ``imio.emailkit.email`` shadows nothing: Python 3 imports are absolute, so the
# standard library's ``email`` package is still what ``import email`` gets, here
# and inside that module.
from imio.emailkit.email import Email  # noqa: E402, F401  (see comment above)
from imio.emailkit.render import render  # noqa: E402, F401  (see comment above)
from imio.emailkit.render import render_shell  # noqa: E402, F401  (same)
