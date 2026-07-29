# Phase 3 — Shell for existing mails: report

**Date:** 2026-07-29
**Plan:** `docs/plans/phase-3.md`

---

## Exit criteria

Verbatim from §9:

> | **3 — Shell for existing mails** | `render_shell(subject, body_html)`; existing PloneMeeting notification bodies dropped into the slot | All PloneMeeting notifications sent styled, zero template redesign |

| Clause | Status |
|---|---|
| `render_shell(subject, body_html)` | **done** — a `render()` sibling, §6.2 untouched |
| existing bodies dropped into the slot | **done** — verified with realistic PloneMeeting-shaped bodies |
| zero template redesign | **demonstrated** — the body goes in byte-for-byte, nothing about it changes |
| *all PloneMeeting notifications sent styled* | **not mine** — see below |

### The clause not mine to satisfy

"All PloneMeeting notifications sent styled" needs the PloneMeeting codebase, a separate distribution
nobody has handed me, and §9 itself puts a real pilot addon in Phase 5. What is delivered is the whole
mechanism plus proof against realistic bodies; the remaining step is mechanical and is the maintainer's.

## Evidence

```
$ python -m pytest tests -q
360 passed, 1 skipped, 2 xfailed in 188.08s

$ make check                 exit 0
$ make check-emails          exit 0   (5 files, including the plaintext twin)
$ zconsole run … scripts/verify_install.py
ALL EXIT-CRITERION CHECKS PASSED
```

On a live site, a legacy body wrapped by `render_shell`:

```
ok   lang on <html> / xml:lang on <body> / role="presentation" / logo alt
ok   inlined CSS from the build   ok   dark-mode <style> block intact
ok   theme tokens applied around the legacy body
ok   LEGACY_BODY present byte-for-byte: inline styles, cellpadding, nested table, entities
<html> element count: 1
```

## The security question, settled first

`render_shell` injects with `structure`, and legacy notification bodies are often assembled by string
concatenation — so a `${...}` in one could plausibly have read the render namespace. **It cannot.**
`structure` inserts the string as markup *data*; the page template is compiled once and the injected
characters are never re-parsed as TAL.

The test proves this properly rather than asserting it. Every expression in the body is a name that
**is** in the namespace, and positive controls show the same engine substituting those exact
expressions where the *shell* writes them:

```
body in  : lang is ${lang}, colour is ${theme/primary_color}, url is ${portal_url},
           env is ${python:__import__("os").environ}, and ${python: 6*7} is forty-two.
slot out : (identical, character for character)

ok  positive control: the shell's own ${lang}                -> lang="fr"
ok  positive control: the shell's own ${theme/primary_color} -> "#123456"
ok  no colour, no 42, no os.environ contents anywhere in the output
```

Without those controls, "the body came out verbatim" could have been a false green from the zope.tal
pass-through path — the trap Phase 0 documented. The body **is** inserted unescaped, which is the
slot's purpose; the shell wraps and deliberately does not sanitise.

## Two real defects found, both in the plaintext part

Both mattered more than they look, because `render_shell` has no `.txt.pt` twin *by design* — a twin's
only content would be `body_html`, which is HTML. So naive extraction **is** its plaintext part, and
this was the plaintext quality of every migrated mail.

1. **Table cells concatenated.** `</tr>` broke a line, `</td>` did not: a header row rendered
   `PointDécision`, a data row `Budget 2026approuvé`. Legacy notification bodies are table-heavy. Cells
   now get a ` | ` separator, so a row stays on one line: `Point | Decision`.
2. **A nested `<head>` leaked its `<title>` into text/plain**, glued to the first line of the body.
   Only ever visible in the plaintext part, because clients drop the nested head from the HTML one —
   precisely the kind of defect a browser preview cannot show.

The workstream that found (1) deliberately did **not** fix it, because it changes `render()`'s output
and therefore committed goldens. That was the right call; the fix was then made deliberately and the
goldens regenerated.

## Gate 6's answer, measured not assumed

All pathological inputs **render; none fails loudly.** An unclosed tag, a `<style>` block, a bare `&`,
`--` inside a comment, a stray closing tag, an unquoted attribute, uppercase `<FONT>`, an MSO
conditional and a naked `<` all pass through verbatim without exception — same reason the slot is safe.

The one case worth knowing: **a pasted whole `<html>` document yields `<html>`, `<body>` and
`<!DOCTYPE>` twice** — technically invalid HTML that mail clients tolerate. Left as is: the plan
forbids cleaning, and the alternative is the shell silently rewriting a consumer's markup. Recorded as
the documented answer rather than papered over. A `check-emails` warning for a consumer doing this is a
reasonable Phase 4 lint addition.

## An unplanned finding: there are two routes, and the second is better

Plan gate 8 said "`Email(...)` can send a shell-rendered body with no builder change". True of the
*message assembly*, verified end to end — but `Email` always renders internally from a template
**name**, so it cannot be handed a `render_shell()` pair. Hence one of the two remaining xfails.

The useful discovery is that this does not matter, because the kit layout defines the `body_html` slot
for **every** template, not just the shell:

| Route | When | What you keep |
|---|---|---|
| `render_shell()` + `build_message()` | you already own your sending code (PloneMeeting calls MailHost directly today) | full control |
| `Email("imio.emailkit:notification").with_context(body_html=<legacy>)` | you want the builder | the registration's subject **and** preheader, and the hand-authored `.txt.pt` twin |

Route 2 was not designed. It falls out of the layout owning the slot, and it is strictly better for any
consumer willing to register a template.

## The two remaining xfails are tripwires, not failures

Both are `strict=True`, so they turn the suite **red** if anyone makes them pass without settling the
underlying question:

1. **§6.3-as-written on the send-test language**, which §6.2 — the frozen section — cannot express.
2. **`Email('imio.emailkit:shell')` raises `TemplateNotFound`**, because the shell is resolved by path
   and deliberately not registered (registering it would put a name nobody can call into
   `TemplateNotFound.available` and the preview list). Fixing it is a maintainer choice: register the
   shell, or document route 2 above — which the README now does.

## Also fixed here

`make lint` ran `ruff --fix`, so a clean tree exited **non-zero because it had fixed something** and
passed only on a second run. Checking is `lint`, rewriting is `format`. Now deterministic.
