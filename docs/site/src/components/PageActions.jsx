'use client'

import Link from 'next/link'

import { REPO_URL } from '@/lib/project'
import { usePagePathname } from '@/lib/usePagePathname'

// Replaces the template's "Was this page helpful?" widget, which posted nowhere —
// on a static export it could only ever thank you and discard the answer. These
// two links do something: they land you in the editor for this exact page, or in
// a new issue. The MDX path is derived from the route, so there is nothing to keep
// in sync when pages are added.
export function PageActions() {
  let pathname = usePagePathname()
  let slug = pathname === '/' ? '' : `${pathname.replace(/^\//, '')}/`
  let editUrl = `${REPO_URL}/edit/main/docs/site/src/app/${slug}page.mdx`

  return (
    <div className="flex items-center justify-end gap-6 border-t border-zinc-900/5 pt-8 text-sm text-zinc-600 dark:border-white/5 dark:text-zinc-400">
      <Link
        href={editUrl}
        className="transition hover:text-zinc-900 dark:hover:text-white"
      >
        Edit this page
      </Link>
      <Link
        href={`${REPO_URL}/issues/new`}
        className="transition hover:text-zinc-900 dark:hover:text-white"
      >
        Report a problem
      </Link>
    </div>
  )
}
