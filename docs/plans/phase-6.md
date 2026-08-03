# Phase 6 — The get-username mail

**Date:** 2026-08-03
**Spec:** §8.1 (amended by this phase), §8.2, §4, §6.1, §6.2
**Depends on:** Phases 0–5 complete and green

---

## 1. Why this is not "one more jbot override"

The package ships restyled versions of two Plone default mails. A third one — the *"get your username"*
reminder from the login-help form — was never shipped, and the reason is structural rather than an
oversight.

The two shipped mails are real page templates on disk:

```
Products/CMFPlone/browser/login/templates/mail_password_template.pt
Products/CMFPlone/browser/login/templates/registered_notify_template.pt
```

`z3c.jbot` keys on the resolved filename, so it can displace them. The get-username mail has no file.
It is a module-level i18n message, `SEND_USERNAME_TEMPLATE` at `login_help.py:33`, declared
`Content-Type: text/plain`, interpolated with `str.format()` and handed straight to `MailHost` by
`RequestUsername.send_username()` (`login_help.py:161`). **There is nothing for jbot to key on.**

Two further constraints from the same module, both load-bearing for the design below:

| Fact | Location | Consequence |
|---|---|---|
| `RequestUsername` is instantiated by **direct class reference** | `login_help.py:243` | Not a ZCA lookup — cannot be swapped by registering an adapter or utility |
| The mail is sent inside the subform's own `update()` | `login_help.py:129-159` | By the time `LoginHelpForm.update()` returns, the stock mail is already sent |
| The subform only renders when `use_email_as_login` is False | `login_help.py:242` | On email-as-login sites this mail is never sent at all |

So the mechanism has to be a **view override**, not a template override. That is a genuine amendment to
§8.1, which currently says the default mails ship "as `z3c.jbot` overrides" — recorded in §6 below rather
than left as drift.

### 1.1 The compensation

Because we own the view, the template gets a *better* status than the two jbot ones, not a worse one. It
speaks §3's normal flat dialect and renders through §6.1 `render()`, which means it is **discovered**,
previewable and golden-tested like any consumer template. The comment at `__init__.py:25-37` — which
explains that §8's mails cannot be discovered because a stock view renders them — becomes true only of
the two jbot mails, and must say so.

## 2. Scope

### 2.1 Template

`emails/src/templates/get_username.vue` → `src/imio/emailkit/templates/get_username.pt`.

Normal dialect: `${login}`, no `options/`, no `python:`. No `useDoctype()` header block and no
`useOutputPath()` — `output.path` is already correct, unlike the two jbot templates.

Registered in the `emailkit` dict in `__init__.py`, discovered as `imio.emailkit.get_username`:

```python
"get_username": {
    "subject": _("email_subject_get_username", default="Your username"),
    "preheader": _("email_preheader_get_username", default="Here is the username you asked for."),
},
```

Context, flat: `fullname`, `login`, `site_name`, `login_url`, `client_addr`.

Content (approved shape): lead line, the username in a `KitPanel` so it survives skimming, a `KitButton`
to the login form, and the "if you did not ask for this" reassurance paragraph carrying the client
address — mirroring `mail_password.vue` so the two mails read as siblings.

**Hand-authored plaintext twin** at `emails/twins/get_username.txt.pt`, copied into `templates/` by
`make build-emails`. Not `naive_text()` fallback: the entire payload of this mail is one string the
recipient has to be able to read and retype, and the generated twin is not trustworthy enough for that
(see `emails/twins/README.md`).

### 2.2 View override

New `src/imio/emailkit/browser/login_help.py`:

```python
class RequestUsername(stock.RequestUsername):
    def send_username(self, portal, userinfo):
        # Email(...).to(userinfo["userid"]) — a userid, not a raw address, so
        # per-member language negotiation applies (§6.2).
        ...

class LoginHelpForm(stock.LoginHelpForm):
    index = ViewPageTemplateFile(<absolute path to stock templates/login_help.pt>)
    def update(self): ...  # reimplemented; see 2.2.1
```

Registered in `browser/configure.zcml`:

```xml
<browser:page
    name="login-help"
    for="plone.base.interfaces.INavigationRoot"
    class=".login_help.LoginHelpForm"
    permission="zope.Public"
    layer="imio.emailkit.interfaces.IEmailkitLayer"
    />
```

Same `for` and same permission as stock. **Bound to `IEmailkitLayer`**, so §8.2's three-level override
story is preserved unchanged: a site on `:base` gets stock Plone's login-help view and stock Plone's
plaintext mail.

#### 2.2.1 Three decisions inside the override

**We reimplement `update()`, and accept the upstream coupling.** There is no seam: the class name is
hardcoded at `login_help.py:243` and the send happens inside `subform.update()`, so `super().update()`
has already put the stock mail on the wire before it returns. The alternative — temporarily rebinding
`stock.RequestUsername` around a `super().update()` call — is a monkeypatch with a race: Zope's
publisher is threaded and two concurrent login-help requests would see each other's rebind. The copy is
twelve lines. It is paid for by gate 10 below, which pins the source of stock `update()` so a Plone
upgrade that changes it fails loudly instead of silently reverting the feature.

**`index` points at stock's `login_help.pt` by absolute path**, so the form markup is not forked. jbot
keys on the resolved filename, so an existing per-site override of the login-help *form* keeps working.

**`immediate=True`**, matching stock — and not merely for parity. `send_username` catches
`SMTPRecipientsRefused` specifically to avoid disclosing whether an address exists; with transactional
delivery the SMTP conversation happens in `tpc_finish`, long after the `except` clause could run, so the
paranoia handling would be dead code.

**The paranoia contract is preserved verbatim:** unknown address and multiple matches both log and send
nothing, and *all three* outcomes emit the identical status message. This is anti-enumeration behaviour,
not an error-reporting shortcoming, and it must not be "improved".

### 2.3 The IP address, in both mails

`mail_password.vue` renders an empty IP. The bug is upstream and we ported it faithfully — stock
`mail_password_template.pt:36` has the identical expression:

```
tal:define="host request/HTTP_X_FORWARDED_FOR|request/REMOTE_ADDR"
```

`ZopePathExpr._eval` (`Products/PageTemplates/Expressions.py:206-217`) falls through a `|` chain **only
on a traversal exception**, never on a falsy result. And `HTTPRequest.get()` special-cases CGI and
`HTTP_` keys (`ZPublisher/HTTPRequest.py:1050-1054`):

```python
if key in isCGI_NAMEs or key[:5] == 'HTTP_':
    if key in environ and (key not in hide_key):
        return environ[key]
    return ''          # returns '', does not raise
```

With no `X-Forwarded-For` header the first subexpression therefore *succeeds*, yielding `''`, and
`request/REMOTE_ADDR` is unreachable. Measured against a real `HTTPRequest`:

```
no XFF -> HTTP_X_FORWARDED_FOR = ''          <- wins the | chain
no XFF -> REMOTE_ADDR          = '10.1.2.3'  <- never reached
no XFF -> getClientAddr()      = '10.1.2.3'
```

**Fix:** `request/getClientAddr` in `mail_password.vue`; `self.request.getClientAddr()` computed in
Python for `get_username`, whose template receives a flat context.

**Ops consequence, and it is not optional.** `getClientAddr` honours `X-Forwarded-For` only for proxies
declared in `zope.conf`; `HTTPRequest.trusted_proxies` defaults to `[]`, and this checkout's
`instance.yaml` declares none. Measured:

```
with XFF, no trusted-proxy -> getClientAddr() = '10.1.2.3'   # the proxy, not the client
```

So a site behind nginx without `trusted-proxy` will print the proxy's address. That is correct by Zope's
rules and useless in a mail, so it is documented in the README as a deployment requirement rather than
worked around in the template. Trusting a client-settable header to avoid an ops note was considered and
rejected: it would let a sender choose which IP the mail names.

### 2.4 Reachability, stated rather than discovered

`login_help.py:242` hides the subform entirely when `use_email_as_login` is True. On those sites this
mail is inert — not broken, but never sent. Gate 8 covers both registry states so that a later reader
does not "fix" the missing form.

## 3. Non-goals

- **No changes to `Email` or `render()`** — §6.2 and §6.1 are frozen; this is a caller.
- **No monkeypatching**, of `MailHost` (§8.4) or of `login_help`'s module globals (2.2.1).
- **No change to the paranoia behaviour**, in either direction.
- **No fork of `login_help.pt`** — the form markup stays Plone's.
- **No new builder methods**, no new recipient sources.
- **No attempt to make the subform appear on email-as-login sites.** That is Plone's product decision.
- **No `trusted-proxy` written into `instance.yaml` as a default.** Declaring a proxy that is not there
  is a spoofing hole; it is documented, not assumed.

## 4. Test plan — `tests/test_get_username.py`

| # | Gate |
|---|---|
| 1 | `imio.emailkit.get_username` is discovered, with subject and preheader msgids |
| 2 | golden files match for `en` and `fr`, HTML and text |
| 3 | the plaintext twin is the hand-authored one, and contains the username |
| 4 | `login-help` on an `IEmailkitLayer`-marked request resolves to our class |
| 5 | `login-help` on an unmarked request resolves to stock Plone's (the `:base` opt-out) |
| 6 | `handleGetUsername` with a real member sends one HTML mail whose body contains the username, and whose subject is our msgid — assert on values, never on markers |
| 7 | paranoia: no match, and more than one match — no mail sent, identical status message in all three outcomes |
| 8 | `use_email_as_login` True → no `RequestUsername` subform; False → present |
| 9 | language: two members with different preferred languages get their own language's mail |
| 10 | **upstream-drift guard** — the source of stock `LoginHelpForm.update` is what we forked from |
| 11 | IP regression: with no `X-Forwarded-For`, both mails render a non-empty client address |
| 12 | the two existing jbot mails still pass every Phase 1 gate unchanged |

Gate 11 is the one that would have caught the original bug, and it is deliberately written against a
request with **no** `X-Forwarded-For` — the configuration under which the stock expression silently
yields `''`. For `get_username` it asserts on the rendered mail; for `mail_password` it asserts through
the stock view, because that mail has no snapshot (see 4.1).

### 4.1 Two existing guards this phase has to satisfy

The suite already enforces the wiring, which is worth knowing before starting rather than discovering as
two red tests:

- `test_golden.py:88` (`test_every_registered_template_has_a_fixture`) drives off **discovery**, so
  registering `get_username` without `tests/fixtures/get_username.py` fails immediately.
- `test_golden.py:166` (`test_no_orphan_fixtures`) checks fixtures against `COVERED`, which is built from
  the harness classes' `templates`. So **`get_username` must also be added to
  `support.RENDERABLE_TEMPLATES`** — a fixture that no harness renders is an orphan and fails.

And one guard it must *not* trip: `test_golden.py:146`
(`test_the_default_mails_are_not_registered_for_discovery`) asserts that `DEFAULT_MAIL_TEMPLATES` never
appear in discovery. `get_username` is deliberately **not** added to that tuple — it is renderable, which
is the whole point of 1.1 — so the guard stays green and keeps protecting the two mails it is about.

## 5. Risks

| Risk | Response |
|---|---|
| A Plone upgrade changes `LoginHelpForm.update` and our fork silently reverts the feature | gate 10 pins the upstream source and fails the build |
| A Plone upgrade turns the get-username mail into a real template | good news, not a risk: delete the view override, keep the template, add a jbot mapping — record it as a decision |
| `getClientAddr` prints `127.0.0.1` on a misconfigured production site | README ops note; gate 11 cannot catch a deployment mistake and is not asked to |
| Someone "fixes" the paranoia behaviour into helpful error messages | non-goal in §3, gate 7, and a comment at the call site |
| The override grows into a general login-help customisation seam | it overrides `update()` and `send_username()` and nothing else; more belongs in a decision entry |

## 6. Documentation changes

| File | Change |
|---|---|
| `SPEC.md` §8.1 | amend the scope sentence (a third mail) **and** the "as `z3c.jbot` overrides" mechanism claim (one of the three is a view override) |
| `SPEC.md` §8.2 | note the asymmetry: this template's markup is jbot-overridable like any other, but the view registration is layer-bound |
| `SPEC.md` §9 | add the phase 6 row |
| `docs/DECISIONS.md` | why jbot cannot reach this mail; why `update()` is forked rather than patched; the upstream IP bug with the `ZopePathExpr` / `HTTPRequest.get` evidence |
| `src/imio/emailkit/__init__.py` | amend the `25-37` comment: "not discovered" now applies to the two jbot mails only |
| `README.md` | the `trusted-proxy` ops requirement |
| `news/` | fragments for the new mail and for the IP fix (separate — one is a feature, one is a bugfix) |
| locales | `make i18n`, then FR/NL/DE for every new msgid |

## 7. Order of work

1. Fixture `tests/fixtures/get_username.py`, then the failing gates 1–3.
2. `get_username.vue` + twin; `make build-emails`; `make update-golden` once the output is reviewed by eye.
3. Registration in `__init__.py` **and** `support.RENDERABLE_TEMPLATES` (4.1); gates 1–3 green.
4. `browser/login_help.py` + ZCML; gates 4–10.
5. The IP fix in `mail_password.vue`; rebuild; gate 11. **No golden re-baseline** — `mail_password` has no
   snapshot by design (4.1), so its assertion is in `tests/test_default_mails.py` through the stock view.
6. `make check-emails` (both §5 gates), `make lint`, full suite — gate 12 confirms no Phase 1 regression.
7. Docs, `make i18n`, translations, news fragments.
