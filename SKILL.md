---
name: emailkit
description: Author, test and ship transactional email templates with imio.emailkit (Maizzle 6 + Chameleon, Plone). Use for a .vue email template, a compiled .pt under templates/, an emails/ Maizzle project, a KitMain/KitPill/KitCard/KitDataList/KitDataRow/KitButton/KitButtonGroup/KitPanel/KitDataTable component, an <emailkit:templates> ZCML registration, a tests/fixtures/*.py or tests/golden/* snapshot, render()/render_shell()/Email(), or theme tokens (logo_url, primary_color, footer_html). Also use when an email renders wrong, ships a raw ${...} placeholder, loses CSS, or fails to parse at runtime.
---

# imio.emailkit — authoring emails

**Build** (Node, dev/CI only): Maizzle 6 compiles `emails/src/templates/*.vue`
+ Tailwind into email-safe HTML, renamed `.pt` and **committed to git**.
**Runtime** (Python only): Chameleon renders the committed `.pt` with real
data. Vue owns `{{ }}`; Chameleon owns `${ }`. They never collide.

You write `.vue`. Production renders `.pt`. Never hand-edit a `.pt`.

## Read this first: the build tells you almost nothing

Every rule below is a real failure that still built with exit code 0 —
Maizzle misses these errors, and a browser preview looks fine. The mail
breaks in the inbox, or fails to parse at runtime.

Only two checks prove a template works:

1. **staleness** — `bin/check-emails --package <self>`: the committed `.pt`
   matches a fresh build.
2. **golden files** — check rendered output against real substituted values,
   not marker strings.

Run both after every change.

---

## The silent-failure catalogue

### 1. `${...}` in a literal `style` kills CSS inlining

```html
<!-- WRONG. Build succeeds. -->
<td style="background-color: ${theme/primary_color}">

<!-- RIGHT -->
<td bgcolor="${primary_color}">
<td tal:attributes="style string:background-color: ${primary_color}">
```

Juice parses `style` as CSS: `{` opens a block, and `}` is eaten, leaving
broken text, not an expression. Inlining then stops for **the whole
document**, with no warning.

Use `bgcolor` for colours — never parsed as CSS. Use
`tal:attributes="style string:…"` for real CSS.

### 2. `${...}` in a literal `class` attribute is corrupted

```html
<!-- WRONG -->
<td class="${row_class}">
```

`css.safe` rewrites `$` to `-`, strips the braces. Runtime-computed **class
values are forbidden** — Tailwind sees only build-time markup, so a runtime
class loses its CSS. Use `tal:attributes="style string:…"` with literal
values.

### 3. `--` in any comment breaks the compiled `.pt` at runtime

Chameleon rejects `--` inside an HTML comment (`ParseError: The string '--' is
not allowed in a comment`), failing **at render time**, after a green build.
Use `;` or a full stop. The kit strips `.vue` comments in `afterTransform`;
the rule still hits **ZCML and GenericSetup XML**, which nothing strips.

Trap: `<Outlook :open="…" />` with an empty slot emits `<!--[endif]---->`. Give
it real slot content, or use `v-html`.

### 4. Writing `<style>` in prose inside a comment breaks the lint

`markup_only` in the lint blanks everything between a literal `<style>` and
the next `</style>`, comments included. A comment naming the element swallows
its own `-->`; the lint then flags the next comment's `<!--` as a stray `--`.
Write `&lt;style&gt;` in prose.

### 5. A component name inside a comment swallows the real block

Maizzle's global regex for its raw/escape component also matches inside HTML
comments. Naming that component in angle brackets inside a comment deletes the
real block. Never do it.

### 6. No `i18n:domain` renders `i18n:translate` untranslated

The msgid's default text still shows — looks like success. The kit's
`Main.vue` sets `i18n:domain="imio.emailkit"` on `<html>`; nested
`i18n:translate` inherits it. For your catalog, set your own domain:

```html
<p i18n:domain="my.addon" i18n:translate="email_intro">Default text.</p>
```

Without it, your msgid misses `imio.emailkit`'s catalog and renders its
default everywhere. Snapshot two languages (`languages = ("fr", "en")`): a
broken translation then shows as two identical snapshots, not a gap.

### 7. `${helper(x)}` must be `${python: helper(x)}`

TAL **path** expressions cannot call functions. `${format_date(when)}` raises
`Invalid variable name` — common, and loud:

```html
<!-- WRONG -->  ${format_date(when)}
<!-- RIGHT -->  ${python: format_date(when)}
```

Same for `tal:content`: `tal:content="python: format_date(when)"`.

### 8. Theme tokens: `tal:attributes` or `bgcolor`, never a literal `style`

Same failure as #1. Read a theme token with `bgcolor` or `tal:attributes`,
never inside a literal `style`.

### 9. A legacy `<style>` block is dropped by Gmail and Outlook.com

`render_shell(subject, body_html)` injects legacy HTML inside `<body>`, where
`<style>` is invalid, so Gmail and Outlook.com strip it. The shell wraps but
does **not** rewrite it into `<head>`. Inline `style="…"` survives: convert
the block to inline styles first — only real clients show the bug.

### 10. A top-level SFC `<style>` block never reaches the email

The bundler extracts it; purge then strips the now-orphaned class too, so the
markup loses both rule and class. Write custom CSS as a real `<style>`
**element** inside `<template>`, or add it to the kit's CSS entry.

### 11. `maizzle build` empties its output directory, silently

It deletes any hand-authored file placed there, twins included — Maizzle
6.0.7 has no `output.clean` / `emptyOutDir` option. Keep **hand-authored
`.txt.pt` twins in `emails/twins/`**, copy them into `templates/` after the
build. Never keep the only copy of anything in an output directory.

### 12. Dark-mode rules keyed on a class are deleted by purge

`css.purge` tracks only `class=` and `id=`, so a class-keyed
`@media (prefers-color-scheme: dark)` rule is stripped with a green build. Key
dark mode on `data-dark="page|surface|body|muted"` **attribute** selectors,
which purge cannot see.

### 13. A new `emails/` project with no `node_modules` ships uncompiled CSS

Tailwind resolves the shell's `@import "@maizzle/tailwindcss"` by walking up
from the **template's** directory. With no `node_modules` ancestor, resolution
fails, but **Maizzle still exits 0** with no inlined styles — same cause as
the kit's no-bare-imports rule: it lives in a Python egg, and `site-packages`
has no `node_modules` above it.

If a rebuild shrinks a lot, check for inline `style` attributes first.
`MIN_INLINE_STYLES`-style assertions catch this.

### 14. Rewording a msgid ships it untranslated

`python -m imio.emailkit.locales` marks a changed msgid `#, fuzzy`; **msgfmt
skips fuzzy entries**, so a reworded, retranslated msgid still renders in
English. The sync reports "0 added, 0 removed", and `make update-golden`
regenerates snapshots from the same broken catalogs, agreeing with the bug.

After rewording: strip the `#, fuzzy` lines, recompile, and read the mail in a
language you can check.

```bash
grep -rn '^#, fuzzy' src/imio/emailkit/locales/   # must be empty
python -c "import gettext; print(gettext.GNUTranslations(open('src/imio/emailkit/locales/fr/LC_MESSAGES/imio.emailkit.mo','rb')).gettext('<msgid>'))"
```

A msgid echoed back to you is untranslated.

### 15. Injected names beat your context

`render()` injects `theme`, `lang`, `target_language`, `portal_url`,
`translate`, `format_date`, `format_datetime`, `format_number`. These always
win over a same-named context key, since the kit layout uses them
unconditionally. Never name a context key `theme`, `lang`, or `preheader` —
`preheader` comes from the registration, not the caller.

---

## Authoring rules (`bin/check-emails` lint)

| Rule | Why |
|---|---|
| No `tal:` / `i18n:` attributes **on a kit component** | Vue attribute fallthrough lands them on the component's root — put them on your own `<tr>` / `<div>`. |
| No runtime-computed `class` values | Tailwind purge only sees build-time markup. |
| No `${...}` in a literal `class` or `style` attribute, ever | Failures 1 and 2. |
| `alt` on every image | RGAA applies to iMio's clients; lint fails without it. |
| `structure` only for `body_html` and `footer_html` | `${...}` is HTML-escaped by default — the right default. |
| No `--` in any comment, anywhere in the repo | Failure 3, reaching ZCML and XML too. |
| Kit files and `.vue` templates stay **import-free** of bare specifiers | The kit ships in a Python egg; `site-packages` has no `node_modules` ancestor. Maizzle auto-imports everything. |

`structure` is safe against template injection. Chameleon compiles the
**template**; an injected string becomes markup data, never re-parsed as TAL.
It stays **unescaped** — the slot's purpose.

### Run the lint

```bash
python -m imio.emailkit.lint emails/          # or any .vue file / directory
python -m imio.emailkit.lint --list-rules     # what each rule catches, and the fix
```

Eight rules, one per catalogue failure: `tal-on-component`, `runtime-class`,
`style-placeholder`, `class-placeholder`, `missing-alt`,
`comment-double-dash`, `raw-in-comment`, `path-call`. `bin/check-emails`
always runs it.

---

## Kit component catalog

The kit is **locked**: compose these, do not extend the Tailwind config.
Components auto-import, prefixed `Kit`.

### `<KitMain>` — the shell (`layouts/Main.vue`)

Wrap every template in it. It owns the whole document: meta tags, MSO
settings, `i18n:domain`, table roles, responsive/dark-mode `<style>`, the
hidden preheader div — and four bands:

1. **white band** — head artwork background, `logo_url` logo (translatable
   `alt`), `pill` slot on the right.
2. **title band** — `#f8f8f8`, closed by a 1 px rule; holds title and
   optional subtitle.
3. **content well** — your markup, plus the `body_html` injection point.
4. **negative footer** — `footer_html` or a translated default, then the iMio
   logo.

The head artwork is shell-owned (a template never references it) and carries
the brand colour, iMio magenta for every consumer. `primary_color` colours
only `KitCard`'s rail and `KitButton`'s fill.

```html
<template>
  <KitMain>
    <template #pill>
      <KitPill tone="success">
        <span i18n:translate="email_pill_new_account" tal:omit-tag="">New account</span>
      </KitPill>
    </template>
    <template #title>
      <span i18n:translate="email_welcome_title" tal:omit-tag="">Welcome</span>
    </template>
    <template #subtitle>${site_name}</template>

    <p class="m-0 text-[15px] leading-6 text-imio-black">${intro}</p>

    <template #mentions>
      <p class="m-0 text-[13px] leading-[21px] text-imio-grey-dark">…</p>
    </template>
  </KitMain>
</template>
```

**The title band belongs to the shell.** Do not write an `<h1>` in the content
well:

| Shape | Use when | How |
|---|---|---|
| `#title` / `#subtitle` slot | the title is **wording** | only shape carrying `i18n:translate` |
| `title` / `subtitle` in the render context | the title is **data** | nothing to write — shell reads the names |

Neither set: the band gets its closing 1 px `#d2d2d2` rule, no content.

> **`<h1>` plus a context `title`?** Delete the `<h1>` — the shell renders
> `title` in the band, so both print, visible on first preview.

`#mentions`: centred small print between body and footer, the copy-this-link
fallback and why-you-got-this text. Keep it here, not at the body's end — the
shell centres, sizes, and dark-mode-hooks it.

`#preheader`: **build-time** fallback for templates a stock Plone view renders
(no `render()` context). The registration's runtime msgid wins when present.

### `<KitPill tone>` — the status badge

In `KitMain`'s `pill` slot. `tone`: `info` (default), `success`, `warning`,
`danger`, resolved at **build** time. One per mail, naming the message's kind
in two words.

```html
<template #pill>
  <KitPill tone="success">
    <span i18n:translate="email_pill_new_account" tal:omit-tag="">New account</span>
  </KitPill>
</template>
```

**White on every tone** — a tinted fill on the head artwork would wash out or
clash with brand colour. The tone is a coloured disc in the 14 px icon: blue,
green, yellow, red.

Icon disappears with no absolute-URL request (golden files, unit tests) or
when a client blocks remote images — deliberate: a relative image URL shows
as broken. Pill stays a legible bold label on white, minus colour — write a
label that carries the meaning alone.

### `<KitCard>` — the rail card

What the mail is *about* — content submitted for review, an account created.
Tinted panel, 6 px `primary_color` rail. `overline`: kind of thing. `title`:
the thing. Default slot: lead paragraph and/or `KitDataList`.

```html
<KitCard>
  <template #overline>
    <span i18n:translate="email_card_kind" tal:omit-tag="">News item</span>
  </template>
  <template #title>${item_title}</template>
  <p class="m-0 text-sm leading-[22px] text-imio-grey-dark">${item_description}</p>
</KitCard>
```

### `<KitDataList>` / `<KitDataRow>` — label/value rows

Fixed handful of facts in a card: who, when, where. Presentational, no
header — unlike `KitDataTable`. `KitDataRow` carries the two cells.
`label-width`: `'130'` (default) or `'120'`, a **string**, as a plain
attribute:

```html
<KitDataList>
  <KitDataRow>
    <template #label><span i18n:translate="email_field_author" tal:omit-tag="">Author</span></template>
    ${author}
  </KitDataRow>
  <KitDataRow label-width="120">
    <template #label><span i18n:translate="email_field_submitted" tal:omit-tag="">Submitted</span></template>
    ${python: format_datetime(submitted)}
  </KitDataRow>
</KitDataList>
```

Do not write the 1 px rule between rows: `tailwind.css` hangs a
`tr + tr > td` selector off `KitDataList`'s class, drawing a top border on
every row but the first. A bottom border needs omitting on the *last* row —
nothing in email can select "last" (`:last-child` does not survive CSS
inlining).

`KitDataRow` can be a component where `KitDataTable`'s rows cannot: a data
list is fixed pairs, never a `tal:repeat`. For a repeat, write a plain `<tr>`
with the cell classes spelled out; it still gets the rule between rows.

### `<KitButton href align variant inline>` — the call to action

Single-cell table, **block** anchor carries the padding — the whole rectangle
is a click target. Cell repeats padding in `mso-padding-alt` for Word. `href`
takes `${...}` (not CSS). `align`: `left` | `center` | `right`. `variant`:
`solid` (default, `primary_color` fill) or `outline` (`#b3004b` rule,
secondary action). Colour is `primary_color` (shell-defined) — works only
inside `<KitMain>`.

```html
<div tal:condition="cta_url | nothing">
  <KitButton href="${cta_url}" align="center">${cta_label}</KitButton>
</div>
```

Put `tal:condition` on the plain `<div>`, not the component. Outlook renders
the button square, ignoring `border-radius`; the VML fix needs a pixel width,
which a translated label cannot give.

### `<KitButtonGroup align>` — two actions on one row

Each `KitButton` is its own table; two cannot share a line in mail, so the
group builds the row. `inline` drops each button's top margin, supplied once
by the group for the pair.

```html
<KitButtonGroup align="center">
  <template #primary>
    <KitButton href="${review_url}" inline>${review_label}</KitButton>
  </template>
  <template #secondary>
    <KitButton href="${back_url}" variant="outline" inline>${back_label}</KitButton>
  </template>
</KitButtonGroup>
```

Two **named** slots hold the buttons — a component cannot wrap untold-about
children, and the 12 px gap needs a home. `#secondary` is optional. Cells stay
side by side on a phone; labels that do not fit on one line want two stacked
`KitButton`s instead.

### `<KitPanel tone>` — the callout

Bordered block for one condition: how long a link lasts, what happens if
ignored. `tone`: `accent` (default, pink) or `neutral`, resolved at **build**
time. Optional `overline` names the condition.

```html
<KitPanel>
  <template #overline>
    <span i18n:translate="email_callout_link_validity" tal:omit-tag="">Link validity</span>
  </template>
  <p class="m-0 text-sm leading-[22px] text-imio-black">…</p>
</KitPanel>
```

### `<KitDataTable>` — chrome for tabular data

Many rows of the same shape, header naming the columns. The one table in the
kit **not** `role="presentation"`: marking it presentational would hide
structure from screen readers. Write rows yourself — `tal:` cannot go on the
component:

```html
<KitDataTable>
  <template #head>
    <th scope="col" class="border-b border-solid border-imio-grey-border p-2 text-left text-sm">Point</th>
    <th scope="col" class="border-b border-solid border-imio-grey-border p-2 text-left text-sm">Decision</th>
  </template>
  <tr tal:repeat="row rows">
    <td class="border-b border-solid border-imio-grey-border p-2 text-sm">${row/title}</td>
  </tr>
</KitDataTable>
```

Add `scope="col"` to header cells yourself; the kit cannot, since cells come
from the slot.

### Theme tokens

Three branding values, set at runtime from `plone.app.registry`; everything
else is Tailwind, fixed at build time.

| Token | Registry record |
|---|---|
| `logo_url` | `imio.emailkit.theme.logo_url` |
| `primary_color` | `imio.emailkit.theme.primary_color` |
| `footer_html` | `imio.emailkit.theme.footer_html` |

The shell defines them. Read as `${primary_color}` inside `bgcolor` or
`tal:attributes`, never inside a literal `style`.

---

## Registration

One `<emailkit:templates>` block per add-on, in its own `configure.zcml`:

```xml
<!-- my/addon/configure.zcml -->
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="my.addon"
    >

  <include package="imio.emailkit" file="meta.zcml" />

  <emailkit:templates directory="templates">
    <!-- `[msgid] Default text` picks the msgid explicitly; the domain comes
         from this file's `i18n_domain`, so no MessageFactory is needed. -->
    <emailkit:template
        name="item_published"
        subject="[email_subject_item_published] Item published"
        preheader="[email_preheader_item_published] …"
        />
  </emailkit:templates>

</configure>
```

- Lookups are namespaced: `my.addon:item_published`, from the ZCML file's own
  package — the bare basename resolves to nothing, since add-ons can share a
  template name.
- **The subject lives in the registration** — a msgid, translated per
  recipient language at send time, never in the template or a sidecar.
- **Always give a default text.** Without one, an untranslated subject shows
  as the bare msgid.
- `preheader`: the hidden inbox-preview line, shown by every inbox. If
  omitted, the client uses whatever body copy comes first — keep it under
  ~100 characters.
- **One block per package; duplicate names conflict.** A second
  `<emailkit:templates>` in one package, or two templates sharing a `name`,
  raises `ConfigurationConflictError` at startup — never a silent overwrite.
- `i18ndude` never extracts from ZCML. If your add-on rebuilds its `.pot`, add
  the same msgids to a small `msgids.py` (see `src/imio/emailkit/msgids.py`).
- `MANIFEST.in`: `recursive-include …/templates *.pt` **and** `prune …/emails`.

`z3c.jbot` overrides work on the resolved `.pt`, no extra setup needed. A site
layer overriding ours must **extend** `IEmailkitLayer`; sibling-layer
precedence is otherwise arbitrary.

---

## Plaintext twins

`<name>.txt.pt`: the plaintext half. Hand-author it in `emails/twins/`, copy
it into `templates/` after the build.

**Never generate one.** Maizzle's plaintext output keeps `${}` but destroys
every `tal:`/`i18n:` construct — conditionals vanish, header lines empty,
`i18n:translate` freezes at English. A generated twin ships a plausible body
with wrong content, wrong language.

Without a twin, a naive extraction runs instead: it warns once, logs a
deprecation, and **drops every link**, since the URL lives in an `<a href>` it
discards. Any template with a call to action needs a twin.

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
`tal:omit-tag=""` emits text without tags. A stray real tag reaches a
plaintext reader as literal markup.

---

## Fixture / golden workflow

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
    "when": "2026-08-12T19:30:00",  # ISO string; format_date coerces it
    "rows": [{"title": "Budget 2026", "decision": "approuvé"}],
}
```

Fixture rules:

- **One key per `${...}`, no more.** The fixture is the contract: a
  placeholder with no matching key fails the golden test loudly.
- **Omit what `render()` injects** — `lang`, `theme` and its tokens,
  `preheader`. Pinning them hides a broken injection and locks snapshots to
  one language.
- **Use plain data, not objects.** A plain Python instance needs
  `__allow_access_to_unprotected_subobjects__` before `${item/title}` can
  traverse it; mappings and ISO strings work without it.
- **Include non-ASCII text.** A charset regression shows up nowhere else.
- **Cover both branches of every `tal:condition`**: one fixture with
  `cta_url`, one without.

`bin/preview-emails` and `@@emailkit-preview` use the same fixtures — keep
them realistic.

### Regenerating snapshots

Do this on purpose, never as a side effect of a failing test:

```bash
EMAILKIT_UPDATE_GOLDEN=1 pytest tests/ -q -rs   # writes, reports every one as skipped
git diff                                        # review before committing
```

A snapshot that repairs itself when it breaks is not a snapshot. The harness
checks the *committed* snapshot for raw `${...}`, so a broken engine cannot
bake in a placeholder and pass forever.

---

## Runtime API

```python
from imio.emailkit import Email, render, render_shell

html, text = render("my.addon:item_published", context={"item": item}, language="fr")

Email("my.addon:item_published").to(member).to("greffe@commune.be").cc(
    managers
).reply_to("noreply@imio.be").with_context(item=item).attach(
    pdf, filename="convocation.pdf"
).send()
```

- The builder holds data, not behaviour: nine fixed methods — `to`, `cc`,
  `bcc`, `reply_to`, `sender`, `subject`, `with_context`, `attach`, `send`.
- Recipients: any mix of an address, a member, a userid, or an iterable.
  `.send()` **groups by resolved language**, rendering once per group — FR/NL
  communes need no extra code. No per-send language argument.
- `.send()` raises on unresolvable or zero recipients, a missing subject, an
  unset `plone.email_from_address`, or unguessable attachment metadata —
  fails loud, never drops silently.
- Delivery is **queued**: an aborted transaction sends nothing. Use
  `.send(immediate=True)` to send anyway.
- To migrate mail code, call `render_shell(subject, body_html)` to wrap a
  legacy body with no template work, or pass it as `body_html` in a
  registered template's context — keeping the registration's subject,
  preheader, and hand-authored twin.

## Plone default mails are ordinary templates

`mail_password_template`, `registered_notify_template` and `get_username`
restyle stock Plone mails — authoring them is **not special**. This
package's own views for all three (`browser/default_mails.py`,
`browser/login_help.py`) build a flat context and call `render()`, so they
are registered, discovered, previewable and golden-tested like any consumer
template: same `${...}`, `i18n:domain`, locale helpers, twins.

Markup using `${options/member}`, `${python: member.getProperty('email')}`, no
locale helpers, no `theme`, or a hand-written `Subject:` header from
`useDoctype()` belongs to a different dialect. Convert it to `render()`, the
kit's locale helpers, and a ZCML-registered subject.

One part stays in Python — it cannot be a template: `RegistrationTool` parses
`Subject`/`To`/`From` out of the returned string, so
`DefaultMailView.header_block` builds an RFC822 preamble. Its subject is the
template's registration msgid: **set the subject in ZCML**, never in the
template.

If you add a context key, add it to `build_context` **and** the fixture — the
golden test catches a forgotten one.

## Wallonie Connect migration mail

`imio.emailkit:user_migrated_to_sso` tells a user their local account now logs
in through Wallonie Connect. The kit owns the template, translations, and
mark — a consumer only sends it:

```python
Email("imio.emailkit:user_migrated_to_sso").to(member).with_context(
    site_name="Délibérations.be",  # the product the reader knows
    institution=institution.Title(),
    email=new_userid,
    username=old_userid,
    login_url=login_url,  # starts the OIDC flow
    account_url=account_url or "",  # empty drops the account-console link
).send()
```

The subject names no product: one registered msgid serves every consumer.

## Checklist before you commit

- [ ] `.vue` changed → **rebuild** and commit the `.pt` (never edit the `.pt`)
- [ ] no `${...}` in a literal `class` or `style`; colours on `bgcolor`
- [ ] no `tal:` / `i18n:` on a kit component
- [ ] no `--` in any comment
- [ ] `i18n:domain` on your element for your msgids
- [ ] helpers called as `${python: …}`
- [ ] `alt` on every image
- [ ] fixture updated for new placeholders
- [ ] twin updated, in `emails/twins/`
- [ ] snapshots regenerated on purpose, diff reviewed
- [ ] staleness gate green, golden gate green
