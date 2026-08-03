import nextMDX from '@next/mdx'

import { recmaPlugins } from './src/mdx/recma.mjs'
import { rehypePlugins } from './src/mdx/rehype.mjs'
import { remarkPlugins } from './src/mdx/remark.mjs'
import withSearch from './src/mdx/search.mjs'

const withMDX = nextMDX({
  options: {
    remarkPlugins,
    rehypePlugins,
    recmaPlugins,
  },
})

// GitHub Pages serves this site from https://imio.github.io/imio.emailkit/, so
// every asset and link needs a `/imio.emailkit` prefix there — and no prefix at
// all under `npm run dev`. The deploy workflow sets NEXT_BASE_PATH; locally it
// is unset and the site lives at the root.
const basePath = process.env.NEXT_BASE_PATH ?? ''

/** @type {import('next').NextConfig} */
const nextConfig = {
  // A fully static site: no Node.js runtime on the hosting side, which is the
  // only thing GitHub Pages can serve.
  output: 'export',
  basePath,
  // `next/image`'s optimiser is a server feature; a static export needs the raw files.
  images: { unoptimized: true },
  // Emits `out/quickstart/index.html` rather than `out/quickstart.html`, so a link
  // to `/quickstart` resolves on GitHub Pages without relying on its
  // extension-stripping behaviour.
  trailingSlash: true,
  pageExtensions: ['js', 'jsx', 'ts', 'tsx', 'mdx'],
}

export default withSearch(withMDX(nextConfig))
