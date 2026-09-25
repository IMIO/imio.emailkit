"""Extraction shim: restate the ZCML msgids where i18ndude can see them.

``python -m imio.emailkit.locales`` rebuilds the ``.pot`` with ``i18ndude
rebuild-pot``, which extracts from Python and page templates but never from
ZCML. The subject/preheader msgids live in ``configure.zcml`` since the
``emailkit:templates`` directive replaced the registration dict, so without
this module a locales rebuild would drop them from the catalog.

``tests/test_msgids.py`` fails when this file and ``configure.zcml`` drift.
"""

from imio.emailkit import _


_("email_subject_notification", default="Notification")
_("email_preheader_notification", default="You have a new notification.")
_("email_subject_get_username", default="Your username")
_("email_preheader_get_username", default="Here is the username you asked for.")
_("email_subject_mail_password_template", default="Password reset request")
_(
    "email_preheader_mail_password_template",
    default="Follow the link to choose a new password.",
)
_(
    "email_subject_registered_notify_template",
    default="An account has been created for you",
)
_(
    "email_preheader_registered_notify_template",
    default="Follow the link to choose your password.",
)
_("email_subject_sso_migrated", default="Your account now uses Wallonie Connect")
_(
    "email_preheader_sso_migrated",
    default="Log in from now on with Wallonie Connect, using your email address.",
)
