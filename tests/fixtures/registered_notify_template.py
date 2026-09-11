"""Context data for ``imio.emailkit:registered_notify_template`` (SPEC §7).

The keys are exactly what
``imio.emailkit.browser.default_mails.RegisteredNotifyView.build_context``
returns.

``expires`` is a real ``datetime``, which is what the view passes too (converted
from the Zope ``DateTime`` ``portal_password_reset`` hands out). An ISO string
would work at render time -- ``format_datetime`` coerces one -- but it would be
the one fixture value that never appears in the output verbatim, because the
template formats it; §7's "every fixture value reaches the html" check would then
have to special-case it. "Plain data, not objects" is about Zope path traversal,
and this value is reached by a ``python:`` call, not traversed.

Absent on purpose, because ``render()`` supplies them: ``lang``, ``theme`` and
its tokens, ``preheader``.
"""

import datetime


CONTEXT = {
    "fullname": "Jeanne Dupont",
    "username": "jdupont",
    "activation_url": (
        "https://sambreville.example.be/passwordreset/8f3c1a9e2b?userid=jdupont"
    ),
    "expires": datetime.datetime(2026, 9, 18, 17, 30),
    "email_from_name": "Délibérations.be",
}
