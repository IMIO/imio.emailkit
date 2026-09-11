Render Plone's password-reset and registration mails through `render()` like every
other template, by owning their views instead of overriding their page templates
with `z3c.jbot`.

They were the package's only second-class templates. A stock CMFPlone view
rendered them, so their bodies had to speak that view's dialect
(`options/member`, `python:member.getProperty(...)`, no locale helpers, no
`theme`) and they could not be registered for discovery -- which meant the
password-reset mail, the one a commune is most likely to want in its own colours,
was the one mail that never appeared in `bin/preview-emails` or
`@@emailkit-preview` and had no golden files.

`imio.emailkit.browser.default_mails` now registers `mail_password_template` and
`registered_notify_template` under the same name, `for` and permission as stock,
differing only by layer, exactly as `login_help.py` has always done for
`get_username`. Both are ordinary registered templates now: one dialect, one
preview list, fixtures, goldens and plaintext twins. Their subjects moved from a
hand-written `Subject:` header in the template to the `<emailkit:templates>`
registration, so they are translated per recipient by the same code path as every
other subject.

Two behaviour changes fall out. The account-activation mail formats its expiry
date through the kit's `format_datetime`, bound to the *recipient's* language;
stock followed the request's, so a Dutch member could get a French date. And a
site package now overrides `imio.emailkit.templates.mail_password_template.pt`
rather than the CMFPlone file -- SPEC 8.2 level 1 is unchanged in mechanism, with
one filename convention for every template the package ships.

The `:base` opt-out is untouched: the views are bound to `IEmailkitLayer`, so a
site that installs `:base` still gets stock Plone's views and stock Plone's mails.
