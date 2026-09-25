"""Context data for ``imio.emailkit:registered_notify_template``.

Keys match ``RegisteredNotifyView.build_context``. ``expires`` is a real
``datetime``, matching what the view passes. ``lang``, ``theme`` and its
tokens, and ``preheader`` are absent, since ``render()`` supplies them.
"""

import datetime


CONTEXT = {
    "fullname": "Jeanne Dupont",
    "username": "jdupont",
    "email": "jeanne.dupont@example.be",
    "password_url": (
        "https://sambreville.example.be/passwordreset/8f3c1a9e2b?userid=jdupont"
    ),
    "expires": datetime.datetime(2026, 9, 18, 17, 30),
    "email_from_name": "Délibérations.be",
}
