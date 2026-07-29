# Decision log — `imio.emailkit`

Every choice `SPEC.md` leaves open, and every deviation considered, is recorded here:
context, options, choice, why. A decision that would contradict the spec is not recorded
here — it is escalated to the maintainer first.

Newest entries at the top.

---

## 2026-07-29 — jbot wiring: include the whole `z3c.jbot` package, never just `meta.zcml`

**Context.** §8.1 registers the jbot directory on `IEmailkitLayer`. How jbot itself is loaded is
not specified.

**Finding.** `<include package="z3c.jbot" file="meta.zcml"/>` registers only the `browser:jbot`
*directive*. The `ViewPageTemplateFile.__get__` monkeypatches live in `z3c.jbot/configure.zcml`.
With `meta.zcml` alone, the directive parses, the `TemplateManager` is built with the correct path
mapping, and **the stock template still renders — silently**. No error, no warning.

**Choice.** `<include package="z3c.jbot"/>`. In a real instance `z3c.autoinclude` handles it, but
`PLONE_FIXTURE` disables autoinclude, so the test layer must include it explicitly and must not
rely on autoinclude.

**Why it matters beyond the one line.** This failure mode is invisible to any test that asserts
only "the override file was resolved". Every jbot test in this project must assert on **rendered
output** — a positive assertion that our markup appears and the stock markup does not. Recorded
because it nearly produced a green test for the wrong reason.

---

## 2026-07-29 — OPEN: how kit templates reach data when hosted by a stock Plone view

**Context.** §8 has our compiled templates replace stock Plone mail templates via jbot. §6.1 has
`render(template, context)` for our own templates. The two paths have different namespaces and the
spec does not reconcile them.

**Finding.** A jbot override is rendered *by the stock view*, and view kwargs land in `options`,
not at top level (`Products/Five/browser/pagetemplatefile.py` → `pt_getContext(..., options=keywords)`).
So `${member/fullname}`, `${reset_url}` and `${lang}` do not resolve against
`PasswordResetToolView`. Additionally **`MemberData` is not path-traversable at all** —
`${member/email}` raises `LocationError` even bound top-level, which is why the stock template
uses `python:member.getProperty('email')`.

**Options.**

- **A — the kit layout emits a `tal:define` preamble** mapping `options/member` → `member`, etc.,
  so authored templates always see flat names regardless of who renders them.
- **B — a kit-owned view class** registered on `IEmailkitLayer` exposing flat, traversable names,
  with jbot overriding only the template.
- **C — accept two dialects**: `options/…` + `python:` expressions for Plone-default overrides,
  flat names for our own templates via `render()`.

**Status.** Open, decided in Phase 1 when `Main.vue` and `render()` are both being written — they
are the two ends of this seam. Leaning A, because it keeps one authoring dialect (§3's whole
premise is that authors learn one set of rules) and puts the adaptation in kit-owned markup where
§3 already puts `lang`, `role="presentation"` and `i18n:domain`. C is explicitly the fallback, not
the goal.

**Why not decided now.** This is a template-authoring constraint, not a pipeline defect, and
choosing well needs the real `Main.vue` in front of us. Phase 0's job was to prove it is a
constraint at all.

---

## 2026-07-29 — §3 AMENDMENT: theme tokens use `tal:attributes`, not a literal `style` attribute

**Context.** §3 specifies that kit components emit theme tokens as
`style="background-color: ${theme/primary_color}"` — "Chameleon placeholder, literal in build
output". Phase 0 proves this does not work.

**Finding.** Juice parses every `style` attribute as CSS, so the `{` opens a block. Two effects,
both silent (the build reports success):

1. the closing `}` is eaten — output is `style="background-color:${theme/primary_color"`, which
   at runtime is not an expression at all, just broken literal text;
2. **CSS inlining stops for the entire document.** One such attribute anywhere took the spike
   template from 31 inline styles to 6.

Measured on identical source, changing only the token form:

| Form | Inline `style` attrs |
|---|---|
| `style="background-color: ${theme/primary_color}"` (§3 as written) | 6 — inlining dead |
| `tal:attributes="style string:background-color: ${theme/primary_color}"` | 31 — correct |

Evidence: `spike/build/theme-token-literal.pt`.

**Choice.** Kit components emit theme tokens via
`tal:attributes="style string:<prop>: ${theme/<token>}"`.

**Why this is not really a deviation.** §3 rule 2, two paragraphs below the sentence being
amended, already blesses exactly this construct: "Conditional styling at runtime uses
`tal:attributes="style ..."` with literal values." The spec's own idiom was already correct; only
the theme-token sentence pointed at the wrong mechanism. The three tokens, the registry records
and the locked-kit model are all unchanged.

**Consequence.** §3's rule 2 is upgraded from cautious advice to a hard constraint, and it now
covers `style` as well as `class`: **no Chameleon placeholder may appear in a literal `style` or
`class` attribute, ever.** Both are `bin/check-emails` lint rules (§5).

---

## 2026-07-29 — Compiled output must have authoring comments stripped

**Context.** Not addressed by the spec.

**Finding.** Chameleon refuses to parse `--` inside an HTML comment
(`ParseError: The string '--' is not allowed in a comment`). An ordinary em-dash-style comment in
a `.vue` source therefore makes the compiled `.pt` unparseable **at runtime**, while the build
reports success. `css.purge` strips only some comments; Maizzle 6 has no comment-removal option.

**Choice.** Strip authoring comments in an `afterTransform` hook, preserving Outlook conditional
comments (load-bearing markup, recognised by `[if` / `[endif]`, including the downlevel-revealed
form). Reference implementation: `spike/maizzle/strip-comments.js`. Moves into the kit's shared
base config in Phase 1.

**Why.** Authoring commentary should not ship in a transactional email regardless; stripping is
the right default and it makes the `--` hazard structurally impossible rather than a lint rule
authors must remember.

---

## 2026-07-29 — `Main.vue` must emit `i18n:domain`

**Context.** §4/§8.1 assume `i18n:translate` translates. Phase 0 found the compiled output
contained **zero** `i18n:domain` declarations.

**Finding.** Without a domain, every `i18n:translate` renders its msgid as an untranslated
default — **indistinguishable from success**, because the msgid text appears in the output either
way. Only after declaring `i18n:domain="imio.emailkit"` did substitution actually occur.

**Choice.** The kit's `Main.vue` emits `i18n:domain="imio.emailkit"` on `<html>`.

**Why there.** The kit owns that markup, so §3 rule 1 (no `tal:`/`i18n:` on kit components from
*consumers*) is untouched, and no author has to remember it — same reasoning §3 already applies
to `lang` and `role="presentation"`.

---

## 2026-07-29 — §6.1 `render()` uses `Products.PageTemplates.PageTemplateFile`; §4's jbot claim corrected

**Context.** §4 states "z3c.jbot works on the resolved `.pt` files (per-site or per-client
overlays), no additional mechanism". §6.1 describes rendering "through Chameleon".

**Finding — two independent constraints converge on the same class.**

1. **Path expressions.** Standalone `chameleon.PageTemplateFile` has no TAL path expressions:
   `${member/fullname}` raises `NameError: fullname`. Plone-idiomatic `/` paths need Zope's
   engine.
2. **jbot reach.** z3c.jbot 3.1 patches `Products.PageTemplates.PageTemplateFile`,
   `Products.Five...ViewPageTemplateFile`, `zope.pagetemplate`/`zope.browserpage` template
   classes, and CMF skins objects. It does **not** patch `z3c.pt.pagetemplate.ViewPageTemplateFile`
   or raw `chameleon.PageTemplateFile` (both measured `patched_by_jbot=False`).

**Choice.** `render()` loads templates via `Products.PageTemplates.PageTemplateFile`.

**Why.** It is the only option that gives both TAL path expressions and jbot overridability. §4's
claim is true *only* under this choice — as written it would be false if `render()` used bare
Chameleon, which the phrase "through Chameleon" invites. Recorded as a spec clarification.

**Related trap.** The Chameleon engine is a runtime `IPageTemplateEngine` utility registered by
`Products.PageTemplates`' ZCML, reached in Plone only via `plone.z3cform`. Without it,
zope.pagetemplate falls back to zope.tal, where `${...}` passes through **verbatim with no
error** while `tal:repeat` still works. Therefore: tests must assert on *substituted values*,
never on marker strings alone, or a green test can coexist with raw `${}` shipping to production.

---

## 2026-07-29 — §8.2 override story requires extending `IEmailkitLayer`

**Context.** §8.2 level 1 says "register a jbot directory on a *more specific* browser layer…
z3c.jbot layer precedence applies — the most specific layer wins."

**Finding.** True only for a layer that **subclasses** `IEmailkitLayer`. Measured against the
request's `__sro__`: for a child layer, `IEmailkitLayer` ordering is stable regardless of
declaration order; for a **sibling** layer, precedence follows declaration order, which comes
from `getAllUtilitiesRegisteredFor(ILocalBrowserLayerType)` and is effectively arbitrary.
Additionally, multiple jbot directories on the *same* layer sort by directory-path string.

**Choice.** Document §8.2 level 1 as "your site layer must **extend** `IEmailkitLayer`", and say
so in the override docs rather than leaving "more specific" to interpretation.

**Why.** It is the difference between a documented guarantee and a coin flip that happens to work
on the developer's machine.

---

## 2026-07-29 — Plone default-mail subjects: the override template emits its own `Subject:` header

**Context.** §8.1 says subjects are "re-registered as i18n msgids in the `imio.emailkit` domain".

**Finding.** The stock subjects are **Python-side**: `view/mail_password_subject` and
`view/registered_notify_subject` are methods on `PasswordResetToolView` that translate hardcoded
`plone`-domain msgids. z3c.jbot swaps template *files* only, so it cannot reach them.

**Options.** (A) the override template emits its own `Subject:` line with an `imio.emailkit`
msgid; (B) override the view class as well, via an adapter/ZCML registration.

**Choice.** **A.** Plone parses the mail headers back out of the rendered template text
(`message_from_string(mail_text)` in `RegistrationTool`), so a template-emitted `Subject:` is
already the supported path and needs no new mechanism.

**Why.** KISS, and it keeps the whole override inside the one artifact jbot already governs — no
second registration to keep in sync, per §8's "no new mechanism" preference.

---

## 2026-07-29 — Maizzle config gotchas worth encoding in the shared base config

**Context.** Phase 0 lost real time to two silent misconfigurations. Recorded so the kit's
`maizzle.config.base.js` (§3) encodes them once.

**Findings.**

- **A partial `css:` key does not deep-merge with the defaults.** Supplying only `css.purge`
  silently drops `inline`, `shorthand`, `safe` and `preferUnitless` — the build succeeds and
  nothing is inlined. Every key must be restated. This initially masqueraded as "inlining is
  broken in Maizzle 6".
- **A top-level SFC `<style>` block never reaches the email** (standard Vue semantics — the
  bundler extracts it). Purge then strips the now-orphaned class from the `class` attribute too.
  Custom CSS must be a real `<style>` **element** inside `<template>`, or live in the kit's CSS
  entry.
- **Maizzle's Tailwind utilities carry `!important`**, so they beat custom CSS of equal
  specificity even when the custom rule comes later.
- **Kit components need a namespace `prefix`.** Maizzle ships a built-in `Button`; an unprefixed
  kit `Button.vue` shadows it. Maizzle throws on genuine two-source collisions rather than
  silently choosing.
- **Kit components must stay import-free.** Vite resolves `node_modules` by walking up from the
  importer, and a `site-packages` directory has no `node_modules` ancestor. Maizzle's
  auto-imports make this free.
- **The raw-escape component is extracted by a naive global regex that also matches inside HTML
  comments.** Mentioning it in angle brackets in a comment swallows the real block and deletes it
  from the output silently. Phase 4 lint rule.
- **Build output is deterministic** (two builds byte-identical) with `html.format: true`, so §5's
  staleness gate works and diffs stay line-granular.

---

## 2026-07-29 — OPEN: plaintext `.txt.pt` twin not yet settled

**Context.** Carried from the pre-Phase-0 entry below. Phase 0 marked assumption (e) non-gating
and did not reach it, once (a) surfaced three caveats worth more attention.

**Status.** Still open, still unblocking: §4 already specifies the runtime fallback ("missing
`.txt.pt` twin → warning at startup, `render()` falls back to a naive text extraction"). Decide in
Phase 1 alongside `render()`, which is where the `(html, text)` tuple is actually built.

---

## 2026-07-29 — GAP / needs approval: development tooling is `uv` + `mxdev`, not buildout

**Context.** `SPEC.md` is silent on how *this repository* is developed and tested. It only
addresses **deployment**: §5 specifies a buildout recipe and rejects buildout-time compilation
because "it would make Node a production dependency across ~350 applications". §7 mentions
`bin/test --update-golden`, which reads as buildout-generated.

**Finding.** `imio.reportproblem` — the reference iMio Plone 6 addon — is a **Cookieplone**
package with no buildout at all: `uv` + `mxdev` + a `Makefile` for dev, constraints from
`dist.plone.org`, `pytest` + `pytest-plone` for tests, `ruff` for lint, `towncrier` for the
changelog, and CI on `plone/meta@2.x` reusable workflows. It carries a deliberate `setup.py`
shim whose docstring explains it exists precisely so the package can still be a `zc.buildout`
develop egg when iMio buildouts check it out into `src/`.

**Reading.** These are not in conflict, they are two layers: **development and CI use
uv + mxdev; deployment uses buildout.** The `setup.py` shim is the seam. This also means §9's
"package-local Makefile precursor" for the preview loop is the *house convention*, not a
stopgap — and §5's recipe serves deployment buildouts, which is where Node must not intrude.

**Options.**

- **A — follow the house convention:** Cookieplone layout, `uv` + `mxdev` + `Makefile` for
  dev/CI, `setup.py` shim for buildout develop-egg compatibility. Consistent with the
  maintainer's own most recent addon.
- **B — buildout for development too**, matching the spec's literal `bin/test` phrasing.
  Diverges from current iMio practice and from the toolchain the CI reusable workflows expect.

**Choice.** **A — approved by the maintainer 2026-07-29.** Cookieplone layout, `uv` + `mxdev`
+ `Makefile` for dev/CI, `pytest` + `pytest-plone`, `ruff`, `towncrier`, `plone/meta@2.x`
reusable workflows, and the `setup.py` shim for buildout develop-egg compatibility. §7's
`bin/test` is read as "the project's test entry point", not literally a buildout-generated
script.

**Why.** Consistency with the maintainer's own most recent addon, and it is the toolchain the
`plone/meta` reusable CI workflows expect. Deployment remains buildout; the `setup.py` shim is
the seam between the two layers. §9's "package-local Makefile precursor" is therefore the house
convention rather than a stopgap.

---

## 2026-07-29 — RESOLVED (§3 amendment): the kit ships `kit/tailwind.css`, not `tailwind.preset.js`

**Context.** §3 lists `imio/emailkit/kit/tailwind.preset.js` — "email-safe preset (px units,
no CSS vars, safelist)". Maizzle 6 ships Tailwind **4**, which is CSS-first: the Maizzle docs
state flatly that "Tailwind CSS 4 is configured in CSS, there's no `tailwind.config.js`
anymore", and v5's `tailwindcss-preset-email` is replaced by `@maizzle/tailwindcss`, imported
from CSS (`@import "@maizzle/tailwindcss";`) with theme tokens in an `@theme { }` block.
A JS preset file has no supported loading path.

**Options.**

- **A — kit ships a CSS entry instead of a JS preset** (`kit/tailwind.css`): `@import
  "@maizzle/tailwindcss";` plus an `@theme { }` block carrying the email-safe tokens. §3's
  file listing is amended; §3's *intent* (one shared, locked, email-safe Tailwind config
  owned by the kit) is unchanged.
- **B — keep a `.js` preset via Tailwind 4's `@config` escape hatch.** Unverified through
  Maizzle's PostCSS pipeline, which strips `@layer`/`@property` at-rules by default. No
  Maizzle documentation confirms it survives.
- **C — pin Maizzle 5 + Tailwind 3** to keep §3's file layout literal. Contradicts the
  spec's own "built on Maizzle 6" mandate and starts on an EOL toolchain.

**Choice.** **A — approved by the maintainer 2026-07-29.** The kit ships
`imio/emailkit/kit/tailwind.css`: `@import "@maizzle/tailwindcss";` plus an `@theme { }` block
carrying the email-safe tokens. §3's file listing is amended to replace `tailwind.preset.js`
with `tailwind.css`.

**Why.** The only option that is both current and supported. §3's intent — one shared, locked,
email-safe Tailwind config owned by the kit, which consumers compose against but do not extend
— is fully preserved; only the file format changes. Option B (`@config` escape hatch) is
unverified through Maizzle's PostCSS pipeline, and option C (pin Maizzle 5) would contradict
the spec's own Maizzle 6 mandate and start on an EOL toolchain.

**Consequence for the theming model.** §3's "consumers do not extend the Tailwind config" is
now enforced by *where the tokens live* rather than by convention: `@theme { }` sits inside the
kit's CSS entry. The three runtime-variable tokens (`logo_url`, `primary_color`, `footer_html`)
are unaffected — they remain Chameleon placeholders in literal inline styles, not Tailwind.

---

## 2026-07-29 — RESOLVED (§10.2): output extension is configured directly, no post-build rename

**Context.** §10.2 left open whether the Vite pipeline can emit `.pt` directly or whether the
compile script renames post-build, noting "either is fine; rename is the assumed default".

**Finding.** Maizzle 6 has a first-class `output.extension` option (default `'html'`), plus a
`--ext` CLI flag; the maintainers' own documented example is `extension: 'blade.php'`, so
non-HTML extensions are an intended use case. Per-template override is `useOutputPath()`
inside `<script setup>`, which replaced v5's frontmatter `permalink`.

**Choice.** `output: { extension: 'pt' }`. No rename step in `bin/compile-emails`.

**Why.** One fewer moving part than the spec's assumed default, and it is the supported
path rather than a workaround. Verified empirically in Phase 0.

---

## 2026-07-29 — LIKELY RESOLVED (§10.1): `kit-mode = path` is supported by design

**Context.** §10.1 asked whether pointing Maizzle at the egg's kit directory works, or
whether we must fall back to `copy`.

**Finding.** Maizzle 6's `components.source` accepts absolute paths and its own type
documentation says paths are "resolved relative to `cwd` (**not** `root`), so paths outside
the email root directory work as expected". The implementation resolves via `path.resolve`,
which returns an absolute path unchanged. Maizzle renders server-side via SSR, and the
framework never sets `server.fs.allow` — the Vite restriction that would have blocked this
guards browser-fetched files, not SSR disk reads.

**Choice.** Plan for `kit-mode = path` as the default, as the spec prefers. `copy` stays the
documented fallback.

**Residual risks to settle in Phase 0.** (1) the *dev server* path specifically, not just
`maizzle build`; (2) bare `import` specifiers inside kit components — Vite resolves
`node_modules` by walking up from the importer, and a site-packages directory has no
`node_modules` ancestor. Mitigation, if needed: keep kit SFCs import-free and rely on
Maizzle's auto-imports.

---

## 2026-07-29 — Maizzle 6 API/config names differ from the spec's prose; pin `>=6.0.5`

**Context.** The spec was written against Maizzle's v5-era vocabulary. Several names changed
in the Vite rewrite. Recorded so implementation reads the spec's *intent* correctly rather
than its literal option names.

**Findings and consequences.**

| Spec says | Maizzle 6 actually | Consequence |
|---|---|---|
| `removeUnusedCSS` (§3, §9) | `css.purge` — **on by default** in v6 | Same transformer, new name. §9's exit criterion is read as "after `css.purge`". |
| `maizzle.config.base.js` (§3) | `maizzle.config.{ts,js}`, ESM `export default defineConfig({})` | `.js` still accepted, so §3's filename stands. The v5 `build: {}` wrapper is gone. |
| `npx maizzle build production` (§5) | `maizzle build -c production.config.ts` | Corrected in the generated script. |
| "wrapped in `v-pre`" (§3 rule 3) | `v-pre` works; `<Raw>` is the v6 block-level escape | `<Raw>` extracts pre-compile into a static VNode. Prefer `<Raw>` for blocks, `v-pre` for a single element. |

**Additional decisions taken from this.**

- **`css.purge.backend` must be extended.** Its default delimiter shield covers
  Handlebars/Liquid/Jinja (`{{ }}`, `{% %}`) but not Chameleon; add
  `backend: [{ heads: '${', tails: '}' }]`.
- **`html.format` is `true` by default** and re-indents output via `oxfmt`. Since we commit
  generated `.pt` and gate on a byte diff (§5 `check-emails`), evaluate `html: { format:
  false }` in Phase 0 to keep diffs meaningful.
- **Pin `@maizzle/framework >= 6.0.5`**: v6.0.3 fixed whitespace preservation in compiled
  HTML and v6.0.5 fixed entity encoding in comment nodes before purge — both directly affect
  fidelity of committed output.
- **A programmatic Node API exists** (`build()`, `render()`, `createRenderer()`), which is a
  cleaner basis for `bin/preview-emails` (§5) than shelling out to the CLI. Phase 4 concern;
  noted now.
- **`replaceStrings` is a poor tool for injecting TAL** — keys compile to case-insensitive
  global regexes, and `${`, `{`, `}`, `?`, `*`, `+`, `^`, `.`, `|`, `(`, `)` are all regex
  metacharacters present in TAL syntax. Authors use `<Raw>`/`v-pre` instead.

**Why it matters.** §3's authoring rule 2 ("no runtime-computed `class` values") is now
*confirmed load-bearing*, not merely cautious: `css.purge` is `email-comb` plus a DOM-aware
step that only understands `class=` and `id=`, and it will delete class references it cannot
match — including from the `class` attribute itself. Separately, `css.safe` maps `$`→`-`,
`{`/`}`→`` and `:`→`-` inside class atoms, so Chameleon syntax in a `class` attribute is
actively corrupted. Both are exactly the silent-failure modes §5's lint step targets.

---

## 2026-07-29 — GAP: how the `.txt.pt` plaintext twin is produced

**Context.** §4 requires a `<name>.txt.pt` twin per template with "placeholders intact", and
§6.1 has `render()` return `(html, text)`. The spec does not say how the twin is *built*.

**Finding.** Maizzle 6 has plaintext support (a `plaintext` config key, `--plaintext` flag,
and an exported `createPlaintext()`), so the twin can plausibly come from the same build
rather than being hand-written — but only if `${}`/`tal:` survive the HTML→text conversion,
which is unverified.

**Status.** Open. Added to the Phase 0 spike as a cheap extra assertion, since the template
under test already carries every placeholder form. If placeholders do not survive, the
options are a hand-authored `.txt.pt` per template or a `<Raw>`-wrapped text block; that
choice comes back here with evidence.

---

## 2026-07-29 — PyPI name availability checked (spec §10.4)

**Context.** §10.4 requires checking PyPI availability for the planned distribution names
"now regardless" of the deferred `collective.emailkit` split.

**Finding.** All names are unregistered (`GET https://pypi.org/pypi/<name>/json` → HTTP 404,
checked 2026-07-29):

| Name | Status |
|---|---|
| `imio.emailkit` | free |
| `imio.recipe.emailkit` | free |
| `collective.emailkit` | free |
| `imio.mailkit` | free |
| `imio.recipe.mailkit` | free |

**Choice.** No action needed; the names in the spec are available. Recorded so the check is
not repeated. Registration happens at first release, not now.

---

## 2026-07-29 — RESOLVED: repository renamed to `imio.emailkit`

**Context.** The git remote was `github.com/IMIO/imio.mailkit`, but `SPEC.md` names the
distribution `imio.emailkit` throughout (§2 artifacts table, §3 kit path
`imio/emailkit/kit/`, §4 entry-point group `imio.emailkit.templates`, §5 recipe
`imio.recipe.emailkit`, §8 profiles `imio.emailkit:base`/`:default`, registry records
`imio.emailkit.theme.*`).

**Choice.** The maintainer renamed the GitHub repository to `IMIO/imio.emailkit`; the local
remote was repointed to match. Repository name, distribution name and Python namespace all
read `imio.emailkit`, exactly as the spec has it.

**Why.** One name for one artifact. The spec was already unambiguous; the repository was the
outlier.

**Note.** The local working directory is still `imio.mailkit` — cosmetic only, no effect on
packaging, and left alone to avoid breaking in-flight tooling paths.

---

## 2026-07-29 — Subagent definitions live in `.claude/agents/`

**Context.** The mission requires five project subagents (`spec-guardian`, `maizzle-author`,
`plone-dev`, `test-writer`, `researcher`) so exploration and build output stay out of the
main context.

**Choice.** Committed as project-scoped agent definitions in `.claude/agents/*.md`, each
instructed to read `SPEC.md` first and each carrying the subset of §3/§6/§7 rules it owns.

**Why.** Project-scoped rather than user-scoped so the rules travel with the repository and
apply to every contributor's assistant, not just one machine.

**Note.** Claude Code loads the agent registry at session start, so definitions created
mid-session are not selectable until the next session; during this session the same roles
are run with their instructions passed inline.
