<div align="center">
    <h1 align="center">imio.emailkit</h1>
</div>
<div align="center">

[![PyPI](https://img.shields.io/pypi/v/imio.emailkit)](https://pypi.org/project/imio.emailkit/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/imio.emailkit)](https://pypi.org/project/imio.emailkit/)
[![PyPI - Wheel](https://img.shields.io/pypi/wheel/imio.emailkit)](https://pypi.org/project/imio.emailkit/)
[![PyPI - License](https://img.shields.io/pypi/l/imio.emailkit)](https://pypi.org/project/imio.emailkit/)
[![PyPI - Status](https://img.shields.io/pypi/status/imio.emailkit)](https://pypi.org/project/imio.emailkit/)


[![PyPI - Plone Versions](https://img.shields.io/pypi/frameworkversions/plone/imio.emailkit)](https://pypi.org/project/imio.emailkit/)

[![CI](https://github.com/IMIO/imio.emailkit/actions/workflows/main.yml/badge.svg)](https://github.com/IMIO/imio.emailkit/actions/workflows/main.yml)
![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-000000)

[![GitHub contributors](https://img.shields.io/github/contributors/IMIO/imio.emailkit)](https://github.com/IMIO/imio.emailkit)
[![GitHub Repo stars](https://img.shields.io/github/stars/IMIO/imio.emailkit?style=social)](https://github.com/IMIO/imio.emailkit)

</div>

Transactional email templating for the iMio Plone ecosystem. Author HTML mails
with a modern toolchain — [Maizzle 6](https://maizzle.com) (Vue SFC + Tailwind
CSS 4) — and render them at runtime with Chameleon, so that **no Node.js ever
runs in production**.

Installing it restyles Plone's stock password-reset and registration mails
immediately. That is the point: the mails a citizen actually receives from a
commune are the ones nobody ever gets round to designing.

## Features

- **Better defaults out of the box.** The `imio.emailkit:default` profile
  restyles Plone's password-reset and user-registration mails, with no extra
  package and no opt-in step.
- **A two-stage pipeline with a build-time seam.** Maizzle compiles `.vue` into
  email-safe HTML (inlined CSS, Outlook fallbacks, dark mode); the output is
  committed as `.pt` and rendered by Chameleon at runtime. Node is a
  developer/CI tool only.
- **A built-in design system** — one canonical layout plus components — shipped
  *inside the egg*, so the buildout pin that governs the runtime governs the
  design system too. No npm registry, no version skew.
- **`render(name, context, language)`** returning `(html, text)`: a pure
  function of template, context and registry state, so previews, tests and real
  sends all take the same path.
- **Locale-aware helpers** (`format_date`, `format_datetime`, `format_number`)
  bound to the render language, so no template reinvents French date formatting.
- **Accessibility and i18n baked into the kit**, not left to authors:
  `role="presentation"` on layout tables, an enforced `alt` on the logo, `lang`
  on `<html>`, and the hidden preheader line every inbox shows next to the
  subject.
- **Three levels of override**, from a registry record to a full markup
  replacement, plus a complete opt-out.

## Compatibility

Plone 6.0, 6.1 and 6.2 on Python 3.10 to 3.13.

> [!IMPORTANT]
> **Classic UI only, and deliberately so.** These are emails: there is no Volto
> component and no REST endpoint to write. Rendering is isolated in
> `imio.emailkit.render`, which has no dependency on the request.

> [!NOTE]
> Building templates needs Node.js 22+. Installing, testing and *running* the
> add-on never does — that is the whole architecture. If you only consume the
> mails it ships, you will never install Node.

## Installation

```shell
pip install imio.emailkit
```

Then install the add-on in Site Setup, or apply the `imio.emailkit:default`
GenericSetup profile.

### The two profiles

| Profile | Installs | Use it when |
| --- | --- | --- |
| `imio.emailkit:default` | the runtime **and** the restyled Plone default mails | almost always |
| `imio.emailkit:base` | the runtime only; stock Plone mails are untouched | you want the API without the restyled defaults |

`:default` extends `:base`, so installing it gives you both.

> [!WARNING]
> On a `:base`-only site, Site Setup lists `imio.emailkit` as *available* rather
> than *installed*. Plone's quick-installer answers "has the `default` profile
> been applied?", not "is this add-on working?" — the add-on is installed and its
> API works. Check `imio.emailkit:base` in `portal_setup` if you need certainty.

## Sending a mail

```python
from imio.emailkit import render

html, text = render(
    "imio.emailkit:mail_password_template",
    context={"member": member, "reset_url": url},
    language="fr",
)
```

`render()` injects the theme tokens, the render language as `lang`, and the
locale helpers. It returns both parts of a `multipart/alternative` body; what you
do with them is yours until the `Email` builder lands.

## Shipping templates from your own add-on

Declare one entry point:

```python
entry_points = {
    "imio.emailkit.templates": [
        "imio.pm.notifications = imio.pm.notifications:emailkit",
    ],
}
```

pointing at a module-level dict:

```python
emailkit = {
    "directory": "templates",  # relative to the package
    "templates": {
        "item_published": {
            "subject": _("email_subject_item_published"),
            "preheader": _("email_preheader_item_published"),  # optional
        },
    },
}
```

Names are namespaced at lookup: `imio.pm.notifications:item_published`. The
**subject lives in the registration** as an i18n msgid, translated per recipient
language — there is no metadata sidecar and no front-matter round-trip. An
unknown name raises `TemplateNotFound` carrying the list of names that *are*
registered.

Each template ships two compiled files, `<name>.pt` and `<name>.txt.pt`, plus a
fixture and a golden snapshot under `tests/`.

## Extending

### 1. Replace the markup, per site or per client

Register your own `z3c.jbot` directory on your site package's browser layer.

> [!IMPORTANT]
> **Your layer must `extend` `IEmailkitLayer`.** "More specific layer wins" is
> only true for a layer that subclasses ours. For a *sibling* layer, z3c.jbot
> precedence follows `ILocalBrowserLayerType` registration order, which is
> effectively arbitrary — it will work on your machine and lose in production.

```python
from imio.emailkit.interfaces import IEmailkitLayer


class IMyCommuneLayer(IEmailkitLayer):
    """This commune's browser layer."""
```

```xml
<include package="z3c.jbot" />
<browser:jbot directory="overrides" layer=".interfaces.IMyCommuneLayer" />
```

Override files are named after the dotted path of the file they shadow, e.g.
`Products.CMFPlone.browser.login.templates.mail_password_template.pt`.

> [!WARNING]
> Include the **package** `z3c.jbot`, never just its `meta.zcml`. `meta.zcml`
> registers the directive but not the monkeypatches that make an override
> effective, so with it alone the directive parses, the path mapping is correct,
> and the stock template still renders — with no error and no warning.

### 2. Adjust the branding only

Three `plone.app.registry` records, which covers most per-commune needs without
touching any markup:

| Record | Used by |
| --- | --- |
| `imio.emailkit.theme.logo_url` | the layout header |
| `imio.emailkit.theme.primary_color` | buttons, header rule |
| `imio.emailkit.theme.footer_html` | the layout footer |

The design system itself is **locked**: consumers compose the layout and
components but do not extend the Tailwind config. That is what keeps every iMio
product's mails recognisably the same.

### 3. Opt out entirely

Install `imio.emailkit:base` instead of `:default`. You keep the API, the
discovery and the kit; Plone's own mails are left exactly as they were.

## Authoring templates

Sources live in `emails/src/templates/*.vue` and compile to `.pt`. Four rules,
all of them learned from failures that produced a *successful build*:

1. **No `tal:`/`i18n:` attributes on kit components.** Attribute fallthrough
   lands them on unpredictable root elements. Author dynamic regions as plain
   `<tr>`/`<td>` markup.
2. **No Chameleon placeholder in a literal `class` or `style` attribute, ever.**
   In `class`, Tailwind's `safe` transform rewrites `${item/css_class}` into
   `-item-css_class`. In `style`, the CSS inliner reads the `{` as a block, eats
   the closing brace **and stops inlining for the whole document** — one such
   attribute took a template from 31 inline styles to 6, build green. Use
   `tal:attributes="style string:…"`.
3. **Escape what must survive the Vue compiler** with `v-pre` (one element) or
   `<Raw>` (a block). To reach the inbox as literal text a placeholder also needs
   Chameleon-level escaping: `$${...}`.
4. **`structure` is reserved** for the shell's `body_html` slot and
   `footer_html`. Everything else is HTML-escaped, which is the safe default.

```shell
make build-emails      # compile emails/ into the package; commit the .pt files
make check-emails      # the staleness gate CI runs
make preview-emails    # render the committed templates with the committed fixtures
```

`make preview-emails` renders through `render()` inside a real Plone site, with a
language switcher. It is deliberately **not** Maizzle's `--watch`, which shows
build-time output — raw `${item/title}` and unexpanded `tal:repeat` — rather than
the mail anyone will receive.

## Testing

```shell
make test              # the whole suite
make update-golden     # regenerate the snapshots, deliberately
```

Every template has a fixture (`tests/fixtures/<name>.py`) and a snapshot
(`tests/golden/<name>.<lang>.html` / `.txt`). The golden tests catch the two
regressions that nothing else does: a Tailwind class silently purged at build,
and a `${}` placeholder that stopped resolving after a refactor.

> [!IMPORTANT]
> Snapshots are regenerated **only** by `make update-golden`, never as a side
> effect of a failing comparison. A snapshot that repairs itself when it breaks
> is not a snapshot.

Two rules for anyone adding a test here:

- **Assert on substituted values, never on marker strings.** Without the
  `IPageTemplateEngine` utility, `zope.pagetemplate` falls back to `zope.tal`,
  where `${...}` passes through verbatim and raises nothing — so a test that
  only checks "our marker is present" stays green while raw placeholders ship.
- **Assert on rendered output, never only that a file was resolved.** See the
  `meta.zcml` warning above.

## Translations

French, Dutch and German. Source labels are in English.

> [!NOTE]
> A missing `i18n:domain` makes every `i18n:translate` render its msgid's default
> text — which is *indistinguishable from success*, because the English default
> appears either way. The kit's layout emits `i18n:domain` so no author has to
> remember it, and the test suite asserts that FR and NL output actually differ.

## Contribute

- [Issue tracker](https://github.com/IMIO/imio.emailkit/issues)
- [Source code](https://github.com/IMIO/imio.emailkit/)

### Prerequisites ✅

-   An [operating system](https://6.docs.plone.org/install/create-project-cookieplone.html#prerequisites-for-installation) that runs all the requirements mentioned.
-   [uv](https://6.docs.plone.org/install/create-project-cookieplone.html#uv)
-   [Make](https://6.docs.plone.org/install/create-project-cookieplone.html#make)
-   [Git](https://6.docs.plone.org/install/create-project-cookieplone.html#git)
-   [Node.js](https://nodejs.org) 22+ — **only** to build email templates

### Installation 🔧

1.  Clone this repository, then change your working directory.

    ```shell
    git clone git@github.com:IMIO/imio.emailkit.git
    cd imio.emailkit
    ```

2.  Install this code base.

    ```shell
    make install
    ```

Useful targets: `make test`, `make test-coverage`, `make check` (format then
lint), `make i18n` (update the catalogs), `make start`, `make create-site`
(`PROFILE=base make create-site` for a site with the opt-out).

### Add features using `plonecli` or `bobtemplates.plone`

This package provides markers as strings (`<!-- extra stuff goes here -->`) that are compatible with [`plonecli`](https://github.com/plone/plonecli) and [`bobtemplates.plone`](https://github.com/plone/bobtemplates.plone).

```shell
make add <template_name>
```

## License

The project is licensed under GPLv2.
