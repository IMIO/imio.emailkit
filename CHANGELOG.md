# Changelog

<!--
   You should *NOT* be adding new change log entries to this file.
   You should create a file in the news directory instead.
   For helpful instructions, please see:
   https://github.com/plone/plone.releaser/blob/master/ADD-A-NEWS-ITEM.rst
-->

<!-- towncrier release notes start -->

## 1.0.0b1 (2026-09-14)


### New features:

- Add `imio.recipe.emailkit`, generating `bin/compile-emails`, `bin/check-emails`
  and `bin/preview-emails` from a buildout part, with `kit-mode = path | copy` and
  `compile-on-install` off by default so a plain buildout run invokes no Node.
  SPEC §5. 
- Add `render(name, context, language)`, entry-point template discovery, the
  locale-aware `format_date`/`format_datetime`/`format_number` helpers, the three
  `imio.emailkit.theme.*` registry tokens and FR/NL/DE catalogs. SPEC §4, §6.1. 
- Add `render_shell(subject, body_html, language=None)`, a `render()` sibling that
  wraps an existing HTML mail body in the kit shell with no template redesign.
  `${...}` inside the injected body is emitted literally, never evaluated. SPEC §9
  phase 3. 
- Add dark-mode support to the kit shell, keyed on `data-dark` attribute selectors so
  the rules survive `css.purge`. Verified structurally; real-client verification needs
  the send-test button. 
- Add the *"Send styled email"* content-rule action: the edit form offers every
  template SPEC §4 discovery knows about, through a new
  `imio.emailkit.templates` vocabulary, plus two recipient sources (an explicit
  list of addresses or user ids, and the triggering content's owner). The executor
  delegates to the `Email` builder, so per-language sending, the registration's
  subject and transaction-safe delivery come for free, and it never swallows an
  error. The stock mail action is untouched. SPEC §8.3. 
- Add the Manager-only `@@emailkit-preview` view: template listing, iframe rendering
  from the committed fixtures, a language switcher, a theme-token panel and a
  send-test button that mails the logged-in user's own address. SPEC §6.3. 
- Add the `Email` builder with `IEmailRecipient` adapters, polymorphic attachments,
  per-language sending (one message per recipient-language group) and
  transaction-safe queued delivery through `IMailHost`. SPEC §6.2. 
- Add the authoring lint (`imio.emailkit.lint`), the second gate of
  `check-emails`: eight regex rules for the SPEC §3 authoring rules, each one
  covering a failure mode that otherwise compiles cleanly and breaks at runtime. 
- Add the built-in design kit (`Main.vue`, `Button`, `Panel`, `DataTable`, the
  Tailwind `@theme` entry) with accessibility defaults, `lang`, `i18n:domain` and the
  preheader slot baked in, plus the restyled Plone password-reset and registration
  mails installed by the `default` profile and opt-out-able via `base`. SPEC §3, §8. 
- Render Plone's password-reset and registration mails through `render()` like every
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
- Restyle Plone's "get your username" reminder mail. Stock Plone sends it as a
  hardcoded plaintext string from `login_help.py`, with no template for `z3c.jbot`
  to override, so `imio.emailkit` overrides the login-help *view* instead and sends
  the mail through the `Email` builder. The new `get_username` template is an
  ordinary registered template: discovered, previewable and golden-tested. Like the
  two jbot-overridden mails, it is bound to `IEmailkitLayer`, so installing the
  `:base` profile still leaves stock Plone untouched.

  Note that Plone only shows the "Get your username" form when `use_email_as_login`
  is off; on sites that log in by email this mail is never sent. 
- Ship the golden-file test base class as `imio.emailkit.golden`, so consumer
  add-ons get the SPEC §7 harness from the egg instead of copying it. 
- Templates from consumer add-ons are now registered with the
  `<emailkit:templates>` ZCML directive instead of the
  `imio.emailkit.templates` entry point + dict. Duplicate names become
  configuration conflicts, `overrides.zcml` works, and the subject/preheader
  msgid domain comes from the ZCML file's `i18n_domain`. The buildout recipe
  and the `bin/` scripts discover consumers by executing their ZCML through a
  permissive configuration machine — no entry point, no hand-rolled parsing. 


### Bug fixes:

- Fix the empty origin IP in the password-reset mail. The template used
  `request/HTTP_X_FORWARDED_FOR | request/REMOTE_ADDR`, copied from stock Plone,
  which renders *empty* whenever no `X-Forwarded-For` header is present:
  `HTTPRequest.get()` returns `''` for a missing `HTTP_` key instead of raising, and
  a TAL `|` chain falls through only on a traversal exception, so the `REMOTE_ADDR`
  fallback was unreachable. Both login-help mails now use `request/getClientAddr`.

  Deployments behind a reverse proxy must declare it as `trusted-proxy` in
  `zope.conf` for the real client address to appear; otherwise Zope correctly
  reports the proxy's own address. See the README. 
- Stop `bin/preview-emails` from printing a traceback whenever the browser asks for
  a file that is not there.

  `PreviewHandler.log_message` filtered the live-reload poll out of the access log
  by testing `VERSION_PATH not in args[0]`. For an access log `args[0]` is the
  request line, but `BaseHTTPRequestHandler.log_error` routes through the same
  method and passes an `HTTPStatus`, so the membership test raised
  `TypeError: argument of type 'HTTPStatus' is not iterable` inside the handler
  thread. Every 404 therefore printed a long traceback about the logging code
  rather than a one-line "file not found".

  The commonest trigger was `/favicon.ico`, which every browser requests on every
  page load; that one is now answered with a 204 rather than left to 404, since the
  preview directory holds rendered mails and nothing else. 


### Internal:

- Prepare the first PyPI release of both distributions in this repository.
  `imio.emailkit` and `imio.recipe.emailkit` each get a `Development Status :: 4 -
  Beta` classifier, a `setuptools>=77` build requirement (the declared 68.2 floor
  could never have built the PEP 639 SPDX `license` field; it only worked because
  PEP 517 isolation fetches a newer setuptools), and a prefixed zest.releaser
  `tag-format`, because one git repository shipping two distributions has one tag
  namespace and a colliding bare version tag makes zest.releaser build the wrong
  one. The recipe also gains its own `LICENSE.GPL`, having declared `GPL-2.0-only`
  while shipping no licence text. 


### Documentation:

- Open `README.md` with a rendered mail. A package whose whole subject is what an
  email looks like began with a title and eleven badges; the banner is a real render
  of the notification template in the v3 design. The image is referenced by absolute
  `raw.githubusercontent.com` URL, because the README is also the PyPI long
  description and PyPI resolves no relative links, and it lives in `docs/` — which
  `MANIFEST.in` does not graft, so it never reaches the sdist or the wheel. 
- Publish the developer documentation as a site at
  <https://imio.github.io/imio.emailkit/>, built from `docs/site/` and deployed by a
  new `docs.yml` workflow on every push to `main` that touches it. Twenty pages
  covering the quickstart, the architecture, the full runtime API, the eight authoring
  rules, the fixture/golden workflow, entry-point distribution, the content-rule action,
  the `render_shell` migration routes and the three override levels. Adding a page is an
  MDX file plus one line in the navigation array; search, the per-page section nav and
  the previous/next links all follow from that. `README.md` is now the pitch and a link
  to the site, so no topic has two homes; `SPEC.md` and `docs/DECISIONS.md` remain the
  authority on *why*. 


### Tests

- Test suite for Phase 2's API, written from SPEC §6.2/§6.3: recipient resolution (string,
  member, userid, mixed and nested iterables, duplicates, `RecipientError`), every
  attachment source and its filename/mimetype inference, per-language sending (one message
  per group, each with its own subject translation and its own rendered body), the subject
  default and both override forms, the `multipart/alternative` shape, and §7's named
  transaction-abort test. `imio.emailkit.testing` now ships
  `install_recording_mailhost()`, a MailHost double that replaces `_makeMailer` rather than
  `_send` so a queued delivery can be told apart from an immediate one — which is what
  makes "abort → queue empty" a real assertion instead of a constant. 
- Test suite, golden-file harness and CI for Phase 1: `imio.emailkit.testing` layers for
  both the `:default` and `:base` profiles, discovery / `render()` / locale-helper /
  theme-token tests, the §8.2 override matrix (restyled defaults, opt-out, site-layer
  precedence), and a GitHub Actions job that fails when the committed `.pt` files differ
  from a fresh Maizzle build.
