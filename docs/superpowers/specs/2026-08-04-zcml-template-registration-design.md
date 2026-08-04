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
packages by scanning their `.zcml` files with ElementTree — consumers may put
the directives in any ZCML file of their package; no dedicated-file convention,
no marker entry point.

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
module-level registry, called by the directive handler and by the build
tooling's scan (see §2). `render.py`, the templates vocabulary and the preview
view keep their lookups untouched.

`imio.emailkit` drops its own entry point from `setup.py` and registers its
templates through the directive.

## 2. Build-time discovery (recipe + bin/ scripts)

`imio.recipe.emailkit.projects` replaces its `iter_entry_points` walk with an
XML scan:

1. For each egg in the working set, recursively glob `*.zcml` under the
   package directory.
2. Cheap pre-filter: skip any file whose raw text does not contain the
   namespace URI `namespaces.imio.be/emailkit`.
3. ElementTree-parse the survivors and collect
   `{http://namespaces.imio.be/emailkit}templates` /
   `{…}template` elements, recording per package: the resolved `emails/`
   dir, the `templates/` output dir (from the `directory` attribute), and the
   template names with their `subject`/`preheader` msgids.

Because every `.zcml` file under the package is scanned, there is **no
`<include>`-following logic at all**.

Documented limitations of the scan (build tooling only — the runtime uses real
`zope.configuration` semantics):

- a `.zcml` file that exists in the package but is never included from
  `configure.zcml` still counts;
- `zcml:condition` on emailkit directives is ignored.

The namespace URI constant is duplicated in the recipe distribution with a
parity test against the runtime constant, replacing today's
`test_entry_point_group_matches_the_runtime`.

`bin/preview-emails` runs outside Zope and cannot execute a consumer's
`configure.zcml` (it uses directives whose meta only a full instance loads).
It therefore feeds the scan results into `register_template()` before calling
`render()`. One registry API, two feeders (directive handler at runtime, scan
in build tooling), one XML parser.

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
- Recipe tests: on-disk `.zcml` fixtures instead of entry-point fixtures;
  one test per scan limitation (never-included file counts, condition
  ignored); pre-filter skips non-matching files; namespace parity test.
- `bin/preview-emails`: a test that the scan-fed registry renders a fixture
  without a Zope instance.

## 5. Spec & docs changes

- SPEC §4 rewritten around the directive: consumer layout keeps `templates/`
  as committed build output; the "Registration: entry point" subsection
  becomes "Registration: ZCML directive" with the example above; the
  failure-mode paragraph gains the conflict error and the i18n caveat.
- SPEC §5 step 1 reworded: "collects distributions exposing the
  `imio.emailkit.templates` entry point" → "scans each egg's `.zcml` files for
  `emailkit:` directives", with the two scan limitations noted.
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
