# Phase 2 — API

**Date:** 2026-07-29
**Spec:** §9 phase 2, §6.2 (`Email` builder — **frozen**), §6.3 (preview view + send-test), §7
**Depends on:** Phase 1 complete — `render()`, discovery, kit, profiles all green

---

## 1. Exit criteria

Verbatim from §9:

> | **2 — API** | `Email` builder, recipient adapters, attachments, per-language send, preview view + send-test | First real notification sent through the builder end-to-end |

"First real notification sent end-to-end" needs a real MTA and a real recipient, which is the same
authority problem as Phase 1's production site. The substitute, stated up front rather than
discovered later: **end-to-end through `IMailHost` on a real instance**, asserting on the queued
message — headers, both MIME parts, attachments, and one message per language group — plus the
send-test button exercising the identical path to a real address. The last hop is the maintainer's.

## 2. The API is frozen — §6.2 verbatim

```python
Email("imio.pm.notifications:item_published") \
    .to(member) \
    .to("greffe@commune.be") \
    .cc(meeting_managers) \
    .reply_to("noreply@imio.be") \
    .with_context(item=item, meeting=meeting) \
    .attach(convocation_pdf, filename="convocation.pdf") \
    .send()
```

Methods, and nothing beyond them: `.to()`, `.cc()`, `.bcc()`, `.reply_to()`, `.sender()`,
`.subject()`, `.with_context()`, `.attach()`, `.send()`.

**The builder is a plain data holder. Each method returns `self`. It holds data, it does not grow
behaviour — no conditionals, no scheduling, no retries.** A signature change is a decision-log entry
plus approval, never a quiet edit. If implementation pressure pushes on this, the answer is to stop
and report.

## 3. Scope

| Deliverable | Spec |
|---|---|
| `Email` builder | §6.2 |
| `IEmailRecipient` adapter + defaults for `str` and Plone members | §6.2 |
| `RecipientError`, `AttachmentError` — raised at `.send()`, never a silent drop | §6.2 |
| Attachments: bytes, path, file object, blob value, content object; inferred filename/mimetype | §6.2 |
| Per-language send: group recipients, render once per group, one message per group | §6.2 |
| Message assembly via `EmailMessage`: `set_content(text)` + `add_alternative(html, subtype="html")` | §6.2 |
| Queued `IMailHost` delivery by default; `.send(immediate=True)` the only escape | §6.2 |
| `@@emailkit-preview` (Manager-only) + send-test | §6.3 |
| §7 tests: recipients, attachments, language grouping, transaction abort | §7 |

## 4. Design notes

**Recipient resolution goes through one adapter, not a chain of `isinstance`.** §6.2 specifies
`IEmailRecipient` with `email` / `fullname` / `language`. `.to()/.cc()/.bcc()` accept a string, a
member, a userid, or an iterable of those in any mix; flattening happens at collection time,
resolution at `.send()` time so errors surface together.

**Language grouping is the reason `render()` was built as a pure function.** `.send()` resolves every
recipient, groups by resolved language (falling back to the site default), renders once per group,
translates the subject msgid per group, and emits one message per group. Attachments are identical
across groups and ride the same assembly.

**Transaction safety is the default and must be tested by aborting.** §6.2: delivery via queued
`IMailHost` send, so an aborted transaction sends nothing. §7 names the test explicitly: `.send()` +
abort → MailHost queue empty.

**Dark mode lands here**, deferred from Phase 1 (`DECISIONS.md`): the send-test button is the first
point at which `prefers-color-scheme` can be verified in a real client rather than a browser.

## 5. Workstreams (parallel)

- **W1 — builder + adapters (`plone-dev`)**: `Email`, `IEmailRecipient` and its adapters, attachment
  source handling, language grouping, message assembly, `IMailHost` delivery.
- **W2 — preview view (`plone-dev`)**: `@@emailkit-preview`, Manager-only, template list, fixture
  rendering in an iframe, language switcher, theme-token panel, send-test.
- **W3 — tests (`test-writer`)**: the §7 matrix for this phase, written from the spec.
- **W4 — kit (`maizzle-author`)**: dark-mode CSS in `Main.vue` with purge-safe selectors.

## 6. Test plan

| # | Gate |
|---|---|
| 1 | recipients: str, member, userid, mixed iterables; duplicates; `RecipientError` on unresolvable |
| 2 | attachments: bytes (filename required), path, file object, blob value, content object; filename/mimetype inference; `AttachmentError` on unguessable |
| 3 | language grouping: FR+NL recipients → exactly two messages, each with its own subject translation and rendered body |
| 4 | subject: from the registration by default; `.subject()` override with msgid and with a literal |
| 5 | message shape: `multipart/alternative`, text part first, html second, correct encoding and headers |
| 6 | **transaction abort → MailHost queue empty** (§7, named explicitly) |
| 7 | `.send(immediate=True)` bypasses the queue |
| 8 | builder immutability of behaviour: every method returns `self`; no method does I/O before `.send()` |
| 9 | preview view: Manager-only (anonymous gets Unauthorized), lists registered templates, renders with fixtures, language switcher works |
| 10 | send-test delivers to the logged-in user's own address and nowhere else |

## 7. Non-goals

- **No `render_shell()`** → Phase 3
- **No recipe, no `bin/` scripts, no authoring lint** → Phase 4
- **No content-rule action** → Phase 5
- **No scheduling, digests, retries, campaigns** → out of scope entirely (§1)
- **No new builder methods** beyond §6.2
- **No `cid:` inline images** — §10.5 keeps them out of v1
- **No MailHost monkey-patching**, ever

## 8. Risks

| Risk | Response |
|---|---|
| `.send()` grows conditionals to handle a real case | that is the §6.2 boundary; report instead of absorbing it |
| Attachment sources need a Plone-version-specific branch | isolate in the source-resolution function, never in the builder |
| The stock mails' `Content-Type` question from Phase 0 resurfaces | it belongs here: settle the MIME shape with a real queued message as evidence |
