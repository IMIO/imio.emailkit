"""Extraction shim: restate the ZCML msgids where i18ndude can see them.

``i18ndude rebuild-pot`` extracts from Python and templates, never ZCML.
The subject/preheader msgids live in ``configure.zcml``, so without this
module they would drop from the catalog.
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
