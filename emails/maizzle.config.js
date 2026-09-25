/**
 * Maizzle project config for `imio.emailkit`'s own templates.
 *
 * `imio.emailkit` is its own first consumer, so this file is the worked
 * example every consumer addon copies: spread the kit's base config, then
 * set only what a base config cannot know, such as where the compiled
 * `.pt` goes.
 *
 * `package.json` has no `"type": "module"` on purpose. Without it,
 * Maizzle loads this file through jiti, which transpiles ESM syntax
 * wherever it finds it, including in the kit file imported below, which
 * lives outside any npm tree and has no `package.json` of its own. With
 * `"type": "module"`, the same import only works on Node 22.7 or later,
 * where module-syntax detection is on by default.
 */
import { defineConfig } from '@maizzle/framework'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import { kitBaseConfig } from '../src/imio/emailkit/kit/maizzle.config.base.js'

const here = dirname(fileURLToPath(import.meta.url))
const pkg = resolve(here, '..', 'src', 'imio', 'emailkit')

/** Here the kit is a sibling in the same checkout, so `kitBaseConfig()`
 * derives it from its own file location. */
const kit = kitBaseConfig()

export default defineConfig({
  ...kit,

  output: {
    ...kit.output,
    /** Committed build output, discovered at runtime through the entry point. */
    path: resolve(pkg, 'templates'),
  },

  emailkit: {
    ...kit.emailkit,
    /** Reached through this project's own CSS file, which keeps the
     * absolute kit path out of committed CSS. */
    cssEntry: resolve(here, 'tailwind.css'),
  },
})
