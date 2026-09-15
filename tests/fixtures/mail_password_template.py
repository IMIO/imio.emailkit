"""Context data for ``imio.emailkit:mail_password_template``.

The keys are exactly what
``imio.emailkit.browser.default_mails.MailPasswordView.build_context`` returns,
which is what makes this fixture the contract it is meant to be: add a
placeholder to the template without adding a key here, and the golden test fails.

``is_anonymous`` is ``True`` -- the forgotten-password form, which is how this
mail is sent in almost every case, and the branch that carries the IP-address
panel.

``userid`` is therefore **absent**, and that is the one place this fixture departs
from "one key per placeholder". The template's two branches are mutually
exclusive and use a different key each (``userid`` in the administrator branch,
``client_addr`` in the anonymous one), so no single fixture can carry both without
one of them becoming dead data that "every fixture value reached the html" would
correctly flag. The administrator branch is covered in
``tests/test_default_mails.py``, which renders the view for real.

Absent on purpose, because ``render()`` supplies them: ``lang``, ``theme`` and
its tokens, ``preheader``.
"""

CONTEXT = {
    # Non-ASCII on purpose: a charset regression shows up nowhere else.
    "site_name": "Délibérations.be — Sambreville",
    "is_anonymous": True,
    "reset_url": "https://sambreville.example.be/passwordreset/8f3c1a9e2b",
    "expiration_hours": 168,
    "client_addr": "81.240.12.7",
}
