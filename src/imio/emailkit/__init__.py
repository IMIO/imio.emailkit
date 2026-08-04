"""Init and utils."""

from zope.i18nmessageid import MessageFactory

import logging


__version__ = "1.0.0a0"

PACKAGE_NAME = "imio.emailkit"

_ = MessageFactory(PACKAGE_NAME)

logger = logging.getLogger(PACKAGE_NAME)


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
