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

The part resolves the eggs, collects every distribution whose ZCML registers
`<emailkit:templates>`, records each one's `emails/` and `templates/`
directory, resolves the design kit out of the `imio.emailkit` egg, and
writes the three scripts.

**A plain buildout run invokes no Node, touches no `emails/` directory, and imports
no consumer code.** That is not a happy accident, it is the point: compiling at
buildout time is explicitly rejected because it would make Node a production
dependency across ~350 applications and couple deployments to npm availability.
`compile-on-install` exists for deployments that deliberately accept Node at
deploy time, and it defaults to false.

## Options

| Option | Default | What it does |
|---|---|---|
| `eggs` | *required* | the distributions to scan. `${instance:eggs}` normally. |
| `kit-mode` | `path` | how the design kit is wired into each consumer's Maizzle build. |
| `node-bin` | `node` | the Node executable. `npm` and `npx` are taken beside it. |
| `compile-on-install` | `false` | run `compile-emails` as an install step. Opt-in. |

Every one of them is also a command-line flag on the generated scripts, so trying
`--kit-mode copy` does not mean editing `buildout.cfg`.

## The scripts

### `bin/compile-emails [--package NAME] [--watch] [--new NAME]`

Wire the kit → `npm ci` in `emails/` if `node_modules` is stale against the lockfile
→ `npx maizzle build` → copy the hand-authored plaintext twins back in. Non-zero on
any failure, and every package is attempted before it gives up, so one broken addon
does not hide the state of the others.

There is no rename step and no move step: Maizzle 6's `output.extension` emits `.pt`
directly and the consumer's own `output.path` writes into `templates/`.
What *is* copied is `emails/twins/*.txt.pt`, because
`maizzle build` empties its output directory and would otherwise delete a committed
twin.

`--watch` delegates to Maizzle's dev server, which shows **build-time** output: raw
`${item/title}`, unexpanded `tal:repeat`. Use `preview-emails --watch` for the loop
you actually want.

`--new NAME` scaffolds the four files a template needs — a `.vue` skeleton, a fixture,
a golden placeholder and a registration stub to paste — and refuses to overwrite
anything without `--force`. The skeleton starts on the right side of every
authoring rule.

### `bin/check-emails [--package NAME]`

**The CI gate.** Two gates:

1. *Staleness.* Snapshot the committed `.pt`, build in place, diff, restore. Exit 1
   with a per-file diff. Every `.pt` under the package is covered, not just
   `templates/` — `imio.emailkit`'s own build also emits its jbot overrides
   elsewhere — while directories the build never wrote into are left alone.
2. *The authoring lint*, `python -m imio.emailkit.lint <paths>`. **Called, not
   reimplemented**: the rules are about the templates, so they live with the runtime
   that ships them. A missing lint module **fails** the gate rather than skipping it;
   `--no-lint` makes skipping a deliberate, visible choice.

`--lint-only` runs gate 2 alone, which needs no Node.

### `bin/preview-emails [--package NAME] [--watch]`

Compile, render every registered template through `render()` with its committed
fixture, and serve the result with a language switcher and live reload. What you
look at is the mail, not the build output.

It needs **no ZODB and no `zope.conf`**: `render()` is a pure function of (template,
context, registry state), so a minimal ZCML load is enough for real placeholder
substitution and real FR/NL/DE translations. Two things are therefore not real —
`portal_url` is empty, and the theme tokens come from the kit's own defaults, which
`--theme token=value` overrides. For a preview against a real site's branding, use
`@@emailkit-preview`.

`--no-compile` renders the committed `.pt` as they are, which is a fast way to see
what is actually in git.

## What a consumer addon has to do

Three things, once.

**1. Lay the addon out as follows.** `emails/` may sit inside the package or at
the checkout root; both are found.

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

**2. Write `emails/maizzle.config.js` against `./.kit/`.** Three imports and one
override; `recipe/tests/consumer` is a working example.

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

`emails/.kit/` is materialised by `compile-emails` before every build and is
identical in shape in both `kit-mode`s, so a consumer's config never mentions the
mode. In `path` mode it holds a two-line re-export of the kit inside the installed
`imio.emailkit` egg, so Maizzle resolves components straight out of site-packages
(a zero-copy mode); in `copy` mode it holds the kit itself. Consumers never
vendor kit files.

Do not add `"type": "module"` to `emails/package.json`. Without it Maizzle loads the
config through jiti, which transpiles the ESM syntax in the kit file — a file that,
in `path` mode, lives outside any npm tree and has no `package.json` of its own to
declare its module type.

**3. Register in ZCML and run the gates in CI:**

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

`path` unless something forces you off it. It is zero-copy, it cannot go stale, and
Phase 0 verified that Maizzle resolves `components.source` from an absolute path
outside the project root. `copy` exists as a documented fallback and is verified
to produce **byte-identical** output; reach for it if a future Maizzle or a packaging
environment stops resolving files outside the npm tree.

## Development

This distribution lives in the `imio.emailkit` repository as a sibling directory,
released separately. Its tests run in two environments,
because no single one has both buildout and the Plone runtime:

```
make recipe-test      # both runs; the union covers every test
make buildout-test    # the Phase 4 acceptance test, end to end
make buildout-clean   # remove everything that writes
```

`test-buildout.cfg` at the repository root is the harness; `test-buildout-pypi.cfg`
is the same thing resolving from PyPI, i.e. the literal "git clone && buildout".
