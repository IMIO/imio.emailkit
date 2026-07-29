# Phase 0 — Spike report

**Date:** 2026-07-29
**Toolchain under test:** `@maizzle/framework` **6.0.7**, Tailwind **4.3.3**, Node **24.11.1**
**Runtime under test:** Plone **6.2.1**, Zope **6.1**, Chameleon **4.6.0**, z3c.jbot **3.1**, Python **3.12**
**Plan:** `docs/plans/phase-0.md`
**Evidence:** everything under `spike/` — sources, both builds, the purge diff, rendered HTML

---

## Verdict summary

| # | Assumption | Verdict |
|---|---|---|
| **(a)** | Maizzle 6 output survives Chameleon (`${}`, `tal:repeat` in a table row, i18n, inlined styles after purge) | **CONFIRMED WITH CAVEATS** — 15/15 checks pass; three caveats below are mandatory, not optional |
| **(b)** | `.pt` emitted directly, no post-build rename | **CONFIRMED** |
| **(c)** | `kit-mode = path` — components resolved from an absolute path outside the project root | **CONFIRMED** for `maizzle build`; dev server moot by design |
| **(d)** | jbot override of a compiled `.pt` wins | **CONFIRMED WITH CAVEATS** — 11/11 tests pass against real Plone; two caveats are Phase 1 work |
| (e) | plaintext `.txt.pt` twin from the same build *(non-gating)* | **NOT REACHED** — deprioritised, see below |

**§9 exit criterion, clause by clause:**

> Inlined styles land correctly after `removeUnusedCSS`; Chameleon renders the output; jbot override wins

1. *Inlined styles land correctly after purge* — **yes**, 31 inline `style` attributes in `spike.pt`; `purge.diff` shows purge removes only unused CSS, comments and orphaned class references. **No placeholder or TAL attribute is touched by purge.**
2. *Chameleon renders the output* — **yes**, `spike/render.py` → 15/15 PASS, output at `spike/rendered/spike.fr.html`.
3. *jbot override wins* — **yes**, `11 passed` in `spike/plone/`, rendered evidence at
   `spike/rendered/mail_password.jbot.html`.

**Phase 0 did not fail. No §10 assumption failed.** Both §10 open questions resolved in the *favourable* direction. Three caveats under (a) are load-bearing and become Phase 1 work.

---

## (a) Maizzle output survives Chameleon — CONFIRMED WITH CAVEATS

`spike/maizzle/emails/spike.vue` carries every construct at once; `spike/render.py` renders the
compiled `.pt` through Zope's page-template machinery with `spike/fixture.py`.

```
=== build/spike.pt ===
  rendered -> rendered/spike.fr.html (11430 bytes)
  [PASS] no unresolved ${...} placeholders
  [PASS] no leftover tal:/i18n:/metal: attributes
  [PASS] tal:repeat produced one row per fixture item
  [PASS] ${...} in a text node substituted
  [PASS] ${...} in an href substituted
  [PASS] theme token via tal:attributes substituted
  [PASS] i18n:translate='' actually translated the msgid
  [PASS] i18n:translate + i18n:name interpolated the name
  [PASS] i18n:translate translated table headers
  [PASS] structure body_html injected unescaped
  [PASS] tal:condition kept the URGENT block
  [PASS] raw-escaped block repeated over extras
  [PASS] v-pre kept Vue braces literal
  [PASS] $${...} escaped to a literal ${...} for the inbox
  [PASS] inlined CSS survived into the render

ALL CHECKS PASSED
```

Confirmed to survive the build untouched: `${...}` in text nodes and in non-`class`,
non-`style` attributes; `tal:repeat` / `tal:condition` / `tal:attributes` / `tal:content`;
`i18n:translate` (with and without a msgid) and `i18n:name`; `structure`; `v-pre`; the
block-level raw escape. Vue never mistakes `tal:`-prefixed attributes for directives, and
`${...}` does not collide with Vue's `{{ }}`.

### Caveat A1 — a Chameleon placeholder in a `style` attribute silently destroys CSS inlining document-wide

**This contradicts SPEC §3 as written** and is the most consequential finding of the phase.
§3 specifies:

> Kit components emit these as `style="background-color: ${theme/primary_color}"` (Chameleon placeholder, literal in build output)

That does not work. Juice parses every `style` attribute as CSS, so the `{` opens a block:

- the closing `}` is eaten — `spike/build/theme-token-literal.pt` contains
  `style="background-color:${theme/primary_color"`, which at runtime is not even an
  expression, just broken literal text;
- **and CSS inlining stops for the entire document.** One such attribute anywhere took
  `spike.pt` from 31 inline styles down to 6. The build still reports success.

Measured, same source, only the token form changed:

| Theme-token form | Inline `style` attrs in `spike.pt` |
|---|---|
| `style="background-color: ${theme/primary_color}"` (§3 as written) | **6** — inlining dead |
| `tal:attributes="style string:background-color: ${theme/primary_color}"` | **31** — correct |

Evidence: `spike/build/theme-token-literal.pt` is a minimal template doing only this; both its
plain `<p>` elements keep their Tailwind classes with nothing inlined, though they inline fine
in isolation.

**The fix is already inside the spec's own idiom.** §3 rule 2 blesses exactly this construct:
"Conditional styling at runtime uses `tal:attributes="style ..."` with literal values." So only
§3's theme-token sentence needs amending; the rule it should have pointed at is two paragraphs
below it. Logged in `docs/DECISIONS.md`.

### Caveat A2 — compiled output must have authoring comments stripped

Chameleon **refuses to parse** `--` inside an HTML comment:

```
ParseError: The string '--' is not allowed in a comment.
 - Location:   (line 64: col 60)
 - Source:     ... never go in a `style` attribute -- see
```

An ordinary em-dash-style comment in a `.vue` source therefore makes the compiled `.pt`
unparseable at runtime, while the Maizzle build reports success — the failure surfaces only
when a real mail is sent. `css.purge` removes only *some* comments, and Maizzle 6 has no
comment-removal option.

Fix implemented and verified: `spike/maizzle/strip-comments.js`, wired through the
`afterTransform` hook. It preserves Outlook conditional comments (load-bearing markup,
recognised by `[if` / `[endif]`, including the downlevel-revealed form) and drops the rest.
Verified: 6 MSO conditionals kept, 0 authoring comments shipped.

### Caveat A3 — `i18n:domain` is required and the build emits none

The compiled output contained **zero** `i18n:domain` declarations, so every `i18n:translate`
rendered its msgid as an untranslated default — **indistinguishable from success**, since the
msgid text appears in the output either way. Only after declaring `i18n:domain="imio.emailkit"`
and registering a translation domain did the spike prove real substitution
(`email_intro_default` → `Vous avez recu une convocation.`).

Phase 1: the kit's `Main.vue` must emit `i18n:domain` on `<html>`. The kit owns that markup, so
this does not violate §3 rule 1 — consumers still never write `i18n:` on a kit component.

### Also established under (a)

- **Two independent escape layers.** `v-pre` stops the *Vue* compiler only; Chameleon still
  evaluates `${...}` inside a `v-pre` element at runtime. To reach the inbox literally, a
  placeholder needs Chameleon-level escaping (`$${...}`). Both verified.
- **The raw-escape component is matched by a naive global regex that also matches inside HTML
  comments.** Writing the component's name in angle brackets inside a comment swallowed the
  real block, deleting it from the output with no warning. Cost real debugging time here;
  it is a Phase 4 lint rule.
- **`i18n:translate=""` is normalised to a valueless `i18n:translate`.** Chameleon accepts it
  and translates correctly.
- **Build output is deterministic** — two consecutive builds are byte-identical. §5's staleness
  gate is therefore viable with `html.format: true`, which also keeps diffs line-granular.
- **§6.1's `render()` is pinned to Zope's page-template machinery, not bare Chameleon.**
  Standalone `chameleon.PageTemplateFile` has no TAL path expressions, so `${member/fullname}`
  raises `NameError: fullname`. This converges with the jbot constraint in (d): both point at
  `Products.PageTemplates.PageTemplateFile`. See the §4 correction in `docs/DECISIONS.md`.
- **The engine swap is silent when absent.** Without the `IPageTemplateEngine` utility
  (`Products.PageTemplates`, reached in Plone only via `plone.z3cform`), zope.pagetemplate
  falls back to zope.tal, where `${...}` passes through **verbatim with no error** while
  `tal:repeat` still works. Any test asserting only on markers would pass while shipping raw
  placeholders. Tests must assert on *substituted values*.

### Negative controls (non-gating) — both behaved as predicted

| Control | Prediction | Result |
|---|---|---|
| 1 — class referenced only from `tal:attributes` | purge removes the rule | **CONFIRMED**: `.spike-purge-victim` present in the purge-off build (`purge.diff`), absent from `spike.pt`. Its A/B twin `.spike-kept-class`, referenced from a real `class` attribute, survives. |
| 2 — `${...}` inside a `class` attribute | `css.safe` corrupts it | **CONFIRMED**: `class="text-sm ${item/css_class}"` → `class="text-sm -item-css_class"` (`$`→`-`, `{`/`}` stripped, `/`→`-`) |

Together these turn §3's authoring rules 2 into a documented failure mode with committed
evidence, and give §5's lint step its precise targets.

---

## (b) Output extension — CONFIRMED

`output: { extension: 'pt' }` emits `spike.pt` directly. No rename step, no `afterBuild` hook.
§10.2's assumed post-build rename is retired.

---

## (c) `kit-mode = path` — CONFIRMED for the path we use

`spike/kit-outside/` sits outside the Maizzle project root and is wired via
`components: { source: [{ path: <absolute>, prefix: 'Kit', pathPrefix: false }] }`. Both
`KitPanel` and `KitButton` resolve and render (`data-kit-marker` present in the output). §10.1's
`copy` fallback is not needed.

Two notes:

- **`prefix` is not cosmetic.** Maizzle ships a built-in `Button` component; an unprefixed kit
  `Button.vue` would shadow it. A namespace prefix (`Kit`) avoids the collision and is what the
  real kit should use. Maizzle *throws* on genuine two-source collisions rather than silently
  picking one.
- **Kit components must stay import-free**, as planned. Vite resolves `node_modules` by walking
  up from the importer, and a `site-packages` directory has no `node_modules` ancestor. Not hit,
  because the stubs rely on Maizzle's auto-imports.

**Dev server: moot by design, not verified.** `maizzle serve` starts cleanly (v6.0.7, port 3000)
but every route probed headlessly returned 404, so this is *inconclusive rather than negative* —
and it does not matter: §5 explicitly rejects Maizzle's watch loop ("build-time output only… a
miserable authoring loop") in favour of `bin/preview-emails`, which compiles, pipes through
`render()` with fixtures, and serves that. Our preview path never uses `maizzle serve`.

---

## (d) jbot override of a compiled `.pt` — CONFIRMED WITH CAVEATS

```
$ spike/.venv/bin/python -m pytest . -q -W ignore::DeprecationWarning
...........                                                              [100%]
11 passed in 18.68s
```

A real Maizzle 6 `.pt` — `spike/build/mail_password.pt`, copied byte-identically (`diff`-verified,
never hand-edited) to
`spike/plone/emailkit_spike/overrides/Products.CMFPlone.browser.login.templates.mail_password_template.pt`
— wins as a `z3c.jbot` override of the stock CMFPlone password-reset mail template on a dedicated
browser layer. Its inlined CSS, `${...}` placeholders, `i18n:translate` and MSO conditional
comments all survive compilation → jbot → Chameleon.

Positive evidence in `spike/rendered/mail_password.jbot.html`: `To: zoe.testeuse@example.be`,
`<html lang="fr"`, `href="http://nohost/plone/passwordreset/deadbeef…"`,
`Bonjour Zoe Testeuse, …`, `style="font-size: 16px; line-height: 24px; color: #374151;"`,
`max-width: 576px`, and `assert "${" not in rendered` passes. The engine guard confirms
`queryUtility(IPageTemplateEngine)` is `Products.PageTemplates.engine.Program` — Chameleon, not
the zope.tal fallback. Negative control: an unmarked request gets the stock CMFPlone file.

### Caveat D1 — `<include package="z3c.jbot" file="meta.zcml"/>` is a silent no-op

`meta.zcml` registers only the `browser:jbot` **directive**. The `ViewPageTemplateFile.__get__`
monkeypatches live in `z3c.jbot/configure.zcml` (`<include package="z3c.jbot.patches"/>`). With
`meta.zcml` alone the directive parses, the `TemplateManager` is built with the *correct* path
mapping, and **the stock template still renders** — no error, no warning. The correct include is
`<include package="z3c.jbot"/>`.

In a real instance `z3c.autoinclude` loads it, but `PLONE_FIXTURE` disables autoinclude. So
Phase 1 must not rely on autoinclude in its own test layer, and this class of mistake is
undetectable without a *positive render assertion* — asserting the override file was found is not
enough.

### Caveat D2 — placeholder names must match the hosting view's namespace

View kwargs land in `options`, not at top level: `Products/Five/browser/pagetemplatefile.py`
calls `pt_getContext(..., options=keywords)`. Calling the view exactly as `RegistrationTool` does
raises `KeyError('member')`, annotated by Chameleon with `Expression: "member/email"` — an
expression that exists only in our override, which is itself proof the override won *and* that
`${...}` was genuinely evaluated rather than passed through.

Worse, **`MemberData` is not path-traversable at all**: `${member/email}` raises `LocationError`
even when `member` is bound top-level. That is why the stock template uses
`python:member.getProperty('email')`.

This is a **template-authoring** constraint, not a Maizzle or jbot limitation. Phase 1 options:
a `tal:define` preamble emitted by the kit layout mapping `options/member` → `member`; a
kit-owned view class exposing flat names; or routing everything through §6.1's
`render(template, context)` with a flat context. Logged in `docs/DECISIONS.md`.

### Declared simplification

The `rendered` fixture does not call `view(member=…, reset=…, password=…, charset=…)`, because
that path raises per D2. It renders the *same jbot-resolved override file* inside the real Plone
site through the real engine, binding `member` as a flat mapping whose values are read off the
real fixture member. The `view(**kwargs)` path is still exercised — as
`test_stock_view_call_renders_the_override`, which pins the failure precisely rather than hiding
it.

### Corrections to earlier discovery

Two "established facts" from the discovery pass did not survive contact with a running test, and
are corrected above: `meta.zcml` alone is **not** sufficient (D1), and the Chameleon engine **is**
present under bare `PLONE_FIXTURE` with no extra `plone.z3cform` ZCML needed.

### Flagged for Phase 2, not tested

The override emits `Content-Type: text/html; charset=utf-8` where the stock template emits
`text/plain`, and `RegistrationTool` feeds the result through `message_from_string(...)` into
MailHost. Whether that alone produces a correct HTML mail, or whether
`multipart/alternative` requires the template to emit a raw MIME body with a boundary, is a
Phase 2 question.

---

## (d) — mechanism established by discovery

Discovery established the mechanism precisely (all paths inside `spike/.venv`):

- The stock mail templates are **`Products/CMFPlone/browser/login/templates/mail_password_template.pt`**
  and **`registered_notify_template.pt`**, both `<browser:page template=.../>` registrations.
  `Products.PasswordResetTool` no longer exists as a package — it is merged into CMFPlone.
  `plone.app.users` ships **no** mail template, so there is one registration mail, not two.
- `browser:page template=` becomes `Products.Five.browser.pagetemplatefile.ViewPageTemplateFile`,
  whose `__get__` **is** patched by jbot. Required override filenames are the dotted paths, e.g.
  `Products.CMFPlone.browser.login.templates.mail_password_template.pt`.
- **CMFPlone does not include jbot's `meta.zcml`** — it must be included explicitly.
- jbot does **not** patch `z3c.pt.pagetemplate.ViewPageTemplateFile` or raw
  `chameleon.PageTemplateFile` (both measured `patched_by_jbot=False`).

§8.1's assumption **holds**: these templates are jbot-overridable. The compiled artifact used as
the override is `spike/build/mail_password.pt` — real Maizzle output with inlined CSS, used
byte-for-byte with no hand editing.

Three consequences for later phases, logged in `docs/DECISIONS.md` rather than decided here:

1. **§8.2's "most specific layer wins" is only true for layers that *extend* `IEmailkitLayer`.**
   For sibling layers, precedence follows `ILocalBrowserLayerType` registration order, which is
   effectively arbitrary. The override story must say "your layer must extend `IEmailkitLayer`".
2. **Subjects are Python-side, not template-side.** `view/mail_password_subject` is a method on
   `PasswordResetToolView` translating a hardcoded `plone`-domain msgid. jbot swaps files only,
   so §8.1's "subjects re-registered as msgids in the `imio.emailkit` domain" needs a route —
   cheapest is the override template emitting its own `Subject:` header with an
   `imio.emailkit` msgid, which is legal because Plone parses the headers back out of the
   rendered text.
3. **§4's "z3c.jbot works on the resolved `.pt` files" is false as written** for our *own*
   templates, unless `render()` loads them through `Products.PageTemplates.PageTemplateFile`.
   Independently forced by the path-expression finding in (a).

---

## (e) Plaintext twin — NOT REACHED

Explicitly non-gating in the plan, and deprioritised once (a) surfaced three caveats worth more
attention. §4 already specifies a runtime fallback for a missing twin, so nothing downstream is
blocked. Carried into Phase 1 as an open item in `docs/DECISIONS.md`.

---

## What surprised us

1. **Failures in this pipeline are silent, not loud.** Every single one of A1, A2, A3 and the
   raw-block deletion produced a *successful build* and plausible-looking output. The
   theme-token bug even produced a page that renders in a browser. This is the strongest
   argument for §5's `check-emails` lint and §7's golden files: the build exit code carries
   almost no information about correctness.
2. ~~A partial `css:` config key does not deep-merge with Maizzle's defaults.~~
   **CORRECTED 2026-07-29 — this claim was wrong.** Maizzle merges config with `defu`, which deep-
   merges: `resolveConfig` on a config supplying only `css.purge` returns
   `{"inline":true,"purge":{…},"shorthand":true,"safe":true,"preferUnitless":true}`. The original
   claim was a hypothesis formed while chasing the dead-inlining symptom and was never tested
   directly; the sole cause of that symptom was caveat A1's placeholder-in-`style`. Recorded here
   rather than deleted, because the wrong diagnosis was committed and acted on.
   The *practical advice* — restate every `css` key in the kit's base config — still stands, but for
   a different reason: a consumer that **spreads** the base object (`{...base, css: {…}}`) shadows
   whole keys, since object spread is shallow. Every key must be restated.
3. **A top-level SFC `<style>` block never reaches the email** — standard Vue semantics: the
   bundler extracts it. Purge then strips the now-orphaned class from the `class` attribute too.
   Custom CSS must be a real `<style>` *element* inside `<template>`.
4. **Maizzle's Tailwind utilities carry `!important`**, so they beat custom CSS of equal
   specificity even when the custom rule comes later in source order.
5. **`<Preheader>` is already a built-in**, so §3's preheader slot needs no hand-rolling. Note
   its filler padding is computed at build time from the placeholder's *length*, so with a
   `${preheader}` placeholder the padding will be wrong at runtime — a Phase 1 detail.

## Cleanup

`spike/` stays committed as the evidence behind this report and is removed in a single `chore:`
commit once the real kit supersedes it in Phase 1. It is never imported by package code and
never ships in an sdist. `spike/.venv/` and `spike/maizzle/node_modules/` are gitignored.
