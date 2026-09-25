"""Context data for ``imio.emailkit:mail_password_template``.

Keys match ``MailPasswordView.build_context``. ``userid`` is absent: the
template's two branches are mutually exclusive, and this fixture covers the
anonymous one (``client_addr``); the administrator branch (``userid``) is
covered in ``tests/test_default_mails.py``.
"""

CONTEXT = {
    # Non-ASCII on purpose: a charset regression shows up here.
    "site_name": "Délibérations.be — Sambreville",
    "is_anonymous": True,
    "reset_url": "https://sambreville.example.be/passwordreset/8f3c1a9e2b",
    "expiration_hours": 168,
    "client_addr": "81.240.12.7",
}
