"""Init and utils."""

from zope.i18nmessageid import MessageFactory

import logging


__version__ = "1.0.0b2.dev0"

PACKAGE_NAME = "imio.emailkit"

_ = MessageFactory(PACKAGE_NAME)

logger = logging.getLogger(PACKAGE_NAME)


# These imports must stay last: ``render`` imports ``_`` back from this
# module, through ``discovery`` and ``interfaces``. Moving them up causes
# a circular import.
#
# ``imio.emailkit.email`` does not shadow the standard library ``email``
# package: Python 3 imports are absolute.
from imio.emailkit.email import Email  # noqa: E402, F401
from imio.emailkit.render import render  # noqa: E402, F401
from imio.emailkit.render import render_shell  # noqa: E402, F401
