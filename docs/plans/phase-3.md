# Phase 3 — Shell for existing mails

**Date:** 2026-07-29
**Spec:** §9 phase 3, §3 (the kit shell), §6.1
**Depends on:** Phase 2 complete — builder, adapters, per-language send, preview all green

---

## 1. Exit criteria

Verbatim from §9:

> | **3 — Shell for existing mails** | `render_shell(subject, body_html)`; existing PloneMeeting notification bodies dropped into the slot | All PloneMeeting notifications sent styled, zero template redesign |

**One clause is not mine to satisfy.** "All PloneMeeting notifications sent styled" needs the
PloneMeeting codebase, which is a separate distribution nobody has handed me. §9's phase 5 note is
explicit that a pilot addon arrives later.

What Phase 3 delivers instead, and it is the whole mechanism:

- `render_shell(subject, body_html)` implemented, tested and documented;
- proof of the "zero template redesign" claim against **realistic PloneMeeting-shaped bodies** — the
  actual HTML idioms those notifications emit — committed as fixtures and golden files;
- a documented migration recipe: what a consumer changes to route an existing notification through the
  shell, and what it explicitly does not change.

The remaining step is mechanical and is the maintainer's: point PloneMeeting's notification sending at
`render_shell`. Stated as a gap, not folded into "met".

## 2. The one new API

```python
html, text = render_shell(subject, body_html, language=None)
```

That is the entire surface. It is **not** a builder method — §6.2 is frozen and this is a `render()`
sibling, so it lives beside `render()` in the public namespace: `from imio.emailkit import render_shell`.

**Semantics.**

- `body_html` is dropped into the kit shell's `body_html` slot with `structure` — §3 rule 4's one
  sanctioned use of unescaped markup, and the reason that slot exists at all.
- `subject` is used for the shell's heading and preheader where the shell wants a title. It accepts a
  msgid or a literal, like `.subject()`.
- Returns `(html, text)` exactly as `render()` does, so the `Email` builder needs no change to send it.
- Same namespace, theme tokens and locale helpers as `render()` — one code path, not a parallel one.

**Open question this phase must settle with evidence.** `body_html` is arbitrary legacy HTML: it will
carry its own `<p>`, `<table>`, `<a>`, maybe inline styles, maybe a `<style>` block, maybe an unclosed
tag. The shell's inlined CSS was computed at build time and cannot see it. So:

1. Does injected legacy markup render at all through Chameleon (`structure` on a fragment)?
2. Does it look acceptable inside the shell without per-body work — the "zero template redesign" claim?
3. What happens with pathological input: unclosed tags, a `<style>` block, a full `<html>` document
   pasted in, `${...}` that must **not** be interpolated?

Item 3 matters most. Legacy notification bodies are often built by string concatenation, and a `${`
in one would otherwise be evaluated by Chameleon at render time. **That is a security-relevant
question, not a cosmetic one**, and it gets an explicit test either way.

## 3. Scope

| Deliverable | Spec |
|---|---|
| `render_shell(subject, body_html, language=None)` | §9 phase 3 |
| A kit shell entry point that takes a body slot rather than authored content | §3 |
| Fixtures + goldens for realistic legacy bodies, including pathological ones | §7 |
| `${...}` in an injected body is **not** interpolated | this plan §2 |
| Migration recipe in the README | §9 |

## 4. Test plan

| # | Gate |
|---|---|
| 1 | `render_shell("Subject", "<p>Body</p>")` returns `(html, text)`; body appears unescaped inside the shell |
| 2 | the shell's own inlined CSS, a11y defaults, `lang` and preheader are all present, exactly as for an authored template |
| 3 | theme tokens apply to the shell around a legacy body |
| 4 | a realistic PloneMeeting-shaped body (nested tables, inline styles, links) survives intact — golden file |
| 5 | **`${...}` inside `body_html` is emitted literally, never evaluated** |
| 6 | pathological input: unclosed tag, `<style>` block, a whole `<html>` document — each either renders sanely or fails loudly, and the test records which |
| 7 | the plaintext part is sensible for an injected body (the naive-extraction path) |
| 8 | `Email(...)` can send a shell-rendered body with no builder change |
| 9 | language: subject msgid translated, `lang` correct, FR ≠ NL |

## 5. Non-goals

- **No PloneMeeting code.** No dependency on it, no import of it, no vendored copy.
- **No new builder methods** — §6.2 stays frozen; `render_shell` is a `render()` sibling.
- **No recipe, no `bin/` scripts, no authoring lint** → Phase 4
- **No content-rule action, no dummy consumer addons** → Phase 5
- **No sanitising or rewriting of `body_html`.** The shell wraps; it does not clean. If a body is
  broken, that is the consumer's markup and silently "fixing" it would be worse than rendering it.

## 6. Risks

| Risk | Response |
|---|---|
| `${` in a legacy body is evaluated by Chameleon | the load-bearing risk of this phase; test 5 exists for it and the answer determines whether `structure` is safe here at all |
| legacy bodies look bad in the shell, so "zero redesign" is false | report it with the golden as evidence rather than quietly adding per-body CSS |
| the shell needs a second kit layout | §10.3 already says a second layout is the cheap first answer; that would be a decision entry, not a silent addition |
