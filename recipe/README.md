# imio.recipe.emailkit

A `zc.buildout` recipe that gives every `imio.emailkit` consumer three scripts:
`bin/compile-emails`, `bin/check-emails` and `bin/preview-emails`.

## Usage

```ini
[buildout]
parts = ... emails

[emails]
recipe = imio.recipe.emailkit
eggs = ${instance:eggs}
# compile-on-install = false   (default)
# kit-mode = path | copy       (default: path)
# node-bin = node              (resolution: PATH by default)
```

The part scans `eggs` for distributions whose ZCML registers
`<emailkit:templates>`, records each one's `emails/`/`templates/` paths, and
writes the three scripts using the design kit from `imio.emailkit`.

**A plain buildout run invokes no Node, touches no `emails/` directory, and
imports no consumer code.** `compile-on-install` opts in to compiling at
install time; default `false`.

## Options

| Option | Default | What it does |
|---|---|---|
| `eggs` | *required* | distributions to scan; normally `${instance:eggs}`. |
| `kit-mode` | `path` | how the design kit wires into a consumer's Maizzle build. |
| `node-bin` | `node` | the Node executable; `npm`/`npx` sit beside it. |
| `compile-on-install` | `false` | run `compile-emails` as an install step. Opt-in. |

Every option is also a script flag (`--kit-mode copy`).

## The scripts

### `bin/compile-emails [--package NAME] [--watch] [--new NAME]`

Steps: wire the kit, `npm ci` if `node_modules` is stale, `npx maizzle
build`, then copy the plaintext twins back in, since `maizzle build` empties
its output directory. Exits non-zero on failure.

`--watch` delegates to Maizzle's dev server, which shows **build-time**
output: raw `${item/title}`, unexpanded `tal:repeat`. Use
`preview-emails --watch` for a real preview.

`--new NAME` scaffolds the four files a template needs: a `.vue` skeleton, a
fixture, a golden placeholder, and a registration stub. It refuses to
overwrite files without `--force`; the skeleton follows every authoring
rule.

### `bin/check-emails [--package NAME]`

**The CI check.** Two checks:

1. *Staleness.* Snapshot the committed `.pt` files, build in place, diff,
   restore. Exit 1 with a per-file diff. Covers every `.pt` under the
   package, not just `templates/`.
2. *The authoring lint*: `python -m imio.emailkit.lint <paths>`. A missing
   lint module **fails** this check. `--no-lint` skips it explicitly.

`--lint-only` runs the authoring lint alone; no Node needed.

### `bin/preview-emails [--package NAME] [--watch]`

Compiles and renders every template through `render()` with its fixture,
serving it with a language switcher and live reload.

It needs **no ZODB and no `zope.conf`**: a minimal ZCML load gives real
placeholder substitution and real FR/NL/DE translations. Two things stay
fake: `portal_url` is empty, and theme tokens use the kit's defaults
(override with `--theme token=value`). For real site branding, use
`@@emailkit-preview`.

`--no-compile` renders the committed `.pt` files as-is.

## What a consumer addon has to do

Three things, once.

**1. Lay the addon out as follows.** `emails/` sits inside the package or at
the checkout root; both work.

```
src/acme/notifications/
├── emails/                     # dev only; prune it from the sdist
│   ├── package.json
│   ├── maizzle.config.js
│   ├── .kit/                   # generated; ignores itself
│   ├── twins/                  # hand-authored *.txt.pt, if any
│   └── src/templates/*.vue
└── templates/*.pt              # committed build output
```

**2. Write `emails/maizzle.config.js` against `./.kit/`.** Three imports and
one override. `recipe/tests/consumer` is a working example.

```js
import { defineConfig } from '@maizzle/framework'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { kitBaseConfig } from './.kit/maizzle.config.base.js'

const here = dirname(fileURLToPath(import.meta.url))
const kit = kitBaseConfig()

export default defineConfig({
  ...kit,
  output: { ...kit.output, path: resolve(here, '..', 'templates') },
})
```

`compile-emails` materializes `emails/.kit/` before every build, identical in
both modes, so a consumer's config never mentions which one. `path` mode
re-exports the kit from the installed egg (zero-copy); `copy` mode holds the
kit itself. Consumers never vendor kit files.

Do not add `"type": "module"` to `emails/package.json`: jiti must transpile
the kit file's ESM syntax, since in `path` mode it lives outside any npm
tree.

**3. Register in ZCML and run the checks in CI:**

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="acme.notifications"
    >
  <include package="imio.emailkit" file="meta.zcml" />
  <emailkit:templates>
    <emailkit:template name="welcome" subject="[email_subject_welcome] Welcome" />
  </emailkit:templates>
</configure>
```

```
bin/check-emails --package acme.notifications
```

## `kit-mode`: which one?

Use `path` unless something forces you off it: zero-copy, and it cannot go
stale. `copy` is a verified, **byte-identical** fallback, for when Maizzle or
packaging stops resolving files outside the npm tree.

## Development

This distribution is a sibling directory in the `imio.emailkit` repository,
released separately. Its tests run in two environments: no single one has
both buildout and the Plone runtime.

```
make recipe-test      # both runs; the union covers every test
make buildout-test    # the full buildout acceptance test, end to end
make buildout-clean   # remove everything that writes
```

`test-buildout.cfg` at the repository root is the harness. `test-buildout-pypi.cfg`
is the same thing resolving from PyPI — the literal "git clone && buildout".
