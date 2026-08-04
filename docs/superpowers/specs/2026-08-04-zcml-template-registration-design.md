# ZCML directive for email-template registration

**Date:** 2026-08-04
**Status:** Approved
**Replaces:** the `imio.emailkit.templates` entry-point + dict mechanism (SPEC §4)

## Problem

Template registration currently rides on a setuptools entry point pointing at a
module-level dict. It works, but it is not the idiomatic Zope registration
mechanism: duplicate names silently overwrite each other, there is no
`overrides.zcml` story, msgid domains must be wired by hand through a
MessageFactory, and the runtime needs a scan/cache/warm-up dance
(`get_templates`, `invalidate_cache`, `warm_cache` on `IDatabaseOpenedWithRoot`)
to simulate what ZCML execution gives for free.

## Decision

Replace the entry point with a ZCML directive. Clean cut: no deprecation shim,
no entry-point fallback. `imio.emailkit` remains its own first consumer, now via
its own ZCML.

Build tooling (the buildout recipe and the `bin/` scripts) discovers consumer
packages by executing their ZCML with `zope.configuration` itself, through a
permissive `ConfigurationMachine` that no-ops every directive except ours —
consumers may put the directives in any ZCML file reachable from
`configure.zcml` or `overrides.zcml`; no dedicated-file convention, no marker
entry point, no hand-rolled XML parsing.

## 1. The directive (runtime)

`imio.emailkit` ships a `meta.zcml` defining the namespace
`http://namespaces.imio.be/emailkit` with a grouping directive:

```xml
<configure xmlns:emailkit="http://namespaces.imio.be/emailkit"
           i18n_domain="imio.pm.notifications">
  <emailkit:templates directory="templates">
    <emailkit:template name="item_published"
                       subject="email_subject_item_published"
                       preheader="email_preheader_item_published" />
    <emailkit:template name="meeting_convocation"
                       subject="email_subject_meeting_convocation" />
  </emailkit:templates>
</configure>
```

- `<emailkit:templates>` is a grouping directive. `directory` is optional,
  defaults to `templates`, and is resolved relative to the package containing
  the ZCML file.
- `<emailkit:template>` attributes: `name` (required, the file stem),
  `subject` (required, MessageID), `preheader` (optional, MessageID). The
  msgid domain comes from the enclosing `i18n_domain` — consumers no longer
  build msgids in Python.
- The full lookup name stays `<package>:<basename>`; the package part is
  derived from the ZCML file's package (the configuration context), never
  spelled out by the consumer.
- Each template emits one configuration action with discriminator
  `('emailkit:template', full_name)`. Duplicate registrations raise
  `ConfigurationConflictError` at startup; `overrides.zcml` works for free.
- File resolution and its failure modes move into the directive handler and
  keep firing at startup (ZCML execution *is* startup):
  - missing `<name>.pt` → warning, template skipped;
  - missing `<name>.txt.pt` → warning, `text_path = None`, `render()` keeps
    its deprecated naive-text fallback;
  - missing/nonexistent `directory` → warning, nothing registered for the
    package.
- A broken registration must not take the instance down harder than the
  entry-point scan did: file-level problems are warnings, only genuine ZCML
  errors (bad attribute, duplicate name) fail configuration.

### discovery.py after the change

Deleted: the entry-point scan, `ENTRY_POINT_GROUP`, the cache,
`invalidate_cache`, `warm_cache` and its `IDatabaseOpenedWithRoot`
subscription in `configure.zcml`.

Kept (public API unchanged): `Template`, `get_template`,
`available_templates`, `TemplateNotFound`.

Added: `register_template(template)` — the single write path into the
module-level registry, called by the directive handler (which the build
tooling's scan executes too, see §2). `render.py`, the templates vocabulary
and the preview view keep their lookups untouched.

`imio.emailkit` drops its own entry point from `setup.py` and registers its
templates through the directive.

## 2. Build-time discovery (recipe + bin/ scripts)

Build tooling executes consumer ZCML with `zope.configuration` itself, via a
**permissive configuration machine**: a `ConfigurationMachine` subclass whose
`factory()` override returns a no-op grouping stub for any directive that is
not registered, instead of raising `ConfigurationError("Unknown directive")`.
Only `imio.emailkit`'s `meta.zcml` is loaded for real, so a consumer's
`configure.zcml` runs with genuine ZCML semantics — `<include>` resolution,
`zcml:condition`, `<exclude>`, `i18n_domain` — while `browser:page`,
`plone:*`, `genericsetup:*` and every other foreign directive is swallowed
without importing its handler (unknown directives never resolve their
handlers; only `<include package>` imports the named package to locate its
files, which is the same import the entry-point mechanism already performed).

The scan, per candidate package:

1. Cheap per-egg pre-filter: if no `.zcml` file under the package contains the
   namespace URI `namespaces.imio.be/emailkit` as a substring, skip the egg
   without executing anything.
2. Otherwise run the permissive machine over the roots Zope loads
   (`configure.zcml`, then `overrides.zcml`, when present — the same files
   `plone.autoinclude` picks up). The stock `include` directive is replaced by
   one that only follows includes resolving *inside* the scanned package;
   cross-package includes are skipped, since every egg is scanned from its own
   roots and following them would only double-count.
3. Execute the resulting actions against the registry: the emailkit directive
   handlers run unchanged, so the build tooling and a live instance populate
   `discovery.py`'s registry through the **exact same code path**. The recipe
   reads back per package: the resolved `emails/` dir, the `templates/` output
   dir, and the template names with their `subject`/`preheader` msgids.

A `.zcml` file never included from the roots is invisible, `zcml:condition`
and `<exclude>` behave for real. One documented divergence remains: feature
flags (`zcml:condition="have plone-X"`) are evaluated against an empty feature
set, since the full instance ZCML that provides features is not loaded — such
conditions are false at build time.

The scan lives in `imio.emailkit` (e.g. `imio.emailkit.scan`), next to the
directive it executes — no duplicated namespace constant, no parity test.

Two execution contexts, deliberately split:

- The **recipe's install step** runs in the buildout process, where the
  instance eggs are not importable — it therefore only records candidate
  packages via the substring pre-filter and generates the scripts.
- The **generated scripts** run with `${instance:eggs}` on `sys.path`, so
  Zope/Plone are importable *as libraries*; they invoke the real scan. The
  constraint on the scan chain is that it must not require a **booted**
  instance — no `getSite()`, no registry/utility lookups, no fully-loaded
  ZCML — which the permissive machine and the module-level registry satisfy
  by construction. A dedicated test runs the scan in a bare Python process
  (instance eggs present, no Zope app started).

`bin/preview-emails` calls the same scan to populate the registry before
calling `render()` — one parser (`zope.configuration`), one registry, one
registration code path.

## 3. i18n caveat

i18ndude does not extract msgids from ZCML. Subject/preheader msgids must be
added to consumer `.po` files by hand, or via a dummy `msgids.py` module if a
consumer prefers automated extraction. This is the one regression versus the
dict approach and gets an explicit line in SPEC §4.

## 4. Tests

- `testing.py`: the dummy addon registers through a ZCML string executed in
  the test layer instead of a fake entry point.
- Directive tests replace the discovery tests: happy path, default
  `directory`, missing `.pt` (skip + warning), missing `.txt.pt` (warning +
  `text_path=None`), missing directory, duplicate name →
  `ConfigurationConflictError`, `overrides.zcml` replacing a registration,
  msgid domain taken from `i18n_domain`.
- Scan tests (in `imio.emailkit`, against on-disk fixture packages): foreign
  directives swallowed without importing their handlers (a fixture whose
  handler module raises on import), `<include file>` followed, subpackage
  include followed, unreferenced file NOT counted, cross-package include
  skipped, `overrides.zcml` root honored, `zcml:condition` respected,
  feature-flag condition false at build time, pre-filter skips non-matching
  eggs, scan and runtime populate identical registries for the same fixture.
- No-instance test: the scan runs to completion in a bare Python subprocess
  (instance eggs on the path, no Zope app booted, no site set).
- Recipe tests shrink to the install step: candidate recording via the
  pre-filter and script generation.
- `bin/preview-emails`: a test that the scan-fed registry renders a fixture
  without a Zope instance.

## 5. Spec & docs changes

- SPEC §4 rewritten around the directive: consumer layout keeps `templates/`
  as committed build output; the "Registration: entry point" subsection
  becomes "Registration: ZCML directive" with the example above; the
  failure-mode paragraph gains the conflict error and the i18n caveat.
- SPEC §5 step 1 reworded: "collects distributions exposing the
  `imio.emailkit.templates` entry point" → "executes each candidate egg's
  ZCML through the permissive machine and collects `emailkit:` registrations",
  with the feature-flag divergence noted.
- README consumer instructions updated to the ZCML example, including the
  `<include package="imio.emailkit" file="meta.zcml" />` line consumers need
  (or `<include package="imio.emailkit" />` when their `configure.zcml`
  already depends on it).

## Out of scope

- Any change to the Maizzle build, the kit, `z3c.jbot` overrides (still
  operate on the resolved `.pt` files), fixtures/goldens content, or the
  rendering pipeline.
- A deprecation window for the entry point (clean cut, nothing shipped
  against it).
