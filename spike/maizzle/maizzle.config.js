import { defineConfig } from '@maizzle/framework'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { stripAuthorComments } from './strip-comments.js'

const here = dirname(fileURLToPath(import.meta.url))

// Absolute path to a component directory OUTSIDE this Maizzle project root.
// Stands in for the kit directory resolved from the installed `imio.emailkit`
// egg -- SPEC §10.1 `kit-mode = path`.
const KIT = resolve(here, '..', 'kit-outside')

export default defineConfig({
  output: {
    // SPEC §10.2: emit `.pt` directly from the pipeline. No post-build rename.
    extension: 'pt',
  },

  components: {
    // `prefix: 'Kit'` avoids collision with Maizzle's own built-in `Button`
    // component, and exercises the prefixed-resolver code path.
    source: [{ path: KIT, prefix: 'Kit', pathPrefix: false }],
  },

  css: {
    // GOTCHA (verified in Phase 0): the `css` key is NOT deep-merged with the
    // defaults. Supplying only `purge` silently drops `inline`, `shorthand`,
    // `safe` and `preferUnitless`, so no CSS gets inlined at all -- the build
    // still succeeds and looks plausible. Every key must be restated.
    inline: true,
    shorthand: true,
    safe: true,
    preferUnitless: true,
    purge: {
      // The default delimiter shield covers Handlebars/Liquid/Jinja
      // (`{{ }}`, `{% %}`) but NOT Chameleon. Without this, `${...}` inside a
      // class attribute is fair game for purge.
      backend: [{ heads: '${', tails: '}' }],
    },
  },

  html: {
    // Left at the default `true` on purpose: formatted output makes the
    // purge-on/purge-off diff line-granular and readable, which is the whole
    // point of the evidence. Determinism (build twice -> identical bytes) is
    // asserted separately, since SPEC §5's staleness gate depends on it.
    format: true,
  },

  afterTransform({ html }) {
    return stripAuthorComments(html)
  },
})
