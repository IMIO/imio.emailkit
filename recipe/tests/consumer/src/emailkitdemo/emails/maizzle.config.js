/**
 * What a consumer addon's Maizzle config looks like: three imports and one
 * override.
 *
 * The kit is reached through `./.kit/maizzle.config.base.js`, which
 * `bin/compile-emails` materialises before every build (SPEC §3/§5). In
 * `kit-mode = path` that file is a two-line re-export of the kit inside the
 * installed `imio.emailkit` egg, so components resolve straight out of
 * site-packages; in `kit-mode = copy` it is the kit itself, copied in. This file
 * cannot tell, and does not have to -- which is the whole point of the wiring.
 *
 * Nothing else is overridden. `emailkit.cssEntry` comes from the kit and is
 * therefore mode-dependent by construction, which is what makes the two modes
 * observably different rather than merely differently spelled.
 *
 * No `"type": "module"` in package.json, for the same reason as the main project:
 * Maizzle then loads this file through jiti, which transpiles the ESM syntax in
 * the kit file this imports -- a file that, in `path` mode, lives outside any npm
 * tree and has no package.json of its own to declare its module type.
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
    /** SPEC §4: the committed build output, a sibling of `emails/`. */
    path: resolve(here, '..', 'templates'),
  },
})
