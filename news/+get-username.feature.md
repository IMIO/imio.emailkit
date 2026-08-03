Restyle Plone's "get your username" reminder mail. Stock Plone sends it as a
hardcoded plaintext string from `login_help.py`, with no template for `z3c.jbot`
to override, so `imio.emailkit` overrides the login-help *view* instead and sends
the mail through the `Email` builder. The new `get_username` template is an
ordinary registered template: discovered, previewable and golden-tested. Like the
two jbot-overridden mails, it is bound to `IEmailkitLayer`, so installing the
`:base` profile still leaves stock Plone untouched.

Note that Plone only shows the "Get your username" form when `use_email_as_login`
is off; on sites that log in by email this mail is never sent.
