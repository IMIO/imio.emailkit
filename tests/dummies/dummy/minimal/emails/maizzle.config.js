/**
 * Maizzle project config for the `dummy.minimal` consumer add-on.
 *
 * Spread the kit's base config, then set the one thing it cannot know:
 * where the compiled `.pt` files go.
 *
 * `kitDir` is a relative path, not the real consumer lookup through
 * `bin/compile-emails`, since these dummies live inside the checkout.
 * `node_modules` is a symlink to the checkout's own install, required
 * because Tailwind resolves the kit's import by walking up from the
 * template's directory; without it Maizzle silently ships uncompiled CSS.
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
    // Committed to `<package>/templates/`, named by the ZCML `directory`.
    path: resolve(here, '..', 'templates'),
  },
})
