"""Context data for ``imio.emailkit:get_username``.

The username-reminder mail, sent by the login-help form's *"Get your username"*
button. Unlike the two Plone default mails this one is **discovered and
``render()``-able**: the view that sends it is
ours, so it speaks the flat dialect and every key below is a plain top-level
name in the template.

As with ``notification.py``, the names ``render()`` injects are deliberately
**absent** -- ``lang``, ``theme`` and its tokens, ``portal_url``, ``preheader``.
Pinning them here would hide a broken injection rather than catch one.

``client_addr`` *is* present, and has to be: it is the one value in this mail
that comes from the request rather than from the registry, and ``render()`` knows
nothing about it. The view computes it with ``request.getClientAddr()`` -- see
``tests/test_get_username.py`` for why that accessor and not the ``|`` chain
stock Plone uses.
"""

CONTEXT = {
    # Accented on purpose, same reasoning as notification.py: a charset
    # regression in the compiled output or in the render surfaces here.
    "fullname": "Françoise Lemaître",
    # A login that is NOT an email address. The subform only renders when
    # `use_email_as_login` is False (`login_help.py:242`), so a username-shaped
    # value is the only realistic fixture -- an email here would depict a state
    # in which this mail is never sent.
    "login": "flemaitre",
    "site_name": "Commune de Sambreville",
    "login_url": "https://sambreville.example.be/login",
    "client_addr": "81.240.17.203",
}
