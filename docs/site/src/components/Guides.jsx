import { Button } from '@/components/Button'
import { Heading } from '@/components/Heading'

const guides = [
  {
    href: '/quickstart',
    name: 'Quickstart',
    description:
      'Install the add-on, then send your first styled mail through the Email builder.',
  },
  {
    href: '/architecture',
    name: 'Architecture',
    description:
      'The build-time / runtime seam, and why no Node.js ever runs in production.',
  },
  {
    href: '/authoring/rules',
    name: 'Authoring rules',
    description:
      'Eight ways a template breaks while the build still reports success.',
  },
  {
    href: '/integration/migrating',
    name: 'Migrating a mail',
    description:
      'Get the styled shell around a body you already build, without re-authoring it.',
  },
]

export function Guides() {
  return (
    <div className="my-16 xl:max-w-none">
      <Heading level={2} id="guides">
        Guides
      </Heading>
      <div className="not-prose mt-4 grid grid-cols-1 gap-8 border-t border-zinc-900/5 pt-10 sm:grid-cols-2 xl:grid-cols-4 dark:border-white/5">
        {guides.map((guide) => (
          <div key={guide.href}>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">
              {guide.name}
            </h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              {guide.description}
            </p>
            <p className="mt-4">
              <Button href={guide.href} variant="text" arrow="right">
                Read more
              </Button>
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
