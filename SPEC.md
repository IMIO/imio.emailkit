# imio.emailkit — Specification

**Status:** Draft 4 — for review
**Date:** 2026-07-28
**Scope:** Transactional email templating and sending for the iMio Plone ecosystem, built on Maizzle 6.

**Changes since Draft 1:** the npm design-system package (`@imio/emailkit`) is deferred — the kit now lives inside `imio.emailkit` itself (§3). Restyled Plone default mails are promoted from an optional extra to a core deliverable, installed by default and overridable (§8). Phasing reordered accordingly (§9). Draft 3: attachments promoted from open question to v1 builder feature (§6.2). Draft 4: DX/UX additions — two-stage dev preview, scaffolding, authoring lint, Agent Skill, preheader, locale helpers, a11y defaults, send-test (§3, §4, §5, §6).

---

## 1. Goals & non-goals

### Goals

- Author HTML emails with a modern toolchain (Maizzle 6: Vue SFC + Tailwind CSS 4), compiled to email-safe HTML (inlined CSS, Outlook fallbacks, dark-mode handling).
- **Zero Node.js in production.** Node is a developer/CI tool only.
- **Better defaults out of the box:** installing `imio.emailkit` restyles Plone's stock transactional mails (password reset, registration) — while keeping them fully overridable.
- Any consumer addon can ship its own email templates, compiled against the shared design system.
- A small, expressive Python API for rendering and sending, replacing raw `MailHost.send` usage.
- First-class i18n (FR/NL/DE) at template and subject level.

### Non-goals

- TTW template markup editing. Templates are dev-owned, versioned in git.
- Intercepting/re-skinning arbitrary outgoing MIME (no MailHost monkey-patching).
- Mail scheduling, digests, retry policies, marketing campaigns. Out of scope; may be built *on top of* this package later.
- Third-party form mailers (easyform etc.). Documented as out of scope.
- Publishing the design system as a standalone npm package — deferred until a concrete consumer outside the buildout-managed ecosystem needs it (§3).

---

## 2. Architecture overview

Two-stage templating with a build-time / runtime seam:

```
┌─────────── dev machine / CI (Node) ───────────┐   ┌───────── production (Python only) ─────────┐
│                                                │   │                                             │
│  .vue templates ──► Maizzle 6 build ──► .pt ───┼──►│  Chameleon render(context) ──► HTML + txt   │
│  (built-in kit:     (Tailwind, inline    │     │   │        │                                    │
│   layouts,           CSS, purge)      committed│   │        ▼                                    │
│   components)                          to git  │   │  Email builder ──► IMailHost (queued)       │
└────────────────────────────────────────────────┘   └─────────────────────────────────────────────┘
```

- **Stage 1 (build, Node):** Maizzle compiles Vue SFC + Tailwind into email-safe HTML. Chameleon syntax (`${...}`, `tal:`, `i18n:`) passes through untouched (Vue owns `{{ }}`, no delimiter conflict). Output is renamed to `.pt` and committed.
- **Stage 2 (runtime, Python):** Chameleon renders the compiled `.pt` with real data. This gives `i18n:translate`, `tal:repeat`, `metal:` macros and `z3c.jbot` overrides for free.

### Artifacts

| Artifact | Ecosystem | Responsibility |
|---|---|---|
| `imio.emailkit` | PyPI / egg | Runtime (`Email` builder, `render()`, discovery), **built-in design kit** (Maizzle layouts/components/preset), restyled Plone default mails, content-rule action |
| `imio.recipe.emailkit` | PyPI / egg | Buildout recipe generating `bin/compile-emails` and `bin/check-emails` |

A future `@imio/emailkit` npm package is the extraction target for the kit if it ever needs to live outside this ecosystem; it is explicitly **not** built now.

---

## 3. Design system — built into `imio.emailkit` (npm packaging deferred)

The kit sources ship inside the Python package:

```
imio/emailkit/kit/
├── maizzle.config.base.js   # shared build config (transformers, output opts)
├── tailwind.preset.js       # email-safe preset (px units, no CSS vars, safelist)
├── layouts/
│   └── Main.vue             # single canonical shell (header, footer slot, dark mode)
└── components/
    ├── Button.vue
    ├── Panel.vue
    ├── DataTable.vue
    └── ...
```

**Why in the egg, not on npm:** one artifact, one version pin. The buildout already pins `imio.emailkit`; that same pin governs the design system every consumer compiles against. No npm registry, no git-tag npm dependencies, no version skew between runtime and kit.

**How consumers reach it:** `bin/compile-emails` (§5) resolves the kit directory from the installed `imio.emailkit` egg and wires it into each consumer's Maizzle build — either by pointing the Maizzle components/layouts paths at the egg directory directly, or by materializing a copy into the consumer's `emails/.kit/` (gitignored) before building. The recipe owns this choice; consumers never vendor kit files.

**Extraction trigger** (revisit then, not before): a project outside buildout-managed deployments needs the kit, or kit release cadence diverges from `imio.emailkit` releases. Extraction is mechanical — the same files move to an npm package and the recipe's wiring step becomes an `npm i`.

### Theming model (v1: locked)

The design system is **locked**: consumers compose layout + components but do not extend the Tailwind config. Rationale: visual coherence across all iMio products, drastically simpler maintenance.

Runtime-variable branding is limited to an explicit set of **theme tokens** rendered as literal inline styles by kit components:

| Token | Registry record | Used by |
|---|---|---|
| `logo_url` | `imio.emailkit.theme.logo_url` | `Main.vue` header |
| `primary_color` | `imio.emailkit.theme.primary_color` | `Button`, header rule |
| `footer_html` | `imio.emailkit.theme.footer_html` | `Main.vue` footer |

Kit components emit these as `style="background-color: ${theme/primary_color}"` (Chameleon placeholder, literal in build output). Everything else is Tailwind, fixed at build time.

### Baked into the kit (the kit does it, not authors)

- **Accessibility defaults:** `role="presentation"` on all layout tables, enforced `alt` on the logo/`Img` component (lint fails without it), real text instead of image-text. RGAA applies to iMio's clients — doing this in the kit means nobody has to think about it again.
- **`lang` attribute:** the layout emits `lang="${lang}"` on `<html>` from the render context. Screen readers pick pronunciation from it; free.
- **Preheader slot:** the layout renders the standard hidden `<div>` from the optional `preheader` msgid in the template registration (§4).

### Authoring rules (enforced by the lint step in `bin/check-emails`, §5)

1. **No `tal:`/`i18n:` attributes on kit components** — attribute fallthrough lands them on unpredictable root elements. Dynamic regions (`tal:repeat` rows, conditionals) are authored as plain `<tr>`/`<td>` markup; kit components are used only inside static structure or inside a controlled row.
2. **No runtime-computed `class` values.** Tailwind purge and `removeUnusedCSS` only see build-time markup. Conditional styling at runtime uses `tal:attributes="style ..."` with literal values.
3. Chameleon placeholders that must survive the Vue compiler are wrapped in `v-pre` or emitted as literal strings.
4. `${...}` values are HTML-escaped by Chameleon by default; `structure` is reserved for the shell's `body_html` slot and `footer_html`, nothing else.

### Agent Skill

Maizzle 6 ships an official Agent Skill so AI assistants stop generating Outlook-broken markup. `imio.emailkit` ships an `emailkit` `SKILL.md` alongside it covering *this* layer: the authoring rules above, the `${}`/`tal:` conventions, the fixture/golden workflow, and the kit component catalog. Template work at iMio is largely AI-assisted; this is disproportionately cheap leverage.

---

## 4. Template distribution & discovery

### Consumer addon layout

```
src/imio/pm/notifications/
├── emails/                      # Maizzle project — dev-only, excluded from sdist
│   ├── package.json
│   ├── maizzle.config.js        # extends the kit base config (wired by bin/compile-emails)
│   ├── .kit/                    # gitignored, materialized by the recipe if copy mode is used
│   └── src/templates/
│       ├── item_published.vue
│       └── meeting_convocation.vue
├── templates/                   # ✅ committed build output
│   ├── item_published.pt
│   ├── item_published.txt.pt    # plaintext twin (placeholders intact)
│   ├── meeting_convocation.pt
│   └── meeting_convocation.txt.pt
└── ...
```

`MANIFEST.in`: `recursive-include ... templates *.pt`, `prune ... emails`.

### Registration: ZCML directive

Consumers declare their templates with the `<emailkit:templates>` directive, in
their own `configure.zcml`:

```xml
<!-- imio/pm/notifications/configure.zcml -->
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="imio.pm.notifications"
    >

  <include package="imio.emailkit" file="meta.zcml" />

  <emailkit:templates directory="templates">
    <emailkit:template
        name="item_published"
        subject="[email_subject_item_published] An item was published"
        preheader="[email_preheader_item_published] ..."
        />
    <emailkit:template
        name="meeting_convocation"
        subject="[email_subject_meeting_convocation] Convocation"
        />
  </emailkit:templates>

</configure>
```

- Template names are namespaced at lookup: `imio.pm.notifications:item_published`.
  The package half of the name is **derived from the ZCML file's own package** —
  the consumer never spells it out, so it cannot disagree with reality.
- **`subject` and `preheader` are `MessageID`s** in the enclosing `i18n_domain`,
  written `[msgid] Default text` to pick the msgid explicitly — the default is
  what reaches the inbox until a catalog translates it. The subject **lives in
  the registration**, translated per recipient language at send time; no
  metadata sidecar, no front-matter round-trip. `preheader` stays optional — the
  hidden inbox-preview line next to the subject, rendered into the layout's
  hidden `<div>` (§3), the highest-visibility email feature that everyone
  forgets. Omitted → the div collapses to nothing.
- **One `<emailkit:templates>` block per package.** It is a `zope.configuration`
  grouping directive, so every template a package ships is declared inside a
  single block; a second block in the same package conflicts with the first —
  deliberate, since both would try to answer "where does this package's
  compiled output land" and there can only be one answer.
- **Duplicate template name → `ConfigurationConflictError`** at startup, not a
  silent overwrite — the same mechanism every other Zope registration gets.
- `directory` may point outside the package's own directory via relative
  traversal (`../templates`, say, for a subpackage sharing its parent's
  compiled output); an absolute path is refused.
- **`overrides.zcml` replaces a registration** the same way it replaces any
  other ZCML-registered component — no bespoke override plumbing.
- **i18n caveat:** `i18ndude` extracts msgids from `.py` and `.pt`, never from
  ZCML, so a `subject`/`preheader` msgid that lives only in `configure.zcml`
  would silently drop out of the `.pot` on a locales rebuild. Consumers that
  want automated extraction restate the same msgids in a small Python module
  (e.g. `msgids.py`) that does nothing but call the message factory on each one
  — exactly what `imio.emailkit` does for its own templates (see
  `src/imio/emailkit/msgids.py`).
- **Overrides (markup):** `z3c.jbot` works on the resolved `.pt` files (per-site
  or per-client overlays), no additional mechanism.

Failure modes are otherwise unchanged: unknown template name → `TemplateNotFound(name, available=[...])`; missing `.txt.pt` twin → warning at startup, `render()` falls back to a naive text extraction with a logged deprecation; missing `.pt` → warning at startup, the template is skipped.

---

## 5. `imio.recipe.emailkit` — buildout recipe

### Usage

```ini
[buildout]
parts = ... emails

[emails]
recipe = imio.recipe.emailkit
eggs = ${instance:eggs}
# compile-on-install = false   (default)
# kit-mode = path | copy       (default: path — point Maizzle at the egg's kit dir)
# node-bin = node              (resolution: PATH by default)
```

### Behavior

The recipe **does not compile during buildout** by default. It:

1. Resolves all eggs, collects the packages whose ZCML mentions the emailkit namespace — a filesystem marker scan at install time; buildout imports nothing — and records `(package, emails_dir, templates_dir)` tuples. It also resolves the kit directory from the `imio.emailkit` egg. The generated scripts re-resolve at run time by *executing* each candidate's ZCML through a permissive configuration machine (only the emailkit directives are live; unknown directives are swallowed unimported), so `directory`, includes, conditions and `overrides.zcml` behave exactly as at instance startup. Known divergence: feature-flag conditions (`have x`) read false at build time, since nothing loads the ZCML that would provide the feature.
2. Generates three scripts:

**`bin/compile-emails [--package NAME] [--watch] [--new NAME]`**
For each discovered package (or the one selected): wire the kit (per `kit-mode`) → `npm ci` in `emails/` (only if `node_modules` is stale vs. lockfile) → `npx maizzle build production` → rename output `*.html` → `*.pt` → move into `templates/`. Exit non-zero on any build failure. `--watch` delegates to Maizzle's dev server (build-time output only; see `preview-emails` for the real loop). `--new NAME` scaffolds the four files a template needs — a minimal `.vue` skeleton, a fixture, a golden placeholder, and a registration stub to paste. Templates have a rigid shape; making the right structure the path of least resistance beats documenting it.

**`bin/check-emails [--package NAME]`**
Two gates in one script. (1) *Staleness:* compile each package into a tmpdir and `diff` against the committed `templates/`; exit 1 with a per-file diff summary if stale. (2) *Authoring lint:* plain-regex checks (~30 lines) of the `.vue` sources for the §3 rules — `tal:`/`i18n:` attributes on kit components, runtime-computed `class` values, missing `alt` on `Img`. These are exactly the bugs that pass the build and fail silently in production (styles purged, attributes landing on the wrong element). **This is the CI gate** — every consumer addon (including `imio.emailkit` itself) runs it in its pipeline.

**`bin/preview-emails [--package NAME]`**
The two-stage dev loop — the flagship DX feature. Maizzle's own `--watch` shows *build-time* output: raw `${item/title}` placeholders and unexpanded `tal:repeat` — a miserable authoring loop. This script watches the `.vue` sources, compiles, pipes the result through Chameleon (`render()`) **with the committed fixtures (§7)**, and serves the result with live reload and a language switcher. ~50 lines of glue over pieces that already exist (compile step, `render()`, fixtures); turns authoring from "compile, deploy, trigger a mail" into "save, look at browser".

3. If `compile-on-install = true`, runs `bin/compile-emails` as an install step (opt-in, for environments that accept Node at deploy time; never the default).

### Explicitly rejected

Compiling at buildout time by default — it would make Node a production dependency across ~350 applications and couple deployments to npm availability.

---

## 6. `imio.emailkit` — runtime API

### 6.1 `render()`

```python
from imio.emailkit import render

html, text = render(
    "imio.pm.notifications:item_published",
    context={"item": item, "meeting": meeting},
    language="fr",              # optional; defaults to negotiated language
)
```

- Renders `.pt` and `.txt.pt` through Chameleon with `context` + injected `theme/*` tokens (from `plone.app.registry`) + standard helpers (`portal_url`, `translate`) + **locale-aware formatting helpers** — `format_date`, `format_datetime`, `format_number` — bound to the render language, so no template ever reinvents French date formatting (half would get it wrong). The render language is also exposed as `lang`, which the layout emits on `<html>` (§3).
- Pure function of (template, context, registry state) — used directly by previews and tests.

### 6.2 `Email` builder

```python
from imio.emailkit import Email

Email("imio.pm.notifications:item_published") \
    .to(member) \
    .to("greffe@commune.be") \
    .cc(meeting_managers) \
    .reply_to("noreply@imio.be") \
    .with_context(item=item, meeting=meeting) \
    .attach(convocation_pdf, filename="convocation.pdf") \
    .send()
```

**Semantics:**

- The builder is a plain data holder; each method returns `self`. **It holds data, it does not grow behavior** — no conditionals, no scheduling, no retries.
- `.to() / .cc() / .bcc()` accept, in any mix: an email string, a Plone member object, a userid, or an iterable of those. Resolution goes through a single adapter:

  ```python
  class IEmailRecipient(Interface):
      email = Attribute("address")
      fullname = Attribute("display name, may be empty")
      language = Attribute("preferred language code, may be None")
  ```

  Default adapters ship for `str` and Plone members. Unresolvable recipients raise `RecipientError` at `.send()` time (fail loud, not silent drop).
- **Per-language sending:** `.send()` groups recipients by resolved language, renders once per language group (subject msgid translated accordingly), and emits one message per group. FR/NL communes are handled with no caller effort.
- **Subject** comes from the template registration; `.subject(...)` exists as an override for edge cases and accepts a msgid or literal string.
- **Attachments:** `.attach(source, filename=None, mimetype=None)`, callable multiple times. `source` accepts, in the same polymorphic spirit as recipients: raw `bytes`, a filesystem path (`str`/`Path`), an open binary file object, a `NamedBlobFile`/`NamedFile` value, or a Plone File/Image content object. `filename` and `mimetype` are inferred where the source carries them (blob values, content objects, paths — via `mimetypes.guess_type`) and required for `bytes`; missing/unguessable metadata raises `AttachmentError` at `.send()` time, consistent with `RecipientError` (fail loud, not silent drop). Assembly goes through `EmailMessage.add_attachment` — attachments ride the same message, identical across language groups.
- Message assembly: `email.message.EmailMessage`, `set_content(text)` + `add_alternative(html, subtype="html")`, correct headers and encoding. Nothing hand-built by callers, ever.
- **Transaction safety by default:** delivery via `IMailHost` queued send — an aborted transaction sends nothing. `.send(immediate=True)` is the escape hatch.
- `From` defaults to the site's configured sender; `.sender(...)` overrides.

### 6.3 Preview view

`@@emailkit-preview` (Manager-only): lists all registered templates, renders each in an iframe using **committed fixture data** (see §7), with a language switcher and a theme-token panel. A **Send test** button mails the currently previewed template + fixture + language to the logged-in user's own address — browser previews lie, Outlook doesn't; this closes the loop with real clients for the cost of one form. ~1 view, disproportionate developer value.

---

## 7. Testing

### Golden files (per consumer addon)

Each template ships a fixture and a snapshot:

```
tests/
├── fixtures/item_published.py      # dict of context data
└── golden/
    ├── item_published.fr.html
    └── item_published.fr.txt
```

A provided test base class renders each registered template against its fixture and diffs against the golden file. Catches the two real regressions: a Tailwind class silently purged at build, and a `${}` placeholder that stopped resolving after a refactor. `bin/test --update-golden` regenerates snapshots deliberately.

### CI contract for every consumer addon

1. `bin/check-emails --package <self>` — build output is not stale.
2. Golden-file tests — runtime rendering is intact.

### In `imio.emailkit` itself

- Discovery tests with two dummy addons (also serving as living documentation).
- Golden files + `check-emails` for its own templates (Plone default mails, shell) — dogfooding the full contract.
- Recipient-resolution adapter tests (str, member, userid, mixed iterables, failures).
- Attachment-source tests (bytes, path, file object, blob value, content object; filename/mimetype inference; `AttachmentError` cases).
- Language-grouping tests for `.send()`.
- Transaction abort test: `.send()` + abort → MailHost queue empty.

---

## 8. Plone default mails — better defaults, still overridable

**Core deliverable:** installing `imio.emailkit`'s default profile immediately restyles Plone's stock transactional mails. No extra package, no opt-in step. This is the package's first visible value and its own dogfooding vehicle — these templates are authored, compiled, discovered, tested and shipped exactly like consumer templates.

### 8.1 Mechanism

- `imio.emailkit` ships compiled kit-based replacements for three CMFPlone mails: **password reset**, **user registration/enrolment** and the **username reminder** from the login-help form.
- The first two are page templates on disk and are replaced as `z3c.jbot` overrides. The **username reminder is not**: stock Plone sends it as a hardcoded plaintext string (`SEND_USERNAME_TEMPLATE` in `Products/CMFPlone/browser/login/login_help.py`), so there is no file for jbot to key on and the **`login-help` view is overridden instead**. Consequence, and it is a gain rather than a compromise: because that view is ours, the template speaks §3's flat dialect, renders through §6.1 `render()` and is genuinely discovered, previewable and golden-tested — the one restyled default mail for which §8's "exactly like consumer templates" is true of *every* verb.
- The jbot directory **and the `login-help` view registration** are bound **to a dedicated browser layer** (`IEmailkitLayer`) installed by the `imio.emailkit:default` GenericSetup profile.
- Subjects are re-registered as i18n msgids in the `imio.emailkit` domain (FR/NL/DE shipped).

### 8.2 Override story (three levels, most common first)

1. **Replace the template markup per site/client:** register a jbot directory on a *more specific* browser layer (the site package's own layer). z3c.jbot layer precedence applies — the most specific layer wins. This is the standard iMio pattern already used elsewhere; no new mechanism. (The username reminder's *markup* is overridable this way like any other template; what is layer-bound rather than jbot-bound is the `login-help` **view** that sends it.)
2. **Adjust branding only:** theme tokens (`logo_url`, `primary_color`, `footer_html`) via `plone.app.registry` — covers the majority of per-commune needs without touching markup.
3. **Opt out entirely:** install the `imio.emailkit:base` profile instead of `:default`. `:base` provides the runtime (API, discovery, kit) without the Plone-default overrides; stock Plone mails remain untouched. `:default` extends `:base`.

### 8.3 Also in scope

- **Content rules:** a new action type *"Send styled email"* — edit form offers the registered template names (vocabulary from discovery) + recipient sources; executor delegates to `Email(...)`. The stock mail action is left untouched.

### 8.4 Explicitly rejected

- MailHost monkey-patching to re-skin arbitrary outgoing MIME (breaks on the first calendar invite or signed message; undebuggable).
- Third-party form mailers (easyform etc.): out of scope, documented.

---

## 9. Phasing

Deferring the npm kit simplifies the critical path: `imio.emailkit` is its own first consumer, so consumer-distribution mechanics move *after* the first production value ships.

| Phase | Deliverable | Exit criterion |
|---|---|---|
| **0 — Spike** | Maizzle 6 → `.pt` pipeline on one template; `tal:repeat` + `${}` inside a compiled table row; jbot override of the compiled output | Inlined styles land correctly after `removeUnusedCSS`; Chameleon renders the output; jbot override wins |
| **1 — Better defaults** | `render()` + locale helpers, built-in kit (`Main.vue` + core components + tokens; a11y defaults, `lang`, preheader slot), restyled password-reset & registration mails, `:base`/`:default` profiles | Installed on one production site; stock mails restyled; opt-out and layer-override both verified |
| **2 — API** | `Email` builder, recipient adapters, attachments, per-language send, preview view + send-test | First real notification sent through the builder end-to-end |
| **3 — Shell for existing mails** | `render_shell(subject, body_html)`; existing PloneMeeting notification bodies dropped into the slot | All PloneMeeting notifications sent styled, zero template redesign |
| **4 — Consumer mechanics** | `imio.recipe.emailkit` (kit wiring, `compile-emails` + `--new` scaffolding, `check-emails` + authoring lint, `preview-emails`), ZCML-directive discovery for external addons, golden-test base class, `emailkit` Agent Skill | One pilot consumer addon green in CI, including staleness and lint gates |
| **5 — Adoption** | Content-rule action; migrate remaining notifications to purpose-built templates; second consumer addon | Two independent addons shipping templates |

Phase 0 remains the load-bearing one, but it shrank: the Maizzle-output-vs-Chameleon interaction is now the only unvalidated assumption on the critical path (discovery/recipe validation moved to Phase 4).

One sequencing note: the two-stage preview loop is needed from Phase 1 — `imio.emailkit` authors its own templates long before the recipe exists. A package-local Makefile precursor (same steps, hardcoded paths) covers Phases 1–3; `bin/preview-emails` in Phase 4 is that Makefile generalized, not new invention.

## 10. Open questions

1. **Kit wiring mode** (`path` vs `copy`, §5): pointing Maizzle at the egg's kit directory is zero-copy but assumes Maizzle/Vite resolves components outside the project root cleanly; verify in Phase 0, fall back to `copy` if not.
2. **Maizzle 6 output extension:** confirm whether the Vite pipeline allows configuring output extension to `.pt` directly, or whether the compile script renames post-build (either is fine; rename is the assumed default).
3. **Theming:** locked kit vs. composable preset — revisit only if deliberations.be and iA.Délib turn out to need genuinely different shells; a second layout in the kit is the cheap first answer.
4. **`collective.emailkit` split & npm extraction:** deferred until a consumer outside the iMio buildout ecosystem exists. Check PyPI availability for `imio.emailkit`, `imio.recipe.emailkit`, `collective.emailkit` now regardless.
5. **Inline `cid:` images:** not in v1 — the theme logo and any imagery are remote URLs. Revisit only if a client environment blocks remote images as policy; `.attach(..., inline=True)` + `cid` generation is the natural extension point.
