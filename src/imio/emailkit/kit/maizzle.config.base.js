/**
 * Shared Maizzle 6 build config for `imio.emailkit` and every consumer
 * addon:
 *
 *     import { defineConfig } from '@maizzle/framework'
 *     import { kitBaseConfig } from '<kit-dir>/maizzle.config.base.js'
 *     export default defineConfig({ ...kitBaseConfig(), output: { path: '…' } })
 *
 * No bare import specifiers: this file lives in `site-packages`, with no
 * `node_modules` ancestor, so it cannot import `@maizzle/framework` or
 * call `defineConfig` itself. Every option below is stated in full, never
 * left to merge with Maizzle's defaults, since a consumer spreading this
 * object shadows whole keys and a half-specified `css` block ships
 * nothing inlined while the build still reports success.
 */
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import {
  flattenConditionalComments,
  stripAuthorComments,
  unbreakPunctuation,
} from './strip-comments.js'

export const kitDir = dirname(fileURLToPath(import.meta.url))

/** @param {string} [dir] Kit directory; `bin/compile-emails` passes it
 * explicitly for an installed egg. */
export function kitBaseConfig(dir = kitDir) {
  return {
    content: ['src/templates/**/*.vue'],

    output: {
      extension: 'pt',
    },

    components: {
      /** `pathPrefix: false` drops the intermediate folder, so
       * `layouts/Main.vue` becomes `KitMain`, not shadowing Maizzle's
       * own built-in `Button` component the way an unprefixed
       * `Button.vue` would (which Maizzle refuses). */
      source: [{ path: dir, prefix: 'Kit', pathPrefix: false }],
    },

    css: {
      inline: true,
      shorthand: true,
      safe: true,
      preferUnitless: true,
      purge: {
        /** Covers Chameleon's `${...}`, which the default delimiter
         * shield does not: without this, purge and `css.safe` treat it
         * as fair game. */
        backend: [{ heads: '${', tails: '}' }],
      },
    },

    html: {
      /** On, not the Maizzle default, so committed `.pt` diffs stay
       * line-granular. Maizzle's own defaults are the only ones that
       * leave all four Outlook conditional comments intact. */
      format: true,
    },

    emailkit: {
      /** A CSS entry, not a JS preset, since Maizzle 6 ships Tailwind 4. */
      cssEntry: resolve(dir, 'tailwind.css'),
    },

    /** Three passes; see `strip-comments.js`. None of their failure
     * modes is visible at build time. */
    afterTransform({ html }) {
      return unbreakPunctuation(
        flattenConditionalComments(stripAuthorComments(html))
      )
    },
  }
}

export default kitBaseConfig()
