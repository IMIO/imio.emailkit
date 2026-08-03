# imio.emailkit — documentation site

The developer documentation published at **<https://imio.github.io/imio.emailkit/>**.

A [Next.js](https://nextjs.org) app built on the [Tailwind Plus](https://tailwindcss.com/plus)
*Protocol* template, exported as static HTML and deployed by
[`.github/workflows/docs.yml`](../../.github/workflows/docs.yml).

## Working on it

```shell
cd docs/site
npm install
npm run dev        # http://localhost:3000
```

`npm run build` produces the static export in `out/`. `npm run lint` is what CI gates on.

## Adding a page

Two steps.

1. Create `src/app/<slug>/page.mdx`, starting with the metadata export:

   ```mdx
   export const metadata = {
     title: 'My page',
     description: 'One sentence — this is the meta description.',
   }

   # My page

   The opening paragraph, styled as a lead. {{ className: 'lead' }}

   ## A section
   ```

2. Add one line to the `navigation` array in
   [`src/components/Navigation.jsx`](src/components/Navigation.jsx).

That is all. Three things then happen on their own:

- **The sidebar sub-nav** is generated from the page's `##` headings by the rehype
  plugin in `src/mdx/rehype.mjs`. There is no `sections` export to maintain.
- **Search** indexes the page. `src/mdx/search.mjs` is a webpack loader that globs
  `src/app/**/*.mdx` at build time and feeds FlexSearch. No configuration.
- **Previous/next links** at the foot of the page come from the same `navigation`
  array, walked flat, top to bottom. So group order is reading order.

## MDX components available in a page

No imports needed — they come from `src/components/mdx.jsx`.

| Component | Use |
| --- | --- |
| `<Note>` | A highlighted aside. Prose inside works, including links and code. |
| `<Properties>` / `<Property name type>` | The definition lists used on the API pages. |
| `<CodeGroup>` | Tabbed code blocks; put several fences inside it. |
| `<Button href variant arrow>` | A call-to-action outside prose. Wrap the label in `<>…</>`. |
| `<Row>` / `<Col>` | Two-column layout on wide screens. |

Fenced code blocks get syntax highlighting, a language tag and a copy button
automatically. Annotate one with `` ```python {{ title: 'setup.py' }} ``.

Headings take annotations too: `## Section {{ anchor: false }}` keeps the heading out
of the sidebar sub-nav.

## Deployment

`.github/workflows/docs.yml`:

- **Any push or pull request touching `docs/site/**`** builds and lints. A page that
  fails to render is caught before merge.
- **A push to `main`** additionally deploys to GitHub Pages.
- The workflow can be run by hand from the Actions tab.

### The one piece of manual setup

**Settings → Pages → Source must be set to "GitHub Actions".** Without it the deploy
job fails; there is no way to set it from a workflow.

### `basePath`

The site is served from a repository subpath, so `next.config.mjs` reads `basePath`
from the `NEXT_BASE_PATH` environment variable — set to `/<repo-name>` by the workflow,
and unset locally so `npm run dev` serves from the root. Nothing hardcodes the URL.

`trailingSlash: true` makes the export write `out/quickstart/index.html` rather than
`out/quickstart.html`. That is what `src/lib/usePagePathname.js` exists to compensate
for: `usePathname()` then reports `/quickstart/`, while the `navigation` array is keyed
`/quickstart`. **Compare a route against a page href through that hook, never through
`usePathname()` directly** — getting it wrong silently breaks the active-page highlight,
the sub-nav and the footer links, with no error.

## Where content belongs

This site is the source of truth for **developer documentation** — how to use the
package. Two files in the repository root are the source of truth for **why it is
built this way**, and the site links to them rather than restating them:

- [`SPEC.md`](../../SPEC.md) — goals, non-goals, architecture, phasing, and what was
  explicitly rejected.
- [`docs/DECISIONS.md`](../DECISIONS.md) — the decision record: measured findings,
  reverted attempts, and the things that looked like they worked.

The root [`README.md`](../../README.md) is deliberately short: badges, the pitch,
`pip install`, and a link here. Prose that belongs on a page here should not be
duplicated there.

## Divergences from the stock Protocol template

Worth knowing before you `diff` against a fresh copy of the template:

- **`src/components/Code.jsx`** — `CodePanel` no longer calls `Children.only()`. It
  crashed the prerender of a page whose markup was byte-identical to a page that built
  fine, because webpack handed the client-component child over as a lazy module
  reference on one chunk boundary and not the other. The `code` prop is already set by
  the rehype plugin, so the assertion bought nothing.
- **`typography.js`** — `@screen sm` / `@screen lg` replaced with plain media queries.
  `@screen` was removed in Tailwind 4, and an unknown at-rule is dropped with only a
  build warning, so those negative margins were silently not applied.
- **`src/components/PageActions.jsx`** — replaces the template's "Was this page
  helpful?" widget, which posted nowhere and on a static export could only thank you
  and discard the answer. It links to the page's source and to a new issue instead.
- **`src/lib/project.js`** — the repository and PyPI URLs, in one place.
- The `emerald-*` accent throughout is now `accent-*`, defined once in
  `src/styles/tailwind.css` from the iMio brand magenta.

One known warning is left as-is: Node reports `MODULE_TYPELESS_PACKAGE_JSON` for
`typography.js`. Silencing it means adding `"type": "module"` to `package.json`, which
would break `postcss.config.js` and `prettier.config.js` — both CommonJS. It is
cosmetic.

## Licence

The Protocol template is a commercial product under the
[Tailwind Plus licence](LICENSE.md), whose allowed-usage list explicitly covers this
case: a free and open-source web application, source publicly available, whose primary
purpose is clearly not to redistribute the components.

Note that it is a **single-individual** licence. Each developer who works on the files
under `docs/site/` needs their own Tailwind Plus seat.

The documentation *content* is part of `imio.emailkit` and is GPLv2, like the rest of
the repository.
