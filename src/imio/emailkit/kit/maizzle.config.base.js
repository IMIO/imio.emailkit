/**
 * Shared Maizzle 6 build config for `imio.emailkit` and every consumer addon
 * (SPEC §3). It ships inside the Python egg, so a consumer resolves the kit
 * directory from the installed distribution and spreads this object into its
 * own `maizzle.config.js`:
 *
 *     import { defineConfig } from '@maizzle/framework'
 *     import { kitBaseConfig } from '<kit-dir>/maizzle.config.base.js'
 *
 *     const kit = kitBaseConfig()
 *     export default defineConfig({ ...kit, output: { ...kit.output, path: '…' } })
 *
 * Two hard constraints on this file:
 *
 * 1. **No bare import specifiers.** It lives in `site-packages`, which has no
 *    `node_modules` ancestor for Node/Vite to walk up to, so it cannot import
 *    `@maizzle/framework` (and therefore cannot call `defineConfig` itself).
 *    Only `node:` builtins and relative kit files are safe. Same rule as the
 *    kit's `.vue` components.
 * 2. **Every option it cares about is stated in full**, never left to be merged
 *    with Maizzle's defaults. A consumer spreading this object will shadow whole
 *    keys, and a half-specified `css` block is the exact failure Phase 0 spent
 *    time on -- see the `css` block below.
 */
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import {
  flattenConditionalComments,
  stripAuthorComments,
  unbreakPunctuation,
} from './strip-comments.js'

/**
 * Absolute path of the kit directory this module was loaded from. Correct
 * whether the kit sits in a checkout's `src/` tree or in an installed egg,
 * because it is derived from this file's own URL.
 */
export const kitDir = dirname(fileURLToPath(import.meta.url))

/**
 * @param {string} [dir] Absolute path to the kit directory. Defaults to the
 *   directory this module was loaded from. Passing it explicitly is the path
 *   `bin/compile-emails` (SPEC §5) takes when it resolves the kit from the
 *   installed `imio.emailkit` egg rather than importing this file directly.
 */
export function kitBaseConfig(dir = kitDir) {
  return {
    /**
     * SPEC §4's consumer layout: sources in `emails/src/templates/`. Resolved
     * against `root`, which defaults to the directory the build runs from.
     */
    content: ['src/templates/**/*.vue'],

    output: {
      /**
       * Emit `.pt` straight from the pipeline. Confirmed in Phase 0 -- no
       * post-build rename step anywhere.
       */
      extension: 'pt',
    },

    components: {
      /**
       * `kit-mode = path` (SPEC §10.1): components are resolved from an
       * absolute path outside the Maizzle project root.
       *
       * `prefix` is not cosmetic. Maizzle ships a built-in `Button`, and an
       * unprefixed kit `Button.vue` shadows it; Maizzle throws on genuine
       * two-source collisions. `pathPrefix: false` drops the intermediate
       * folder, so `layouts/Main.vue` is `<KitMain>` and
       * `components/Button.vue` is `<KitButton>`.
       */
      source: [{ path: dir, prefix: 'Kit', pathPrefix: false }],
    },

    css: {
      /**
       * Every key is restated on purpose. Phase 0 lost real time to a partial
       * `css:` object that silently shipped a document with nothing inlined
       * while the build reported success. Restating is cheap; diagnosing a
       * mail whose CSS quietly vanished is not.
       */
      inline: true,
      shorthand: true,
      safe: true,
      preferUnitless: true,
      purge: {
        /**
         * The default delimiter shield covers Handlebars/Liquid/Jinja
         * (`{{ }}`, `{% %}`) but not Chameleon. Without this, `${...}` is fair
         * game for purge and for the `css.safe` selector rewriter.
         */
        backend: [{ heads: '${', tails: '}' }],
      },
    },

    html: {
      /**
       * Formatting is on (not the Maizzle default) because it keeps the
       * committed `.pt` diffs line-granular, which is what makes SPEC §5's
       * staleness gate readable. Output is deterministic either way.
       *
       * Maizzle's default options are kept: measured, they are the only ones
       * that leave all four Outlook conditional comments intact. Raising
       * `printWidth` or switching to `htmlWhitespaceSensitivity: 'css'` fixes
       * the formatter's inline-whitespace habit but costs either the
       * line-granular diffs or the conditional comments; the whitespace is
       * repaired in `afterTransform` instead.
       */
      format: true,
    },

    /**
     * Kit-owned settings the kit's own `.vue` files read back via
     * `useConfig()`. Consumers extend this object, they do not replace it.
     */
    emailkit: {
      /**
       * The one locked, email-safe Tailwind entry (SPEC §3, amended: a CSS
       * entry rather than a JS preset, because Maizzle 6 ships Tailwind 4).
       * `layouts/Main.vue` `@import`s this by absolute path, so the shell
       * works from inside an egg where no relative path would.
       */
      cssEntry: resolve(dir, 'tailwind.css'),
    },

    /**
     * Three passes, none cosmetic -- see `strip-comments.js`. The first makes
     * the compiled `.pt` parseable at all, the second keeps Outlook's
     * conditional comments working, the third keeps punctuation attached to the
     * word before it. None of the three failures is visible at build time.
     *
     * `afterTransform` is the first hook that sees formatted HTML, which is why
     * they run here and not earlier.
     */
    afterTransform({ html }) {
      return unbreakPunctuation(
        flattenConditionalComments(stripAuthorComments(html))
      )
    },
  }
}

export default kitBaseConfig()
