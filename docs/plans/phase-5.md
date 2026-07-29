# Phase 5 — Adoption

**Date:** 2026-07-29
**Spec:** §9 phase 5, §8.3 (content rules)
**Depends on:** Phases 0–4 complete and green

---

## 1. Exit criteria, and what is actually reachable

Verbatim from §9:

> | **5 — Adoption** | Content-rule action; migrate remaining notifications to purpose-built templates; second consumer addon | Two independent addons shipping templates |

This row has three deliverables and they do **not** have the same status. Stated up front rather than
discovered at the end:

| Deliverable | Reachable now? |
|---|---|
| **Content-rule action** (§8.3) | **Yes, fully.** It lives entirely inside this package. |
| Migrate remaining notifications to purpose-built templates | **No.** Needs the PloneMeeting codebase. |
| Second consumer addon | **Partly.** Three addons already ship templates through the real mechanism (`tests/dummies/dummy.minimal`, `dummy.complete`, `recipe/tests/consumer/emailkitdemo`) — but they are test doubles, not products. |

The mission brief is explicit that a **pilot addon arrives from the maintainer**, so the migration and a
genuine second product are handed over, not simulated. Phase 5 therefore delivers the content-rule
action and leaves the adoption half openly incomplete.

## 2. Scope: the content-rule action (§8.3)

> **Content rules:** a new action type *"Send styled email"* — edit form offers the registered template
> names (vocabulary from discovery) + recipient sources; executor delegates to `Email(...)`. The stock
> mail action is left untouched.

- A `plone.contentrules` action: schema, add/edit forms, executor, GS registration.
- **A vocabulary over discovery** — the same `get_templates()` the preview view uses, so a template
  registered by any addon appears without touching this package.
- **The executor delegates to `Email(...)` and does nothing else.** §6.2 is frozen; this is a caller.
- Recipient sources: at minimum an explicit address list and the content's owner. Anything beyond that
  is a decision entry, not an invention.
- **The stock mail action is left untouched** (§8.3, explicit).

## 3. Non-goals

- **No changes to `Email`** — §6.2 frozen; the action is a consumer of it.
- **No MailHost monkey-patching**, no TTW markup editing (choosing a registered template from a
  vocabulary is not editing markup).
- **No scheduling, digests or retries** (§1 non-goals) — a content rule fires, it does not queue.
- **No PloneMeeting code**, no vendored copy, no dependency.
- **No new builder methods.**

## 4. Test plan

| # | Gate |
|---|---|
| 1 | the action type is registered and appears in the content-rules control panel |
| 2 | the vocabulary lists every discovered template, including ones from other addons |
| 3 | adding the action through the form stores template + recipients |
| 4 | firing the rule sends exactly one mail per language group, through `Email` |
| 5 | the mail is the styled template, with placeholders substituted (assert on values, never markers) |
| 6 | an unresolvable recipient raises `RecipientError` — no silent drop |
| 7 | a rule naming a template that has since disappeared fails loudly, not silently |
| 8 | the stock mail action still works and is unmodified |
| 9 | transaction abort → nothing sent (§6.2's guarantee holds through the executor) |

## 5. Risks

| Risk | Response |
|---|---|
| The executor is tempted to grow conditionals | it delegates to `Email` and returns; anything else belongs in the builder, which is frozen — report instead |
| Recipient sources balloon into a feature | two sources, then stop; more is a decision entry |
| A rule holds a stale template name | gate 7 — must fail loudly, since a content rule silently not mailing is indistinguishable from no rule |
