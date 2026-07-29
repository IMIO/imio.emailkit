# Phase 1 — Better defaults

**Date:** 2026-07-29
**Spec:** `SPEC.md` §9 phase 1, §3 (kit), §4 (discovery), §6.1 (`render()`), §8 (Plone default mails)
**Depends on:** Phase 0 — all four assumptions confirmed, four caveats carried in here

---

## 1. Exit criteria

Verbatim from §9:

> | **1 — Better defaults** | `render()` + locale helpers, built-in kit (`Main.vue` + core components + tokens; a11y defaults, `lang`, preheader slot), restyled password-reset & registration mails, `:base`/`:default` profiles | Installed on one production site; stock mails restyled; opt-out and layer-override both verified |

**One clause I cannot satisfy and will not pretend to.** "Installed on one production site" needs a
production Plone site and a deployment decision that are not mine to make. Phase 1 substitutes
*installed and verified on a real Plone 6.2.1 instance built from this repo* — the same profile
run, the same layer, the same mails, in a test fixture and a runnable local instance. The
production install is handed over as a documented, one-command step. This is stated as a gap, not
quietly redefined.

The other three clauses are met in full: stock mails restyled, opt-out (`:base`) verified,
layer-override verified.

## 2. Scope

| Deliverable | Spec |
|---|---|
| Package scaffold (Cookieplone layout, `setup.py` shim, CI, Makefile) | §2, house convention |
| Built-in kit: `maizzle.config.base.js`, `tailwind.css`, `layouts/Main.vue`, `components/` | §3 |
| Entry-point discovery + `TemplateNotFound` | §4 |
| `render()` + locale helpers (`format_date`, `format_datetime`, `format_number`, `lang`) | §6.1 |
| Restyled password-reset and registration mails as jbot overrides | §8.1 |
| `:base` / `:default` GS profiles, `IEmailkitLayer`, theme-token registry records | §8.2, §3 |
| Makefile preview-loop precursor | §9 sequencing note |
| Golden-file tests, discovery tests, override/opt-out tests | §7 |

## 3. Carried-in caveats from Phase 0 — all four must be honoured

| Caveat | Where it lands in Phase 1 |
|---|---|
| A1 — placeholder in `style`/`class` silently kills inlining | kit components use `tal:attributes="style string:…"` for theme tokens; nothing else |
| A2 — `--` in a comment makes the `.pt` unparseable | `strip-comments` hook moves into `maizzle.config.base.js` |
| A3 — `i18n:domain` absent means silent non-translation | `Main.vue` emits `i18n:domain="imio.emailkit"` on `<html>` |
| D1 — `meta.zcml` alone is a silent no-op | ZCML includes the whole `z3c.jbot` package; the test layer never relies on autoinclude |
| D2 — view kwargs land in `options`, `MemberData` is not traversable | resolved below |

## 4. Two decisions this phase must settle

### 4.1 The namespace seam (was open after Phase 0)

Our own templates render through `render()` with a flat context. The two Plone-default overrides
are rendered by a *stock view* whose kwargs land in `options`, and `MemberData` cannot be
path-traversed at all.

**Decision: a scoped two-dialect approach, with a host-agnostic shell.**

- `Main.vue` defines the names *it* needs with TAL's fallback operator, so the shell works under
  either host without the author thinking about it:
  `tal:define="lang lang | options/lang | string:en; theme theme | options/theme | nothing; preheader preheader | options/preheader | nothing"`
- The **two** Plone-default mail bodies use the hosting view's idiom (`options/…`,
  `python:member.getProperty('…')`). They are the documented exception: we do not control the view
  that renders them.
- Every other template — ours and consumers' — uses `render()`'s flat context, which is the one
  dialect §3 teaches.

Rejected: a universal `tal:define` preamble normalising `member` for all templates. It cannot work,
because the problem is not the *name* but that `MemberData` is not traversable — the preamble would
have to know each field. Two dialects scoped to two files beats a leaky abstraction everywhere.

### 4.2 The plaintext `.txt.pt` twin

Settled with evidence, not assertion: test Maizzle's `plaintext` output for whether `${}`/`tal:`
survive, then pick. If it survives, twins are generated; if not, they are hand-authored for the two
default mails and `render()` uses §4's documented naive-extraction fallback elsewhere. Result goes
to `docs/DECISIONS.md` either way.

## 5. Workstreams (parallel)

Three independent tracks, each with its own agent, converging on integration tests.

**W1 — kit (`maizzle-author`).** `src/imio/emailkit/kit/`: `maizzle.config.base.js` (restating
every `css` key per the Phase 0 no-deep-merge gotcha, `output.extension: 'pt'`, the
`strip-comments` hook, `components.source` prefixed `Kit`), `tailwind.css` (`@import
"@maizzle/tailwindcss"` + `@theme`), `layouts/Main.vue` (a11y defaults, `lang`, `i18n:domain`,
preheader, header/footer with theme tokens), `components/{Button,Panel,DataTable}.vue`. Plus the
`emails/` project and the two default-mail templates.

**W2 — runtime (`plone-dev`).** Package scaffold; `discovery.py` (entry-point scan + cache +
`TemplateNotFound`); `render()` loading via `Products.PageTemplates.PageTemplateFile` (Phase 0
pinned this) with theme tokens from the registry and locale helpers; `interfaces.py`
(`IEmailkitLayer`); `profiles/{base,default}`; ZCML including all of `z3c.jbot`.

**W3 — tests + CI (`test-writer`).** `testing.py` layers, `conftest.py`, golden-file base class,
fixtures, discovery tests, the override/opt-out/layer-precedence matrix, GitHub Actions on
`plone/meta@2.x`, Makefile targets.

Then integration by me: wire the pieces, run everything, `spec-guardian` on the diff.

## 6. Test plan

| # | Gate |
|---|---|
| 1 | `make build` compiles the kit's templates; committed `.pt` matches (staleness check) |
| 2 | Golden-file tests: each registered template renders against its fixture and matches its snapshot, FR and EN |
| 3 | Discovery: `imio.emailkit` finds its own templates; unknown name raises `TemplateNotFound` with `available=[...]` |
| 4 | `render()` returns `(html, text)`; placeholders resolved; **assert on substituted values**, never markers (Phase 0's zope.tal trap) |
| 5 | Locale helpers: `format_date`/`format_datetime`/`format_number` bound to render language, FR vs EN differ |
| 6 | `:default` installed → both stock mails restyled; rendered output contains kit markup and inlined CSS |
| 7 | **Opt-out**: `:base` installed → stock mails untouched (negative assertion) |
| 8 | **Layer override**: a site layer *extending* `IEmailkitLayer` with its own jbot dir wins over ours |
| 9 | Theme tokens: changing `imio.emailkit.theme.primary_color` in the registry changes rendered output |
| 10 | `make check` (ruff + zpretty + pyroma) and the full pytest suite green |

## 7. Non-goals

- **No `Email` builder**, recipient adapters, attachments, per-language send → Phase 2
- **No `render_shell()`** → Phase 3
- **No `imio.recipe.emailkit`**, no `bin/compile-emails` / `check-emails` / `preview-emails`; Phase 1 gets a **Makefile** precursor only → Phase 4
- **No entry-point discovery of *external* addons** beyond our own registration working → Phase 4
- **No content-rule action** → Phase 5
- **No `@@emailkit-preview` view** → Phase 2 (§6.3 lists it there)
- **No authoring lint** → Phase 4
- **No npm publication** of the kit, ever

## 8. Risks

| Risk | Response |
|---|---|
| The two stock mails need data the override cannot reach | §4.1's scoped dialect; if a field is still unreachable, report it rather than adding a view class silently |
| `multipart/alternative` needed for HTML mail | Phase 0 flagged it; `text/html` first, MIME shape is a Phase 2 question |
| Kit `Main.vue` grows into a god-template | it owns exactly the shell: a11y, `lang`, `i18n:domain`, preheader, header, footer slot. Anything else is a component |
| Scaffold churn eats the phase | scaffold is copied from `imio.reportproblem`, not designed |
