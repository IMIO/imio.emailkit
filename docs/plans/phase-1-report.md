# Phase 1 — Better defaults: report

**Date:** 2026-07-29
**Plan:** `docs/plans/phase-1.md`
**Stack verified against:** Plone 6.2.1, Zope 6.1, Chameleon 4.6.0, z3c.jbot 3.1, Python 3.12,
Maizzle 6.0.7, Tailwind 4.3.3

---

## Exit criteria

Verbatim from §9:

> | **1 — Better defaults** | `render()` + locale helpers, built-in kit (`Main.vue` + core components + tokens; a11y defaults, `lang`, preheader slot), restyled password-reset & registration mails, `:base`/`:default` profiles | Installed on one production site; stock mails restyled; opt-out and layer-override both verified |

| Clause | Status |
|---|---|
| `render()` + locale helpers | **done** — frozen §6.1 signature, CLDR-bound helpers |
| built-in kit | **done** — `Main.vue`, 3 components, `@theme` tokens, a11y defaults, `lang`, preheader |
| restyled password-reset & registration mails | **done** — verified on a live site |
| `:base` / `:default` profiles | **done** |
| stock mails restyled | **verified** |
| opt-out verified | **verified** |
| layer-override verified | **verified** |
| *installed on one production site* | **substituted — see below** |

### The one clause not met as written

A production site is not mine to deploy. The substitute is a **real Plone 6.2.1 instance built
from this repo** (`make install && make create-site`), checked against a live ZODB rather than a
test fixture:

```
$ .venv/bin/zconsole run instance/etc/zope.conf scripts/verify_install.py
  [PASS] imio.emailkit:default is applied -- version=('1000',)
  [PASS] IEmailkitLayer is registered
  [PASS] the three theme records exist
  [PASS] mail_password_template resolves to our override -- .../browser/overrides/Products.CMFPlone.browser.login.templates.mail_password_template.pt
  [PASS] registered_notify_template resolves to our override -- .../browser/overrides/Products.CMFPlone.browser.login.templates.registered_notify_template.pt
  [PASS] render() returns html and text
  [PASS] no raw ${...} survived the render
  [PASS] CSS was inlined
  [PASS] lang came from the render language
ALL EXIT-CRITERION CHECKS PASSED
```

What this does **not** cover, and what the maintainer still has to do: a real MTA, real recipients,
and real mail clients. `scripts/verify_install.py` is committed so the same check can be run on the
production site as the acceptance step.

## Test evidence

```
$ python -m pytest tests -q
125 passed, 1 skipped in 57.77s

$ make check-emails
  ok        notification.pt
  ok        Products.CMFPlone.browser.login.templates.mail_password_template.pt
  ok        Products.CMFPlone.browser.login.templates.registered_notify_template.pt
==> Email build output is up to date

$ make check          # ruff check + format + pyroma + check-python-versions + zpretty
exit 0        All checks passed!        Final rating: 10/10
```

The staleness gate was verified by **tampering**: corrupting a committed `.pt` makes it exit 2 with
`STALE notification.pt` and a diff. A gate that has only ever been seen to pass has not been tested.

The one skip is honest: `notification` never calls `format_datetime`, so the *binding* of helpers to
the render language is not observable end-to-end through a template. The helpers themselves have 11
differential tests (FR/NL/EN/DE ordering, month-name localisation, decimal separators).

## What Phase 1 found

Phase 0's thesis — *failures in this pipeline are silent* — held up, and got worse. Four more
defects, every one of which produced a **successful build**:

1. **`@import "@maizzle/tailwindcss"` cannot live in the kit's CSS.** Tailwind resolves bare
   specifiers from the importing file, and a kit directory inside an egg has no `node_modules`
   ancestor. **Maizzle catches CSS errors and ships the uncompiled stylesheet with exit 0.**
2. **The formatter breaks conditional comments across lines**, after which Chameleon re-serialises
   them malformed and **Outlook silently ignores every MSO fallback**. Phase 0 shipped this latent;
   its single-line comments happened to mask it.
3. **`<Outlook :open>` with an empty slot emits `<!--[endif]---->`** — `--` in a comment, which
   makes the `.pt` unparseable at runtime.
4. **`htmlWhitespaceSensitivity: 'ignore'` breaks the line before punctuation**, so "account x ."
   renders — and because that text is also the `i18n:translate` default, the stray space is baked
   into the `.pot`.

Plus: **`Subject: <span i18n:translate=…>` needs `tal:omit-tag=""`**, or the header ships as
`Subject: <span>Reset your password</span>`. The Phase 0 spike had this bug.

The `--`-in-a-comment hazard bit three separate times in this phase alone — in a `.vue` comment, in
`profiles.zcml`, and in `browserlayer.xml` while I was editing it. It is now guarded structurally
for the compiled output (the comment stripper) but remains a live trap in ZCML and XML.

## Corrections to earlier work

- **A Phase 0 finding was wrong and had been acted on.** "A partial `css:` key does not deep-merge"
  is false: Maizzle uses `defu`, and `resolveConfig` on a config supplying only `css.purge` still
  returns `inline: true`. It was an untested hypothesis formed while chasing dead inlining, whose
  only real cause was caveat A1. Corrected in `phase-0-report.md` and `DECISIONS.md` rather than
  deleted, because it was committed. The advice to restate every `css` key survives on different
  grounds: consumers *extend* the base config and object spread is shallow.
- **A Phase 1 decision was withdrawn mid-phase.** "Build the default mails into `templates/` and
  copy to `browser/overrides/`" would have made them discoverable but still not renderable: the
  blocker is the dialect, not the path. §8's "discovered … exactly like consumer templates" is now
  recorded as true of every verb except *discovered*.
- **`test_theme_records_removed` was right and the implementation was the gap.** Uninstall now
  removes the theme records: a record whose defining interface is gone makes the registry control
  panel raise, which outweighs the instinct to preserve settings.

## Two gates that fought

`make check` runs `zpretty` over `src`, and the compiled `.pt` files live under `src`. `zpretty`'s
formatting is not Maizzle's, so letting it near them would make `check-emails` report them stale
**forever**. `zpretty` is now pointed at hand-written `*.zcml`/`*.xml` only. When a formatting gate
and a correctness gate disagree, the correctness gate wins.

## Deferred, with reasons

| Item | Why | Lands in |
|---|---|---|
| `make preview-emails` has no watcher / live reload | it compiles, renders through `render()` in a real site, and serves with a language switcher; wiring a watcher to a process holding a ZODB connection is the part with real design in it | Phase 4, as `bin/preview-emails` |
| Real dark-mode CSS in `Main.vue` (§3) | needs class-free selectors to survive `css.purge` plus per-client testing a browser cannot give | Phase 2, with the send-test button (§6.3) |
| Hand-authored `.txt.pt` twins | §4's naive-extraction fallback covers it; Maizzle's plaintext destroys `tal:`/`i18n:` | Phase 2+, per template as needed |
| Golden base class exported for consumers | it lives in `tests/`, not the egg | Phase 4 |
| Authoring lint (gate 2 of `check-emails`) | Phase 4 per §5 | Phase 4 |

## Spec review outcome

`spec-guardian` reviewed the whole phase: **PASS WITH CONCERNS**. All hard boundaries intact, §6.1's
signature exactly as frozen, no scope creep against §9, and the two riskiest checks clean — zero
Chameleon placeholders in any literal `style`/`class` (caveat A1) and a genuine `:base` opt-out with
both positive and negative assertions on rendered output.

Everything it raised was fixed rather than argued:

| Finding | Resolution |
|---|---|
| **VIOLATION** — the README's only `render()` example named an unregistered template and would raise `TemplateNotFound` | rewritten to `imio.emailkit:notification`, with a note explaining why the default mails are not discoverable |
| **VIOLATION** — README promised a `.txt.pt` twin per template | corrected to describe hand-authored twins and the fallback |
| **CONCERN** — README sold dark mode and `multipart/alternative` as delivered | both now scoped to what actually ships |
| **CONCERN** — `naive_text()` kept the hidden preheader, freezing invisible filler into the plaintext golden | hidden elements and zero-width characters stripped |
| **GAP** — no `.txt.pt` anywhere, so §4's *primary* path was unexecuted code | `notification.txt.pt` hand-authored; it also exposed a `FileNotFoundError` in `render()` |
| **GAP** — `target_language` injection and namespace precedence undocumented | recorded in `DECISIONS.md` |
| **GAP** — `Main.vue`'s named `preheader` slot is a second mechanism | recorded, scoped to a build-time fallback |
| **CONCERN** — `@@emailkit_theme` registered `for="*"` | rationale recorded |
| **CONCERN** — a formatter had edited `SPEC.md` | reverted; spec and docs fenced off from every formatter |

The `SPEC.md` one is the most uncomfortable finding of the phase: `make format` ran `ruff` with no
path argument, ruff's preview formatter rewrites fenced Python inside markdown, and it silently
collapsed §6.2's builder chain — an unnoticed tool edit to the approved source of truth.

## Known quirks documented rather than papered over

- **`is_product_installed()` is `False` on a `:base`-only site.** Plone's quick-installer asks "was
  the `default` profile applied?". `:base` is a real install with a working runtime; the answer is
  Plone's definition, not ours to redefine. In the README.
- **§8.2 level 2 reaches the two shipped mails by a different route** than consumer templates: no
  `render()` runs, so the override reads the registry via `@@emailkit_theme`. Consequently the stock
  view's namespace has no locale helpers either — a jbot-hosted override cannot call
  `format_datetime`.
- **Locale helpers need `${python: format_date(x)}`.** TAL path expressions cannot call functions.
