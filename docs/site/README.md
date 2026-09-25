# imio.emailkit — documentation site

Developer documentation at **<https://imio.github.io/imio.emailkit/>**: a
[Next.js](https://nextjs.org) app exported as static HTML, deployed by
[`.github/workflows/docs.yml`](../../.github/workflows/docs.yml).

## Working on it

```shell
cd docs/site
npm install
npm run dev        # http://localhost:3000
```

`npm run build` writes the export to `out/`; CI gates on `npm run lint`.

## Adding a page

1. Create `src/app/<slug>/page.mdx`, with the metadata export:

   ```mdx
   export const metadata = {
     title: 'My page',
     description: 'One sentence — this is the meta description.',
   }

   # My page

   The opening paragraph, styled as a lead. {{ className: 'lead' }}

   ## A section
   ```

2. Add a line to `navigation` in
   [`src/components/Navigation.jsx`](src/components/Navigation.jsx).

Three things happen automatically:

- **Sidebar sub-nav**: from the page's `##` headings, via
  `src/mdx/rehype.mjs`. No `sections` export needed.
- **Search**: `src/mdx/search.mjs` globs `src/app/**/*.mdx` for FlexSearch. No
  configuration.
- **Previous/next links**: from `navigation`, read top-to-bottom; group order
  sets reading order.

## MDX components available in a page

No imports needed — they come from `src/components/mdx.jsx`.

| Component | Use |
| --- | --- |
| `<Note>` | Highlighted aside; supports prose, links, code. |
| `<Properties>` / `<Property name type>` | Definition lists for API pages. |
| `<CodeGroup>` | Tabbed code blocks; nest several fences. |
| `<Button href variant arrow>` | CTA outside prose; label wrapped in `<>…</>`. |
| `<Row>` / `<Col>` | Two-column layout on wide screens. |

Fenced code blocks auto-highlight, tag their language, and get a copy
button; annotate with `` ```python {{ title: 'setup.py' }} ``. Headings take
annotations too — `## Section {{ anchor: false }}` hides one from the
sub-nav.

## Deployment

`.github/workflows/docs.yml`:

- Any push or PR touching `docs/site/**` builds and lints, catching bad
  pages pre-merge.
- A push to `main` also deploys to GitHub Pages.
- Run it by hand from the Actions tab.
- **Settings → Pages → Source = "GitHub Actions"**: no workflow sets this —
  a Pages deploy error means check it.

### `basePath`

`next.config.mjs` reads `basePath` from `NEXT_BASE_PATH` — `/<repo-name>` in
the workflow, unset locally so `npm run dev` serves from the root. No
hardcoded URL.

`trailingSlash: true` writes `out/quickstart/index.html`, not
`out/quickstart.html`: `usePathname()` then reports `/quickstart/` while
`navigation` keys `/quickstart`. `src/lib/usePagePathname.js` normalizes
this. **Compare routes to page hrefs only through that hook** —
`usePathname()` directly silently breaks the active-page highlight, sub-nav,
and footer links.

## Where content belongs

The root [`README.md`](../../README.md) stays short — badges, the pitch,
`pip install`, a link here — this site holds **developer documentation**.

## Divergences from the stock template

Differences from a fresh copy of the template:

- `src/components/Code.jsx`: `CodePanel` skips `Children.only()` — it crashed
  prerenders under webpack's chunk-splitting; rehype already sets `code`.
- `typography.js`: plain media queries, not `@screen sm`/`@screen lg`
  (removed in Tailwind 4) — reverting silently drops these margins.
- `src/components/PageActions.jsx`: replaces the dead "Was this page
  helpful?" widget with links to the page's source and a new issue.
- `src/lib/project.js`: the repository and PyPI URLs, in one place.
- `emerald-*` → `accent-*` throughout, from the iMio brand magenta in
  `src/styles/tailwind.css`.

One cosmetic warning stays: Node's `MODULE_TYPELESS_PACKAGE_JSON` for
`typography.js`. Fixing it needs `"type": "module"` in `package.json`,
breaking the CommonJS `postcss.config.js`/`prettier.config.js`.

## Licence

The documentation *content* is `imio.emailkit`'s: GPLv2, like the rest.
