/**
 * Maizzle project config for the `dummy.complete` consumer add-on.
 *
 * Identical to `dummy.minimal`'s except for `output.path`.
 *
 * Do not: spread `css` partially (shallow spread silently disables
 * `css.inline`); import from `node_modules` in a kit file or a bare
 * specifier in a `.vue` template; or point `output.path` anywhere but the
 * committed `templates/` dir (a build empties that directory first).
 *
 * `kitDir` is relative only because these dummies live inside the
 * `imio.emailkit` checkout.
 */
import { defineConfig } from '@maizzle/framework'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const kitDir = resolve(here, '..', '..', '..', '..', '..', 'src', 'imio', 'emailkit', 'kit')

const { kitBaseConfig } = await import(resolve(kitDir, 'maizzle.config.base.js'))
const kit = kitBaseConfig()

export default defineConfig({
  ...kit,

  output: {
    ...kit.output,
    path: resolve(here, '..', 'templates'),
  },
})
