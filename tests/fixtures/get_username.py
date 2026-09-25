"""Context data for ``imio.emailkit:get_username``, the username-reminder mail.

Names ``render()`` injects (``lang``, ``theme`` and its tokens,
``portal_url``, ``preheader``) are absent on purpose. ``client_addr`` is
present: it comes from the request, via ``request.getClientAddr()``, not the
registry.
"""

CONTEXT = {
    # Accented on purpose: a charset regression shows up here.
    "fullname": "Françoise Lemaître",
    # A login that is not an email address: the subform only renders when
    # `use_email_as_login` is False, so this is the only realistic fixture.
    "login": "flemaitre",
    "site_name": "Commune de Sambreville",
    "login_url": "https://sambreville.example.be/login",
    "client_addr": "81.240.17.203",
}
