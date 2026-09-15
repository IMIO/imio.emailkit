<div align="center">

<!-- Absolute raw URL rather than a relative path: this README is the PyPI long
     description too, and PyPI resolves no relative links. Pinned to `main`, so it
     renders once this lands there. -->
<img src="https://raw.githubusercontent.com/IMIO/imio.emailkit/main/docs/banner.png" alt="A transactional email rendered by imio.emailkit: the Délibérations.be masthead over a white card, an 'À relire' status pill, and a notification asking a section editor to review a page submitted for publication." width="640">

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

Transactional email templating for the iMio Plone ecosystem. Author HTML mails
with a modern toolchain — [Maizzle 6](https://maizzle.com) (Vue SFC + Tailwind
CSS 4) — and render them at runtime with Chameleon, so that **no Node.js ever
runs in production**.

Installing it restyles Plone's stock password-reset, registration and
username-reminder mails immediately. That is the point: the mails a citizen
actually receives from a commune are the ones nobody ever gets round to
designing.

## 📖 Documentation

**<https://imio.github.io/imio.emailkit/>**

Everything is there: the quickstart, the architecture, the full API reference,
the template-authoring rules, how to ship templates from your own add-on, and
how to override what this package ships.

Some entry points worth naming:

| | |
| --- | --- |
| [Quickstart](https://imio.github.io/imio.emailkit/quickstart/) | install, then send your first styled mail |
| [Architecture](https://imio.github.io/imio.emailkit/architecture/) | the build-time / runtime seam, and why |
| [`Email` builder](https://imio.github.io/imio.emailkit/api/email/) | recipients, attachments, per-language sending |
| [Authoring rules](https://imio.github.io/imio.emailkit/authoring/rules/) | eight ways a template breaks with a green build |
| [Shipping templates](https://imio.github.io/imio.emailkit/integration/shipping-templates/) | get your own add-on's templates discovered |
| [Migrating a mail](https://imio.github.io/imio.emailkit/integration/migrating/) | you already build HTML bodies |
| [Overrides & theming](https://imio.github.io/imio.emailkit/integration/overrides/) | three levels, plus a full opt-out |

## Installation

```shell
pip install imio.emailkit
```

Then install the add-on in Site Setup, or apply the `imio.emailkit:default`
GenericSetup profile — which restyles Plone's own transactional mails. Use
`imio.emailkit:base` for the runtime only.

> [!IMPORTANT]
> **Behind a reverse proxy, declare `trusted-proxy` in `zope.conf`**, or the
> login-help mails will name the proxy's own IP address instead of the client's.
> Why, and why the header is not read directly:
> [Installation & profiles](https://imio.github.io/imio.emailkit/installation/#behind-a-reverse-proxy).

```python
from imio.emailkit import Email

Email("imio.emailkit:notification").to(member).with_context(
    title=title, intro=intro, cta_url=url
).send()
```

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

## Contribute

- [Issue tracker](https://github.com/IMIO/imio.emailkit/issues)
- [Source code](https://github.com/IMIO/imio.emailkit/)
- [Contributing guide](https://imio.github.io/imio.emailkit/contributing/)

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

Run `make help` for every target. The ones you will reach for most: `make test`,
`make check` (format then lint), `make start`, `make create-site`,
`make build-emails`, `make check-emails`, `make preview-emails`.

## The design record

This README and the documentation site describe *what the package does*.
[`docs/DECISIONS.md`](docs/DECISIONS.md) describes *why*, and it is the authority
when the two disagree: every measured finding, every reverted attempt, every
"this looked like it worked".

Comments throughout the code cite a `SPEC.md` by section number (§4, §6.2, §7).
That file is no longer in the repository; the citations are kept as stable names
for the contracts they refer to, and DECISIONS.md is where the reasoning behind
each one actually lives.

[`SKILL.md`](SKILL.md) carries the authoring conventions for AI-assisted work,
which is how much of the template work here is done.

The documentation site itself lives in [`docs/site/`](docs/site) — see
[its README](docs/site/README.md) for how to add a page.

## License

The project is licensed under GPLv2.
