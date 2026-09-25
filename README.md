<div align="center">

<!-- Absolute URL: PyPI uses this as its long description; relative links
     don't resolve. Pinned to `main`. -->
<img src="https://raw.githubusercontent.com/IMIO/imio.emailkit/main/docs/banner.png" alt="A transactional email from imio.emailkit: masthead, status pill, and review notification." width="640">

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
[![Docs](https://github.com/IMIO/imio.emailkit/actions/workflows/docs.yml/badge.svg)](https://github.com/IMIO/imio.emailkit/actions/workflows/docs.yml)
![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-000000)

[![GitHub contributors](https://img.shields.io/github/contributors/IMIO/imio.emailkit)](https://github.com/IMIO/imio.emailkit)
[![GitHub Repo stars](https://img.shields.io/github/stars/IMIO/imio.emailkit?style=social)](https://github.com/IMIO/imio.emailkit)

</div>

Transactional email templating for iMio's Plone ecosystem: author HTML
mails with [Maizzle 6](https://maizzle.com) (Vue SFC + Tailwind CSS 4),
rendered at runtime by Chameleon. **No Node.js runs in production.**

Installing it restyles Plone's password-reset, registration and
username-reminder mails.

## Documentation

**<https://imio.github.io/imio.emailkit/>**

Covers the quickstart, architecture, API reference, authoring rules,
shipping, and overrides:

| | |
| --- | --- |
| [Quickstart](https://imio.github.io/imio.emailkit/quickstart/) | install, send a mail |
| [Architecture](https://imio.github.io/imio.emailkit/architecture/) | the build-time / runtime seam |
| [`Email` builder](https://imio.github.io/imio.emailkit/api/email/) | recipients, attachments, per-language |
| [Authoring rules](https://imio.github.io/imio.emailkit/authoring/rules/) | eight ways to silently break a template |
| [Shipping templates](https://imio.github.io/imio.emailkit/integration/shipping-templates/) | get your templates discovered |
| [Migrating a mail](https://imio.github.io/imio.emailkit/integration/migrating/) | already building HTML bodies |
| [Overrides & theming](https://imio.github.io/imio.emailkit/integration/overrides/) | three levels, full opt-out |

## Installation

```shell
pip install imio.emailkit
```

Install the add-on in Site Setup, or apply `imio.emailkit:default` for
Plone's transactional mails; `imio.emailkit:base` is runtime-only.

> [!IMPORTANT]
> **Behind a reverse proxy, declare `trusted-proxy` in `zope.conf`** — otherwise
> login-help mails show the proxy's IP, not the client's:
> [Installation & profiles](https://imio.github.io/imio.emailkit/installation/#behind-a-reverse-proxy).

```python
from imio.emailkit import Email

Email("imio.emailkit:notification").to(member).with_context(
    title=title, intro=intro, cta_url=url
).send()
```

## Compatibility

Plone 6.0–6.2 on Python 3.10–3.13.

> [!IMPORTANT]
> **Classic UI only**: no Volto component, no REST endpoint; rendering lives
> in `imio.emailkit.render`, independent of the request. Building templates
> needs Node.js 22+; installing, testing, and *running* the add-on do not.

## Contribute

- [Issue tracker](https://github.com/IMIO/imio.emailkit/issues)
- [Source](https://github.com/IMIO/imio.emailkit/)
- [Contributing guide](https://imio.github.io/imio.emailkit/contributing/)

### Prerequisites

-   An [operating system](https://6.docs.plone.org/install/create-project-cookieplone.html#prerequisites-for-installation) meeting these requirements.
-   [uv](https://6.docs.plone.org/install/create-project-cookieplone.html#uv)
-   [Make](https://6.docs.plone.org/install/create-project-cookieplone.html#make)
-   [Git](https://6.docs.plone.org/install/create-project-cookieplone.html#git)
-   [Node.js](https://nodejs.org) 22+, **only** for building templates

### Installation

1.  Clone this repository and enter it.

    ```shell
    git clone git@github.com:IMIO/imio.emailkit.git
    cd imio.emailkit
    ```

2.  Install it.

    ```shell
    make install
    ```

`make help` lists every target; common ones: `make test`, `make check`
(format then lint), `make start`, `make create-site`, `make build-emails`,
`make check-emails`, `make preview-emails`.

## Working on the docs

[`SKILL.md`](SKILL.md) covers authoring conventions for AI-assisted work;
the documentation site lives in [`docs/site/`](docs/site) — see
[its README](docs/site/README.md) to add a page.

## License

Licensed under GPLv2.
