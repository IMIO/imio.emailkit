import { usePathname } from 'next/navigation'

/**
 * The current path without its trailing slash — `/quickstart`, never `/quickstart/`.
 *
 * `next.config.mjs` sets `trailingSlash: true` so the static export writes
 * `out/quickstart/index.html`, which GitHub Pages can serve directly. The cost is
 * that `usePathname()` then reports `/quickstart/`, while the `navigation` array
 * and the section map built in `app/layout.jsx` are both keyed `/quickstart`.
 * Comparing the two raw would silently break every active-page highlight, the
 * per-page section list, and the previous/next footer links — all without an error.
 *
 * Every comparison against a page href goes through this hook.
 */
export function usePagePathname() {
  let pathname = usePathname()
  return pathname !== '/' ? pathname.replace(/\/$/, '') : pathname
}
