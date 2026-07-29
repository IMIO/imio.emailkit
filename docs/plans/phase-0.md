# Phase 0 — Spike

**Status:** awaiting approval
**Date:** 2026-07-29
**Spec:** `SPEC.md` Draft 4, §9 phase 0 + §10 open questions 1 & 2

---

## 1. Purpose

Phase 0 validates the one unvalidated assumption on the critical path: **that Maizzle 6
build output survives as a Chameleon template**. Nothing is built to keep. The deliverable
is *evidence*, committed, plus a written verdict per assumption.

> §9: "Phase 0 remains the load-bearing one, but it shrank: the Maizzle-output-vs-Chameleon
> interaction is now the only unvalidated assumption on the critical path (discovery/recipe
> validation moved to Phase 4)."

If any assumption fails, work stops and options are presented. Nothing is engineered around
silently.

## 2. Spec sections covered

| Section | What Phase 0 settles |
|---|---|
| §9 phase 0 | the whole row (deliverable + exit criterion) |
| §10.1 | `kit-mode = path` viability — Maizzle resolving components outside the project root |
| §10.2 | output extension: `.pt` direct from the pipeline vs. post-build rename |
| §3 authoring rules | rules **2–4** are exercised by the torture template. Rule 1 (no `tal:`/`i18n:` on kit components) is **not** tested here — enforcement is §5's lint step in Phase 4 |
| §8.1 | that a compiled `.pt` functions as a `z3c.jbot` override on a browser layer |

### Gating vs. non-gating

Only assumptions **(a)–(d)** gate the phase; they are exactly §9's deliverable and exit
criterion. Assumption **(e)** and the two negative controls are **non-gating**: they are
opportunistic observations that cost a build flag and two lines of template, recorded in the
report for later phases. They cannot fail Phase 0, and an inconclusive result for them is
recorded as inconclusive rather than quietly counted as a pass.

## 3. Assumptions under test

Each gets a verdict of **CONFIRMED** / **CONFIRMED WITH CAVEAT** / **FAILED** in
`docs/plans/phase-0-report.md`, each backed by a committed artifact.

**(a) Maizzle 6 output survives Chameleon.** `${...}` in text nodes and in non-`class`
attributes; `tal:repeat` on a `<tr>` inside a compiled table; `tal:condition`,
`tal:attributes`; `i18n:translate=""` and `i18n:translate="msgid"` + `i18n:name`; and
inlined styles landing correctly *after* `css.purge` (the v6 name for `removeUnusedCSS`).

**(b) Output extension.** `output: { extension: 'pt' }` emits `.pt` directly.
Research says this is first-class; the spike confirms it and retires the assumed rename step.

**(c) `kit-mode = path`.** Components resolved from an **absolute path outside the Maizzle
project root**, simulating a directory inside a Python egg. Tested under both `maizzle build`
**and** `maizzle dev` — research flagged the dev server as the unverified half.

**(d) jbot override wins.** A Maizzle-compiled `.pt` — inlined styles, TAL, i18n and all —
placed in a `z3c.jbot` overrides directory registered on a browser layer, overriding a real
CMFPlone/PasswordReset mail template, and winning.

**(e) — non-gating, opportunistic.** Do `${}`/`tal:` placeholders survive Maizzle's plaintext
generation (§4's `.txt.pt` twin)? The template under test already carries every placeholder
form, so this costs one build flag and one assertion. Not part of §9 phase 0's deliverable,
and §4 already specifies a runtime fallback ("missing `.txt.pt` twin → warning at startup,
`render()` falls back to a naive text extraction"), so twin *production* is not on the
critical path. Recorded as an observation only; it cannot fail the phase.

## 4. Approach

The spike is deliberately built as **one torture-test template**, not a realistic email.
Realism is Phase 1's job; Phase 0 wants maximum syntax coverage per unit of work, so a single
template carries every construct at once and one diff answers several questions.

Two builds of the same source — **purge on** and **purge off** — are produced and diffed
against each other. That single diff is the primary evidence for (a): it shows exactly what
`css.purge` removes, and whether anything it removed was load-bearing.

The template also carries two **non-gating negative controls** — a class referenced only from
`tal:attributes="class ..."`, and a Chameleon placeholder inside a `class` attribute. Both are
*expected to break*: research says `css.purge` is blind to anything outside `class=`/`id=`,
and that `css.safe` maps `$`→`-`, `{`/`}`→`` and `:`→`-` inside class atoms. They cost two
lines and document a failure mode §5's lint will later catch. Enforcing §3's rules is Phase 4's
job, not Phase 0's; these controls only observe.

Note the two controls target **different transformers**: control 1 is about `css.purge`,
control 2 about `css.safe`. `css.purge.backend` shields purge only and does not govern
`css.safe`, so it should not mask control 2 — but if either control comes back inconclusive,
the report says inconclusive.

Verdict (d) needs a real Plone. The spike bootstraps a throwaway test environment with
`uv` + the Plone constraints file, following the `imio.reportproblem` conventions
(pytest + pytest-plone). This is **spike-local and sets no precedent** — the Phase 1 test
harness is a Phase 1 decision, and the dev-tooling question is logged separately in
`docs/DECISIONS.md`.

## 5. File-by-file change list

Everything lands under `spike/` (throwaway) plus two documents. **No file outside `spike/`
and `docs/` is created or touched in this phase.**

### Maizzle side

| File | Purpose |
|---|---|
| `spike/README.md` | what this is, how to run it, that it is throwaway and why it stays committed (evidence for the report) |
| `spike/package.json` | `@maizzle/framework >= 6.0.5` (v6.0.3 fixed whitespace preservation, v6.0.5 entity encoding before purge — both affect committed-output fidelity) |
| `spike/package-lock.json` | committed, so the evidence is reproducible |
| `spike/maizzle.config.js` | `output.extension: 'pt'`; `components.source` pointing at the **absolute** out-of-root kit path; `css.purge.backend: [{ heads: '${', tails: '}' }]`; `html.format` evaluated both ways |
| `spike/maizzle.nopurge.config.js` | same with `css: { purge: false }` — the control build |
| `spike/tailwind.css` | Tailwind 4 CSS-first entry: `@import "@maizzle/tailwindcss"` + an `@theme {}` block. Matches the approved §3 amendment replacing `tailwind.preset.js` with `kit/tailwind.css` (`docs/DECISIONS.md`, 2026-07-29) |
| `spike/emails/spike.vue` | the torture-test template (§6) |
| `spike/kit-outside/Button.vue` | kit component living **outside** the Maizzle root; emits `style="background-color: ${theme/primary_color}"` per §3's theme-token model |
| `spike/kit-outside/Panel.vue` | second out-of-root component, to prove more than a single-file fluke; import-free, per the bare-specifier risk in `docs/DECISIONS.md` |

### Python side

| File | Purpose |
|---|---|
| `spike/fixture.py` | context data: a list for `tal:repeat`, theme tokens, `lang` |
| `spike/render.py` | standalone Chameleon render of the compiled `.pt` with the fixture — no Plone needed, proves `render()` is feasible as a pure function (§6.1) |
| `spike/plone/` | minimal throwaway addon: `configure.zcml`, a browser layer, a `<browser:jbot directory="overrides"/>` registration, and the compiled `.pt` as the override |
| `spike/plone/test_jbot.py` | pytest-plone test asserting the override wins |
| `spike/mx.ini`, `spike/Makefile` | `uv` + Plone constraints bootstrap for the jbot test, following `imio.reportproblem` conventions |

### Committed evidence

| File | Purpose |
|---|---|
| `spike/build/spike.pt` | compiled output, purge **on** |
| `spike/build/spike.nopurge.pt` | compiled output, purge **off** (control) |
| `spike/build/purge.diff` | the diff between the two — primary evidence for (a) |
| `spike/build/spike.txt` | plaintext output, for (e) |
| `spike/rendered/spike.fr.html` | Chameleon-rendered final HTML |
| `spike/rendered/spike.jbot.html` | rendered through the jbot override, for (d) |

**Drift is untracked in the spike.** The committed `spike/build/*` artifacts can fall out of
sync with `spike/emails/spike.vue` because the staleness gate (§5 `check-emails`) does not
exist until Phase 4. Mitigation is procedural: all artifacts are regenerated in one pass and
committed together with their source, and the report names the commit they came from. The
"`.vue` and `.pt` move together" rule is honoured by hand here, and by `bin/check-emails`
from Phase 4 on.

### Documents

| File | Purpose |
|---|---|
| `docs/plans/phase-0-report.md` | per-assumption verdict, each citing its artifact; plus surprises |
| `docs/DECISIONS.md` | already seeded; updated with Phase 0 outcomes |

## 6. What `spike/emails/spike.vue` must contain

Every construct the runtime depends on, in one file:

- `${...}` in a **text node** and in **non-`class` attributes** (`href`, `style`)
- `tal:repeat` on a `<tr>` **inside a table** — the specific §9 requirement
- `tal:condition`, `tal:attributes="style ..."` with literal values (§3 rule 2's sanctioned pattern)
- `i18n:translate=""` on an element; `i18n:translate="msgid"` with `i18n:name`
- `structure` on the shell's `body_html` slot — the one sanctioned use (§3 rule 4)
- a `<Raw>` block and a `v-pre` element — both v6 escape hatches, compared
- two out-of-root kit components (`Button`, `Panel`)
- Tailwind utility classes that must survive purge and be inlined
- §3's baked-in a11y: `role="presentation"` on layout tables, `alt` on the image, `lang="${lang}"` on `<html>`, the hidden preheader `<div>`
- **negative control 1:** a class referenced only from `tal:attributes="class ..."` — expected to be purged
- **negative control 2:** `${...}` inside a `class` attribute — expected to be corrupted by `css.safe`

## 7. Test plan

Each step is a pass/fail gate with a committed artifact.

| # | Step | Assertion | Assumption |
|---|---|---|---|
| 1 | `npm ci && npx maizzle build` in `spike/` | exits 0; `build/spike.pt` exists — no rename step ran | (b) |
| 2 | inspect `build/spike.pt` | `${...}` intact in text and non-`class` attributes; `tal:repeat`/`tal:condition`/`tal:attributes` intact; `i18n:translate=""` not stripped (v6 removes empty `style`/`class` only); `<Raw>`/`v-pre` content verbatim | (a) |
| 3 | inspect `build/spike.pt` | elements carrying Tailwind classes have real inlined `style="..."`; the theme-token `style` placeholder survived as a literal | (a) — §9 exit criterion |
| 4 | `diff build/spike.nopurge.pt build/spike.pt` | the only differences are unused-CSS removals; **no** placeholder, TAL attribute or needed declaration is among them | (a) — §9 exit criterion |
| 5 | same diff, negative controls | both controls **do** break, as predicted; inconclusive is recorded as inconclusive | non-gating — evidence for §3 rule 2 |
| 6 | grep output for `kit-outside` markup | both out-of-root components resolved and rendered | (c) |
| 7 | `npx maizzle dev` | dev server starts and resolves the out-of-root components too | (c) — the unverified half |
| 8 | `python render.py` | Chameleon parses and renders without error; `tal:repeat` produced one row per fixture item; every `${...}` substituted; nothing left unresolved | (a) — §9 exit criterion |
| 9 | plaintext build | whether `${}`/`tal:` survive into `build/spike.txt` | (e) |
| 10 | `pytest spike/plone/test_jbot.py` | the compiled `.pt` overrides the stock template; rendered output contains the kit marker and not the stock one | (d) — §9 exit criterion |

Steps 1–9 need only Node and Chameleon, both already available locally. Step 10 needs the
`uv` + Plone bootstrap.

## 8. Exit criteria

Copied verbatim from §9:

> | **0 — Spike** | Maizzle 6 → `.pt` pipeline on one template; `tal:repeat` + `${}` inside a compiled table row; jbot override of the compiled output | Inlined styles land correctly after `removeUnusedCSS`; Chameleon renders the output; jbot override wins |

Read against Maizzle 6's vocabulary, `removeUnusedCSS` is `css.purge` (see `docs/DECISIONS.md`).

Phase 0 is done when:

1. all three clauses of that exit criterion are demonstrated with committed artifacts;
2. `docs/plans/phase-0-report.md` carries a verdict per assumption (a)–(e), each citing its artifact;
3. every surprise is recorded in `docs/DECISIONS.md` or escalated;
4. `spec-guardian` has reviewed the diff.

## 9. Non-goals

Explicitly **not** in Phase 0 — each belongs to a later phase and will be refused if it
creeps in:

- **No kit authoring.** No `Main.vue`, no real components, no theme tokens in the registry. The spike's `kit-outside/` files are stubs that exist only to prove path resolution. → Phase 1
- **No `render()` API, no locale helpers.** `spike/render.py` is a throwaway script, not the beginning of the module. → Phase 1
- **No `Email` builder, no recipient/attachment adapters, no per-language send.** → Phase 2
- **No package scaffold**: no `pyproject.toml`, no `setup.py`, no `src/imio/emailkit/`, no namespace. → Phase 1
- **No GenericSetup profiles**, no `IEmailkitLayer` for real, no restyled Plone mails. The spike's `spike/plone/` addon is a test harness, not a draft of the package. → Phase 1
- **No recipe, no `bin/` scripts, no `Makefile` for the package.** The Phase 1 Makefile precursor is a Phase 1 deliverable. → Phases 1 / 4
- **No i18n catalogs**, no `.pot`, no translations. → Phase 1
- **No CI configuration.** → Phase 4 (per §7's CI contract), scaffolded with the package
- **No golden-file harness.** → Phase 4
- **No `check-emails` lint implementation.** Phase 0 only produces the *evidence* that the rules it will enforce are real. → Phase 4
- **No kit `tailwind.css`.** The §3 amendment is approved, but authoring the real kit CSS entry is Phase 1. `spike/tailwind.css` is a throwaway stand-in sized to make purge and inlining observable. → Phase 1

## 10. Known risks

| Risk | Mitigation |
|---|---|
| `css.purge` deletes something needed and no safelist fixes it | that *is* the finding — report it, present options (§10 says fall back, never engineer around) |
| Vue compiler mangles a specific `tal:`/`i18n:` attribute | the torture template enumerates the full attribute set, so this surfaces now rather than in Phase 3 |
| bare `import` specifiers fail from the out-of-root kit dir (no `node_modules` ancestor) | kit stubs are import-free by design; if it bites, `vite.resolve.alias` is the documented escape |
| the real CMFPlone mail template is registered in a way jbot cannot reach | that is itself a §8.1 finding and gets reported; fall back to overriding an own view to keep (d) answerable |
| the Plone bootstrap eats disproportionate time | steps 1–9 are independent of it and land first; (d) is the only one gated on it |

## 11. Cleanup

`spike/` stays committed through Phase 1 as the evidence backing the report, then is removed
in a single `chore:` commit once the real kit supersedes it. It is never imported by package
code and never ships in an sdist.
