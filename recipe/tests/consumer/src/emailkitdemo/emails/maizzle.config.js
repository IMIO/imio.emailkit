/**
 * A consumer addon's Maizzle config: three imports and one override.
 *
 * The kit is reached through `./.kit/maizzle.config.base.js`, written by
 * `bin/compile-emails`. This file does not need to know if it holds a
 * re-export (`kit-mode = path`) or the kit itself (`kit-mode = copy`).
 */
import { defineConfig } from '@maizzle/framework'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { kitBaseConfig } from './.kit/maizzle.config.base.js'

const here = dirname(fileURLToPath(import.meta.url))
const kit = kitBaseConfig()

export default defineConfig({
  ...kit,

  output: {
    ...kit.output,
    path: resolve(here, '..', 'templates'),
  },
})
