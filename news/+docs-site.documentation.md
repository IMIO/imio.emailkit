Publish the developer documentation as a site at
<https://imio.github.io/imio.emailkit/>, built from `docs/site/` and deployed by a
new `docs.yml` workflow on every push to `main` that touches it. Twenty pages
covering the quickstart, the architecture, the full runtime API, the eight authoring
rules, the fixture/golden workflow, entry-point distribution, the content-rule action,
the `render_shell` migration routes and the three override levels. Adding a page is an
MDX file plus one line in the navigation array; search, the per-page section nav and
the previous/next links all follow from that. `README.md` is now the pitch and a link
to the site, so no topic has two homes; `SPEC.md` and `docs/DECISIONS.md` remain the
authority on *why*.
