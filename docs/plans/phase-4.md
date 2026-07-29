# Phase 4 — Consumer mechanics

**Date:** 2026-07-29
**Spec:** §9 phase 4, §5 (the recipe), §4 (discovery), §7 (golden tests, CI contract), §3 (Agent Skill)
**Depends on:** Phases 0–3 complete

---

## 1. Exit criteria

Verbatim from §9:

> | **4 — Consumer mechanics** | `imio.recipe.emailkit` (kit wiring, `compile-emails` + `--new` scaffolding, `check-emails` + authoring lint, `preview-emails`), entry-point discovery for external addons, golden-test base class, `emailkit` Agent Skill | One pilot consumer addon green in CI, including staleness and lint gates |

Acceptance, per the mission brief: **`git clone && buildout && bin/compile-emails` works from a clean
checkout**, and two dummy consumer addons live in `tests/` doubling as living documentation (§7).

This is the first phase whose exit criterion I can meet in full — no pilot addon from outside is
needed, because §9 asks for "one pilot consumer addon green in CI" and §7 asks for the two dummies. I
build those; Phase 5 is where a *real* addon arrives.

## 2. A second distribution

`imio.recipe.emailkit` is a **separate egg** (§2's artifact table), so this phase adds a second
packaging root. Layout decision to make and record: a sibling directory in this repo, or its own
repository. §2 lists them as two artifacts without saying where they live.

**Leaning: a sibling directory in this repo** (`recipe/`), released as its own distribution. One
checkout, one CI run, and the recipe's tests can exercise the real kit next door instead of a pinned
release. Split later if release cadences diverge — the same argument §3 makes for deferring the npm
package. To be confirmed as a decision entry before building.

## 3. The dev/deploy toolchain seam

The recipe generates buildout scripts, but this repo's own dev tooling is `uv` + `mxdev` (approved
decision, matching `imio.reportproblem`). Those are not in conflict — buildout is how iMio *deploys*
— but the acceptance test explicitly says `buildout`, so Phase 4 needs a **real buildout** in CI to
run it. That is new infrastructure for this repo and the main risk in the phase.

Node stays a dev/CI tool. The recipe must **not** compile during buildout by default (§5 is explicit:
`compile-on-install = false`, and §5's "Explicitly rejected" section says compiling at buildout time
would make Node a production dependency across ~350 applications).

## 4. Scope

| Deliverable | Spec |
|---|---|
| `imio.recipe.emailkit`: resolve eggs, collect `imio.emailkit.templates` entry points, record `(package, emails_dir, templates_dir)`, resolve the kit dir | §5 |
| `bin/compile-emails [--package NAME] [--watch] [--new NAME]` | §5 |
| `bin/check-emails [--package NAME]` — staleness **and** authoring lint | §5 |
| `bin/preview-emails [--package NAME]` — the two-stage loop, generalised from the Makefile | §5, §9 note |
| `kit-mode = path \| copy` (default `path`, confirmed viable in Phase 0) | §5, §10.1 |
| Entry-point discovery for **external** addons | §4 |
| Golden-test base class exported from the egg for consumers | §7 |
| Two dummy consumer addons in `tests/` | §7 |
| `emailkit` `SKILL.md` | §3 |

## 5. The authoring lint — gate 2 of `check-emails`

§5 wants "plain-regex checks (~30 lines)" of the `.vue` sources. Every rule below is a failure this
project has actually hit, which is why the list is longer than §5's three examples — and each one
produced a **successful build**:

| Rule | Evidence |
|---|---|
| `tal:`/`i18n:` attributes on a kit component | §3 rule 1 — attribute fallthrough |
| runtime-computed `class` values | §3 rule 2 |
| a Chameleon placeholder in a literal `style` attribute | Phase 0 caveat A1 — eats the brace **and silently kills inlining document-wide** |
| a Chameleon placeholder in a literal `class` attribute | Phase 0 control 2 — `css.safe` corrupts it |
| missing `alt` on `Img` | §3 |
| `--` inside any comment | caveat A2 — unparseable `.pt` at runtime; has bitten four times, including in ZCML |
| the raw-escape component's name written in angle brackets inside a comment | Phase 1 — swallows the real block |
| `${helper(...)}` instead of `${python: helper(...)}` | Phase 1 — TAL paths cannot call functions |

Keep it regex-simple per §5. A lint that needs a parser is a lint nobody runs.

## 6. Test plan

| # | Gate |
|---|---|
| 1 | recipe unit tests: egg resolution, entry-point collection, kit-dir resolution, script generation |
| 2 | `kit-mode = path` and `= copy` both produce a working build |
| 3 | **`git clone && buildout && bin/compile-emails`** from a clean checkout — the acceptance test |
| 4 | `bin/check-emails` staleness gate: passes clean, fails on a tampered `.pt`, non-zero exit, per-file diff |
| 5 | authoring lint: one fixture per rule in §5 above, each caught; and a clean file passing |
| 6 | `bin/compile-emails --new NAME` scaffolds the four files and the result compiles |
| 7 | `bin/preview-emails` renders through `render()` with fixtures and serves |
| 8 | discovery finds templates in **two** external dummy addons, namespaced, no collision |
| 9 | the exported golden base class works from a consumer addon's own test suite |
| 10 | CI: the dummy addons run the §7 contract (staleness + goldens) and go red when either breaks |
| 11 | `compile-on-install = false` by default — buildout install runs no Node |

## 7. Non-goals

- **No npm publication.** The kit stays in the egg (§3); extraction has an explicit trigger and this is not it.
- **No compiling during buildout by default** (§5, explicitly rejected).
- **No content-rule action, no real pilot addon migration** → Phase 5
- **No new builder methods** — §6.2 frozen.
- **No Node in a runtime or default-install path**, ever.

## 8. Risks

| Risk | Response |
|---|---|
| Standing up a real buildout in CI is slow or fragile | it is the acceptance test §9 asks for; if it cannot be made reliable, report that rather than substituting a weaker check |
| The recipe duplicates Makefile logic | the Makefile is the precursor §9 sanctions; extract shared logic into the egg and have both call it, rather than maintaining two copies |
| `--watch` / `preview-emails` needs a process holding a ZODB connection | deferred in Phase 1 for exactly this reason; it is the piece with real design in it |
| The lint produces false positives and gets disabled | prefer a missed case to a false alarm; every rule needs a passing-clean fixture too |
