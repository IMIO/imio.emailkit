import glob from 'fast-glob'
import { Nunito, Quicksand } from 'next/font/google'

import { Providers } from '@/app/providers'
import { Layout } from '@/components/Layout'

import '@/styles/tailwind.css'

// `next/font` downloads these at build time and self-hosts them in the export,
// so the published site never calls fonts.googleapis.com. Quicksand is the iMio
// display face; Nunito is the brand's open stand-in for the licensed Avenir LT Std.
const quicksand = Quicksand({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-quicksand',
})

const nunito = Nunito({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-nunito',
})

export const metadata = {
  title: {
    template: '%s - imio.emailkit',
    default: 'imio.emailkit — developer documentation',
  },
  description:
    'Transactional email templating for the iMio Plone ecosystem: author HTML mails with Maizzle 6 and render them with Chameleon, with no Node.js in production.',
}

export default async function RootLayout({ children }) {
  let pages = await glob('**/*.mdx', { cwd: 'src/app' })
  let allSectionsEntries = await Promise.all(
    pages.map(async (filename) => [
      '/' + filename.replace(/(^|\/)page\.mdx$/, ''),
      (await import(`./${filename}`)).sections,
    ]),
  )
  let allSections = Object.fromEntries(allSectionsEntries)

  return (
    <html
      lang="en"
      className={`h-full ${quicksand.variable} ${nunito.variable}`}
      suppressHydrationWarning
    >
      <body className="flex min-h-full bg-white antialiased dark:bg-zinc-900">
        <Providers>
          <div className="w-full">
            <Layout allSections={allSections}>{children}</Layout>
          </div>
        </Providers>
      </body>
    </html>
  )
}
