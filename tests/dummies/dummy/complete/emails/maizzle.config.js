/**
 * Maizzle project config for the `dummy.complete` consumer add-on.
 *
 * Identical to `dummy.minimal`'s except for `output.path`, which is the point:
 * the kit's base config carries everything, and a consumer's config is two
 * settings long however big the add-on gets.
 *
 * What a consumer must NOT do here, all three learned the hard way:
 *
 *  - Do not spread `css` partially (`{...kit, css: {purge: …}}`). Object spread is
 *    shallow, so it shadows the whole key and `css.inline` goes back to its
 *    default. The build still exits 0 and the mail ships with nothing inlined.
 *  - Do not add an `import` of anything from `node_modules` to a kit file, or of
 *    a bare specifier to a `.vue` template. Vite resolves those by walking up
 *    from the importing file, and the kit lives in a Python egg.
 *  - Do not point `output.path` anywhere but the committed `templates/` dir.
 *    `maizzle build` **empties** its output directory, silently, with no option to
 *    stop it -- it has already deleted a committed hand-authored twin in this
 *    repository. That is why the twins below live in `emails/twins/` and are
 *    copied in after the build.
 *
 * As in `dummy.minimal`, `kitDir` is a relative path only because these dummies
 * live inside the `imio.emailkit` checkout; `bin/compile-emails` resolves it from
 * the installed egg (SPEC §5, `kit-mode = path`).
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
