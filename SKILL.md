---
name: emailkit
description: Author, test and ship transactional email templates with imio.emailkit (Maizzle 6 + Chameleon, Plone). Use whenever you touch a .vue email template, a compiled .pt under templates/, an emails/ Maizzle project, a KitMain/KitButton/KitPanel/KitDataTable component, an imio.emailkit.templates entry point, a tests/fixtures/*.py or tests/golden/* snapshot, render()/render_shell()/Email(), or theme tokens (logo_url, primary_color, footer_html). Also use when an email renders wrong, ships raw ${...} placeholders, loses its CSS, or fails to parse at runtime.
---

# imio.emailkit — authoring emails

Two stages, one seam. **Build** (Node, dev/CI only): Maizzle 6 compiles
`emails/src/templates/*.vue` + Tailwind into email-safe HTML, renamed `.pt` and
**committed to git**. **Runtime** (Python only): Chameleon renders the committed
`.pt` with real data. Vue owns `{{ }}`, Chameleon owns `${ }`, so they never
collide.

You write `.vue`. Production renders `.pt`. Never hand-edit a `.pt`.

## Read this first: the build tells you almost nothing

Every rule below comes from a real failure in this project, and **every one of them
produced a successful build with exit code 0**. Maizzle catches its own errors and
ships. A browser preview looks fine. The mail is broken in the inbox, or the
template will not even parse at runtime.

The only trustworthy gates are the two in §7's CI contract:

1. **staleness** — `bin/check-emails --package <self>`: the committed `.pt` matches
   a fresh build.
2. **golden files** — rendering assertions on *substituted values*, never on marker
   strings.

If you change a template and do not run both, you do not know whether it works.

---

## The silent-failure catalogue

### 1. `${...}` in a literal `style` attribute kills CSS inlining document-wide

```html
<!-- WRONG. Build succeeds. -->
<td style="background-color: ${theme/primary_color}">

<!-- RIGHT -->
<td bgcolor="${primary_color}">
<td tal:attributes="style string:background-color: ${primary_color}">
```

Juice parses every `style` attribute as CSS, so `{` opens a block and the closing
`}` is eaten: the output is `style="background-color:${theme/primary_color"`, which
at runtime is not an expression at all, just broken text. Worse, **inlining stops
for the whole document**. Measured on one identical template: 31 inline styles with
the correct form, **6** with a single bad one. Nothing warns.

Prefer `bgcolor` for colours (never parsed as CSS, and the most bulletproof way to
colour a cell in mail anyway); use `tal:attributes="style string:…"` when you
genuinely need CSS.

### 2. `${...}` in a literal `class` attribute is corrupted

```html
<!-- WRONG -->
<td class="${row_class}">
```

`css.safe` rewrites selector-unsafe characters: `$` becomes `-` and the braces are
stripped. Separately, SPEC §3 rule 2 forbids **runtime-computed class values**
outright — Tailwind's scanner and `removeUnusedCSS` only see build-time markup, so
a class assembled at runtime has had its CSS purged before the mail is sent.
Conditional styling goes through `tal:attributes="style string:…"` with literal
values.

### 3. `--` anywhere in a comment makes the compiled `.pt` unparseable at runtime

Chameleon refuses `--` inside an HTML comment (`ParseError: The string '--' is not
allowed in a comment`). An ordinary em-dash-style authoring comment therefore breaks
the template **at render time**, long after a green build. Use `;` or a full stop.

The kit strips authoring comments in `afterTransform`, which makes this structurally
impossible in *your* comments — but the same rule applies to **ZCML and GenericSetup
XML**, which nothing strips. It has cost time four separate times, once blocking
instance startup.

A related trap: `<Outlook :open="…" />` with an **empty slot** emits
`<!--[endif]---->` — a `--` in a comment. Give `<Outlook>` real slot content, or use
`v-html`.

### 4. Naming the raw-escape component inside a comment swallows the real block

Maizzle extracts its raw/escape component with a naive global regex that also
matches **inside HTML comments**. Mentioning that component's name in angle
brackets in a comment silently swallows the real block and deletes it from the
output. Do not write component names in angle brackets inside comments.

### 5. No `i18n:domain` means `i18n:translate` renders the msgid untranslated

…and that is **indistinguishable from success**, because the msgid's default text
appears in the output either way. The kit's `Main.vue` declares
`i18n:domain="imio.emailkit"` on `<html>`, so kit strings translate.

**A nested `i18n:translate` inherits that domain.** If the msgid belongs to *your*
add-on's catalog, say so on your own element:

```html
<p i18n:domain="my.addon" i18n:translate="email_intro">Default text.</p>
```

Without the `i18n:domain`, your msgid is looked up in `imio.emailkit`'s catalog,
misses, and renders its default in every language. Snapshot two languages
(`languages = ("fr", "en")`) and a translation that stopped resolving shows up as
identical snapshots rather than as nothing at all.

### 6. `${helper(x)}` must be `${python: helper(x)}`

TAL **path** expressions cannot call functions. `${format_date(when)}` raises
`Invalid variable name`. This one fails loudly, but you will hit it constantly:

```html
<!-- WRONG -->  ${format_date(when)}
<!-- RIGHT -->  ${python: format_date(when)}
```

Same for `tal:content`: `tal:content="python: format_date(when)"`.

### 7. Theme tokens go via `tal:attributes` or `bgcolor`, never a literal `style`

SPEC §3 as originally written showed `style="background-color: ${theme/primary_color}"`.
That is failure 1. The amended rule is in `docs/DECISIONS.md`; the three tokens,
their registry records and the locked-kit model are unchanged.

### 8. A legacy body's own `<style>` block is dropped by Gmail and Outlook.com

`render_shell(subject, body_html)` injects legacy HTML into the shell's content
well, which is inside `<body>` — invalid placement for `<style>`, and Gmail and
Outlook.com strip it. The shell wraps and does **not** rewrite, so it will not hoist
the block into `<head>`. Inline `style="…"` attributes in the injected body survive
untouched: convert the block to inline styles before migrating. It looks perfect in
a browser preview, so you cannot discover this before real clients do.

### 9. A top-level SFC `<style>` block never reaches the email

Standard Vue semantics: the bundler extracts it. Purge then strips the
now-orphaned class from the `class` attribute too, so the markup silently loses
both rule and class. Custom CSS must be a real `<style>` **element** inside
`<template>`, or live in the kit's CSS entry.

### 10. `maizzle build` empties its output directory, silently

It has already deleted a committed hand-authored plaintext twin. Maizzle 6.0.7
exposes no `output.clean` / `emptyOutDir` option. So **hand-authored `.txt.pt`
twins live in `emails/twins/`** and are copied into `templates/` after the build.
Never keep the only copy of anything in an output directory.

### 11. Dark-mode rules keyed on a class are deleted by purge

`css.purge` models only `class=` and `id=`, so a class-keyed
`@media (prefers-color-scheme: dark)` rule is stripped with a successful build. The
kit keys dark mode on `data-dark="page|surface|body|muted"` **attribute** selectors,
which purge cannot see and therefore cannot remove. If you add a dark rule, key it
on an attribute.

### 12. A new `emails/` project with no `node_modules` ships uncompiled CSS

Tailwind resolves the `@import "@maizzle/tailwindcss"` that the shell emits by
walking up from the **template's** directory. With no `node_modules` ancestor the
resolution fails, **Maizzle catches the CSS error and exits 0**, and the build
prints "Built 1 template". Measured on one template: 5.3 KB of output with inlined
styles becomes 3.5 KB with none. Same root cause as the kit's own no-bare-imports
rule — the kit lives in a Python egg, and `site-packages` has no `node_modules`
above it.

So: if a rebuild's output suddenly gets much smaller, check for inline `style`
attributes before anything else. `MIN_INLINE_STYLES`-style assertions exist for
this reason.

### 13. Injected names beat your context

`render()` injects `theme`, `lang`, `target_language`, `portal_url`, `translate`,
`format_date`, `format_datetime`, `format_number` — and those win over keys of the
same name in your context, because the kit layout uses them unconditionally. Do not
name a context key `theme`, `lang` or `preheader`; `preheader` comes from the
registration, not from the caller.

---

## Authoring rules (enforced by the lint in `bin/check-emails`)

| Rule | Why |
|---|---|
| No `tal:` / `i18n:` attributes **on a kit component** | Vue attribute fallthrough lands them on whichever element happens to be the component's root. Put them on your own `<tr>` / `<div>` instead. |
| No runtime-computed `class` values | Tailwind purge only sees build-time markup. |
| No `${...}` in a literal `class` or `style` attribute, ever | Failures 1 and 2. |
| `alt` on every image | RGAA applies to iMio's clients; the lint fails without it. |
| `structure` only for `body_html` and `footer_html` | `${...}` is HTML-escaped by default, and that default is right. |
| No `--` in any comment, anywhere in the repo | Failure 3, and it reaches ZCML and XML too. |
| Kit files and `.vue` templates stay **import-free** of bare specifiers | The kit ships inside a Python egg, and a `site-packages` directory has no `node_modules` ancestor for Vite to walk up to. Maizzle auto-imports every component. |

`structure` is safe from template injection: Chameleon compiles the *template*, and
an injected string is inserted as markup data that is never re-parsed as TAL —
verified, including `${python: __import__(…)}` in a body. It is still inserted
**unescaped**, which is the entire point of the slot.

### Run the lint

```bash
python -m imio.emailkit.lint emails/          # or any .vue file / directory
python -m imio.emailkit.lint --list-rules     # what each rule catches, and the fix
```

Eight rules, each one a failure from the catalogue above:
`tal-on-component`, `runtime-class`, `style-placeholder`, `class-placeholder`,
`missing-alt`, `comment-double-dash`, `raw-in-comment`, `path-call`. It is gate 2
of `bin/check-emails`, so CI runs it whether you do or not.

---

## Kit component catalog

The kit is **locked**: compose these, do not extend the Tailwind config. Components
are auto-imported and prefixed `Kit`.

### `<KitMain>` — the shell (`layouts/Main.vue`)

Wrap every template in it. It owns the whole document and you never write any of
this yourself: `<html lang="${lang}">`, charset/viewport/format-detection/colour-scheme
meta, the MSO document settings, `i18n:domain`, `role="presentation"` on layout
tables, the dark-mode `<style>`, the hidden preheader div, the logo header with an
enforced translatable `alt`, the `primary_color` rule, the content well, the
`footer_html` footer with a translated default, and the `body_html` injection point.

```html
<template>
  <KitMain>
    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${title}</h1>
    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${intro}</p>
  </KitMain>
</template>
```

It also exposes a named `preheader` slot, a **build-time** fallback for templates a
stock Plone view renders (they never see `render()`'s context). The runtime msgid
from the registration always wins when present.

### `<KitButton href align>` — the call to action

A single-cell table, not a padded `<a>`: cell padding is the one padding every
client including Outlook honours. `href` takes a `${...}` placeholder (`href` is not
CSS). `align` is `left` | `center` | `right`. Colour comes from `primary_color`,
which the shell defines — so it only works inside `<KitMain>`.

```html
<div tal:condition="cta_url | nothing">
  <KitButton href="${cta_url}" align="center">${cta_label}</KitButton>
</div>
```

Note the `tal:condition` on a plain `<div>`, not on the component.

### `<KitPanel tone>` — a tinted callout

`tone` is `neutral` (default) or `accent`. Resolved at **build** time, so the class
strings are literal in the output. Magenta is high-signal at iMio: use `accent` for
the one thing the reader must not miss.

```html
<KitPanel tone="accent"><strong>${python: format_date(when)}</strong></KitPanel>
```

### `<KitDataTable>` — table chrome for real tabular data

The one table in the kit that is **not** `role="presentation"` — marking a data
table as presentational hides its structure from screen readers. Rows are yours,
because `tal:` may not go on the component:

```html
<KitDataTable>
  <template #head>
    <th scope="col" class="border border-solid border-imio-grey-border p-2 text-left text-sm">Point</th>
    <th scope="col" class="border border-solid border-imio-grey-border p-2 text-left text-sm">Decision</th>
  </template>
  <tr tal:repeat="row rows">
    <td class="border border-solid border-imio-grey-border p-2 text-sm">${row/title}</td>
  </tr>
</KitDataTable>
```

Header cells want `scope="col"`; the kit cannot add it, the cells come from the slot.

### Theme tokens

Three runtime-variable branding values, from `plone.app.registry`. Everything else
is Tailwind, fixed at build time.

| Token | Registry record |
|---|---|
| `logo_url` | `imio.emailkit.theme.logo_url` |
| `primary_color` | `imio.emailkit.theme.primary_color` |
| `footer_html` | `imio.emailkit.theme.footer_html` |

The shell defines them; read them as `${primary_color}` inside `bgcolor` or
`tal:attributes`, never in a literal `style`.

---

## Registration (SPEC §4)

One entry point per add-on, pointing at a module-level dict:

```toml
# pyproject.toml
[project.entry-points."imio.emailkit.templates"]
"my.addon" = "my.addon:emailkit"
```

```python
# my/addon/__init__.py
from zope.i18nmessageid import MessageFactory

_ = MessageFactory("my.addon")

emailkit = {
    "directory": "templates",          # relative to this package; this is the default
    "templates": {
        "item_published": {
            "subject": _("email_subject_item_published", default="Item published"),
            "preheader": _("email_preheader_item_published", default="…"),  # optional
        },
    },
}
```

- Lookups are namespaced: `my.addon:item_published`. The bare basename resolves to
  nothing, on purpose — two add-ons will eventually both ship `item_published`.
- **The subject lives in the registration**, as a msgid, translated per recipient
  language at send time. Not in the template, not in a sidecar.
- **Always pass `default=`.** Without it an untranslated subject reaches the inbox
  as the bare msgid.
- `preheader` is the hidden inbox-preview line, the highest-visibility email
  feature everyone forgets. Every inbox shows it; omitted, the client fills it with
  whatever body copy comes first. Keep it under ~100 characters.
- `MANIFEST.in`: `recursive-include …/templates *.pt` **and** `prune …/emails`.

Overrides need no new mechanism: `z3c.jbot` works on the resolved `.pt`. A site
layer that overrides ours must **extend** `IEmailkitLayer` — for a *sibling* layer
precedence is effectively arbitrary.

---

## Plaintext twins

`<name>.txt.pt` is the plaintext half, hand-authored, source-controlled in
`emails/twins/`, copied into `templates/` after the build.

**Never generate one.** Maizzle's plaintext output keeps `${}` but destroys every
`tal:`/`i18n:` construct: conditionals vanish, header lines come out empty,
`i18n:translate` freezes at the English default. A generated twin ships a
plausible-looking body with the wrong content in the wrong language.

Without a twin, §4's naive extraction runs, warns once at startup, logs a
deprecation — and **drops every link**, because the URL lives in an `<a href>` the
extraction throws away. Any template with a call to action wants a twin.

```html
<tal:body
  ><span tal:omit-tag="" tal:content="title" />

<tal:rows tal:repeat="row rows">* <span tal:omit-tag="" tal:content="row/title" />
</tal:rows>
<span tal:omit-tag="" tal:content="cta_label" /> :
<span tal:omit-tag="" tal:content="cta_url" />
</tal:body>
```

A twin is a **template**: keep the placeholders, they run at send time.
`tal:omit-tag=""` is how you emit text without emitting tags — a stray real tag
reaches a plaintext reader as literal markup.

---

## The fixture / golden workflow

```
tests/
├── test_emails.py               # 4 lines
├── fixtures/item_published.py   # CONTEXT = {...}
└── golden/
    ├── item_published.fr.html
    ├── item_published.fr.txt
    ├── item_published.en.html
    └── item_published.en.txt
```

```python
# tests/test_emails.py -- the whole suite
from imio.emailkit.golden import GoldenTemplateTests


class TestEmailGoldens(GoldenTemplateTests):
    package = "my.addon"
    templates = ("item_published",)
```

```python
# tests/fixtures/item_published.py
CONTEXT = {
    "title": "Séance du conseil communal du 12 août",
    "when": "2026-08-12T19:30:00",          # ISO string; format_date coerces it
    "rows": [{"title": "Budget 2026", "decision": "approuvé"}],
}
```

Rules that make the fixture worth having:

- **One key per `${...}`, and no more.** The fixture is the contract: add a
  placeholder without adding the key and the golden test fails loudly. That is the
  feature.
- **Omit what `render()` injects** — `lang`, `theme` and its tokens, `preheader`.
  Pinning them hides a broken injection and pins every snapshot to one language.
- **Plain data, not objects.** A plain Python instance needs
  `__allow_access_to_unprotected_subobjects__` before `${item/title}` traverses;
  mappings and ISO strings just work.
- **Include non-ASCII text.** A charset regression shows up nowhere else.
- **Cover both branches of a `tal:condition`** across your fixtures: one that
  supplies `cta_url` and one that does not.

The same fixtures feed `bin/preview-emails` and `@@emailkit-preview`, so keeping
them realistic is not cosmetic.

### Regenerating snapshots

Deliberate, never a side effect of a failure:

```bash
EMAILKIT_UPDATE_GOLDEN=1 pytest tests/ -q -rs   # writes, reports every one as skipped
git diff                                        # review before committing
```

A snapshot that repairs itself when it breaks is not a snapshot. The harness also
audits the *committed* snapshot for raw `${...}`, so a regeneration run on a broken
engine cannot bake a placeholder in and be confirmed for ever.

---

## Runtime API

```python
from imio.emailkit import Email, render, render_shell

html, text = render("my.addon:item_published", context={"item": item}, language="fr")

Email("my.addon:item_published") \
    .to(member).to("greffe@commune.be").cc(managers) \
    .reply_to("noreply@imio.be") \
    .with_context(item=item) \
    .attach(pdf, filename="convocation.pdf") \
    .send()
```

- The builder holds data and does not grow behaviour. Nine methods, frozen: `to`,
  `cc`, `bcc`, `reply_to`, `sender`, `subject`, `with_context`, `attach`, `send`.
- Recipients accept, in any mix: an address, a member, a userid, or an iterable.
  `.send()` **groups by resolved language** and renders once per group, so FR/NL
  communes need no caller effort. There is no per-send language argument, by design.
- Unresolvable recipients, zero recipients, a missing subject, an unset
  `plone.email_from_address`, and unguessable attachment metadata all raise at
  `.send()`. Fail loud, never silent drop.
- Delivery is **queued**: an aborted transaction sends nothing.
  `.send(immediate=True)` is the escape hatch.
- Migrating existing mail code: `render_shell(subject, body_html)` wraps a legacy
  body in the kit shell with no template work. Or keep the builder and pass the
  legacy markup as `body_html` in the context of a registered template — the layout
  defines that slot for every template, and that route keeps the registration's
  subject, the preheader and the hand-authored twin.

## Templates a stock Plone view renders (jbot overrides)

The restyled password-reset and registration mails are the documented exception.
They are rendered by a stock view, so:

- view kwargs land in **`options`**, not at top level: `${options/member}`;
- `MemberData` is **not path-traversable at all** — `${member/email}` raises, use
  `${python: member.getProperty('email')}`;
- there are **no locale helpers** and no `theme` in that namespace (the shell reaches
  the registry through `@@emailkit_theme` instead);
- the subject is emitted by the template as its own `Subject:` header, and needs
  `tal:omit-tag=""` on the `i18n:translate` span, or the header ships as
  `Subject: <span>Reset your password</span>`.

These cannot go through `render()` and are not registered for discovery. Do not copy
their dialect into an ordinary template.

## Checklist before you commit

- [ ] `.vue` changed → **rebuild** and commit the `.pt` (never edit the `.pt`)
- [ ] no `${...}` in a literal `class` or `style`; colours on `bgcolor`
- [ ] no `tal:` / `i18n:` on a kit component
- [ ] no `--` in any comment
- [ ] `i18n:domain` on your own element for your own msgids
- [ ] helpers called as `${python: …}`
- [ ] `alt` on every image
- [ ] fixture updated for every new placeholder
- [ ] twin updated, in `emails/twins/`
- [ ] snapshots regenerated deliberately and the diff reviewed
- [ ] staleness gate green, golden gate green
