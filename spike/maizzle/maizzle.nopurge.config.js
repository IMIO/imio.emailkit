import { defineConfig } from '@maizzle/framework'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { stripAuthorComments } from './strip-comments.js'

const here = dirname(fileURLToPath(import.meta.url))
const KIT = resolve(here, '..', 'kit-outside')

// Control build: identical to maizzle.config.js except `css.purge` is off.
// Diffing this against the purge-on output is the primary evidence for
// assumption (a) -- it shows exactly what purge removed.
export default defineConfig({
  output: {
    extension: 'pt',
    path: 'dist-nopurge',
  },

  components: {
    source: [{ path: KIT, prefix: 'Kit', pathPrefix: false }],
  },

  css: {
    purge: false,
  },

  html: {
    format: true,
  },

  afterTransform({ html }) {
    return stripAuthorComments(html)
  },
})
