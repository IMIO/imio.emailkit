# Phase 4 — Consumer mechanics: report

**Date:** 2026-07-29
**Plan:** `docs/plans/phase-4.md`

---

## Exit criteria

Verbatim from §9:

> | **4 — Consumer mechanics** | `imio.recipe.emailkit` (kit wiring, `compile-emails` + `--new` scaffolding, `check-emails` + authoring lint, `preview-emails`), entry-point discovery for external addons, golden-test base class, `emailkit` Agent Skill | One pilot consumer addon green in CI, including staleness and lint gates |

**This is the first phase whose exit criterion is met in full**, with no substitution.

| Clause | Status |
|---|---|
| `imio.recipe.emailkit` | **done** — second distribution, 115 own tests |
| kit wiring (`path` \| `copy`) | **done** — both modes exercised in the acceptance test |
| `compile-emails` + `--new` scaffolding | **done** |
| `check-emails` + authoring lint | **done** — §5's two gates in one script |
| `preview-emails` | **done** — compiles, renders through `render()`, serves |
| entry-point discovery for external addons | **done** — proven through a real buildout working set |
| golden-test base class | **done** — and verified present in a built wheel |
| `emailkit` Agent Skill | **done** — `SKILL.md` |
| **one pilot consumer green incl. both gates** | **done** — `emailkitdemo`, plus two dummies in `tests/` |

## Evidence

```
$ python -m pytest tests -q                 494 passed, 1 skipped, 2 xfailed
$ cd recipe && python -m pytest tests -q    115 passed, 1 skipped
$ make check                                exit 0
$ make check-emails                         exit 0   (both §5 gates)
$ zconsole … scripts/verify_install.py      ALL EXIT-CRITERION CHECKS PASSED
```

The acceptance test — §9's `git clone && buildout && bin/compile-emails`:

```
==> buildout, with node/npm/npx REMOVED from PATH
==> bin/compile-emails (kit-mode = path, the default)
==> bin/compile-emails --kit-mode copy
==> bin/check-emails --package emailkitdemo (both gates)
    gate 1: the committed build output is not stale
    gate 2: the authoring lint (SPEC §3 rules)     1 file,  no violations
==> bin/check-emails --package imio.emailkit (both gates)
    gate 2: the authoring lint (SPEC §3 rules)     8 files, no violations
==> bin/preview-emails
    Discovered 2 email template(s) from imio.emailkit.templates:
        emailkitdemo:demo, imio.emailkit:notification
==> Acceptance test passed
```

Two properties worth naming:

- **The no-Node boundary is tested, not asserted.** Buildout runs with `node`, `npm` and `npx` stripped
  from `PATH`. If Node ever leaks into a deployment path in front of ~350 production applications, that
  target fails. `compile-on-install` stays `false`.
- **External discovery is proven, not simulated.** `bin/preview-emails` found templates from **two
  distributions** through a real buildout working set — the recipe's whole reason to exist is serving
  add-ons it does not own.

## The authoring lint

Eight rules, plain regex, stdlib only — **one per failure this project actually hit, and every one of
them produced a successful build.** Each report gives location, what was found, the runtime
consequence, the fix, and the opt-out marker, because none of these are visible at build time.

Two judgement calls kept it usable:

- **Rule 2 is deliberately narrower than "no computed `class`".** The literal reading flags the kit's own
  `Panel.vue` (`:class="toneClass"`), which is *correct* — Vue resolves it at build time and every
  complete utility name is literal, so Tailwind's scanner finds them. The real hazard is a name
  assembled from fragments (`'bg-' + tone`), which no scanner can see. A lint that reddens a correct kit
  file is a lint switched off within a day.
- **Rule 6 shares the MSO guard with `kit/strip-comments.js`** so the two cannot drift, and exempts JS
  banner comments. **Rule 7 deliberately does scan JS comments**, because Maizzle's `rawExtract` regex
  runs over the raw file and has no concept of a comment — `<script>` is no shelter.

It found exactly one real violation in the repo (a `--` in an authoring comment), which was **fixed
rather than suppressed**, after which `check-emails` gained the lint as a prerequisite. Verified it
genuinely fails: a planted `--` gives exit 2 with the rule and the consequence.

## The most important finding of the phase

**`i18n:domain` inherits.** A consumer add-on's own `i18n:translate` nested inside the kit layout
resolves against the **`imio.emailkit`** catalog, not theirs. The msgid is not found, so it renders its
default text — in every language, identically.

This is caveat A3 one level out, and it is the worst silent failure the project has found, because:

- it is a **consumer's** failure, in their language files, not ours;
- there is **no visual symptom** — the text is real, grammatical and plausible;
- it would be discovered by a client reading a Dutch mail in English.

`dummy.complete`'s `convocation.vue` demonstrates the fix and its goldens show the contrast
deliberately. A ninth lint rule is the natural guard and is **recommended, not done**: distinguishing
"author forgot" from "author is deliberately reusing a kit msgid" needs the care that narrowed rule 2.

## Two packaging traps

- **`MANIFEST.in`'s `graft` follows symlinks.** The dummies need a `node_modules` symlink at build time,
  because without a `node_modules` *ancestor* Tailwind cannot resolve the kit's `@import` and **Maizzle
  ships the uncompiled stylesheet with exit 0** (5.3 KB → 3.5 KB, zero inline styles — briefly committed
  as broken output). That symlink put roughly **20,000 files into the sdist**, silently, invisible to
  `git status` because it is gitignored. Now self-cleaning; the built sdist has 0 `node_modules` entries.
- **The shipped golden base class is a separate module on purpose.** `golden.py` imports `pytest`;
  `testing.py` holds the Plone layers `zope.testrunner` consumers import. A test asserts `testing.py`
  never imports pytest, so they cannot merge by accident.

## Process notes

I raced my own test suite **three times** — running it while a workstream still owned `tests/`, and
twice while `make buildout-test` was emptying `templates/` (the documented Maizzle behaviour). Each time
I spent real effort diagnosing failures that were artefacts. The rule I should have followed from the
first occurrence: **run the suite only when nothing else is touching the tree.** Recorded because the
cost was mine and repeated.

I also fixed a wrong assertion of my own: `test_every_registered_template_has_a_fixture` checked *every*
registered template, so this package failed because a **consumer's** fixture lives in the consumer's
directory. It passed alone and failed whenever the dummies were installed in the same session.

## Left for the maintainer

- `SKILL.md` sits at the repo root and ships in the sdist but not the wheel, and is not under
  `.claude/skills/emailkit/`. Both are packaging choices.
- `bin/check-emails --package dummy.minimal` cannot drive the `tests/dummies` add-ons: it resolves
  packages from the buildout working set, and a fixture-installed `.dist-info` is in nobody's working
  set. `tests/test_consumer_ci.py` reproduces the gate's logic instead, which is also what makes its red
  half demonstrable without Node.
- The recommended ninth lint rule for `i18n:domain`.
