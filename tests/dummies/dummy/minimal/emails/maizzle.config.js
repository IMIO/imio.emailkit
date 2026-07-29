/**
 * Maizzle project config for the `dummy.minimal` consumer add-on.
 *
 * This is the whole build configuration a consumer needs: spread the kit's base
 * config, then set the one thing a base config cannot know -- where the compiled
 * `.pt` files go. Everything else (Tailwind entry, `css.*`, the `.pt` output
 * extension, the three `afterTransform` passes, the `Kit` component prefix) comes
 * from the kit and is deliberately not restated here.
 *
 * Two things a real add-on writes differently:
 *
 *  1. `kitDir` -- a real consumer never hardcodes it. `bin/compile-emails`
 *     (SPEC §5, `kit-mode = path`) resolves the kit directory from the installed
 *     `imio.emailkit` egg and wires it in. These dummies live *inside* the
 *     `imio.emailkit` checkout, so the honest thing here is a relative path to
 *     the sibling kit rather than a fake egg lookup.
 *  2. `node_modules` -- a real `emails/` directory has its own `package.json` and
 *     its own `npm ci`. These two borrow the checkout's install through a
 *     gitignored symlink that `tests/dummyaddons.py` creates for the build and
 *     removes afterwards, so the test suite never runs a second `npm ci`.
 *
 * That symlink is **not** optional, and the failure without it is the silent kind
 * this project keeps finding. Tailwind resolves the `@import "@maizzle/tailwindcss"`
 * that `Main.vue` emits by walking up from the *template's* directory; with no
 * `node_modules` ancestor the resolution fails, **Maizzle catches the CSS error and
 * ships the uncompiled stylesheet with exit code 0**, and the build says
 * "Built 1 template". Measured: 5.3 KB of compiled output with inlined styles
 * becomes 3.5 KB with none.
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
    /**
     * SPEC §4's consumer layout: build output is committed to `<package>/templates/`
     * and is what the entry-point registration's `directory` key names.
     */
    path: resolve(here, '..', 'templates'),
  },
})
