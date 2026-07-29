# Phase 2 — API: report

**Date:** 2026-07-29
**Plan:** `docs/plans/phase-2.md`
**Stack:** Plone 6.2.1, Zope 6.1, Chameleon 4.6.0, Python 3.12, Maizzle 6.0.7

---

## Exit criteria

Verbatim from §9:

> | **2 — API** | `Email` builder, recipient adapters, attachments, per-language send, preview view + send-test | First real notification sent through the builder end-to-end |

| Clause | Status |
|---|---|
| `Email` builder | **done** — §6.2's nine methods, nothing more |
| recipient adapters | **done** — one `IEmailRecipient` adapter, defaults for `str` and members |
| attachments | **done** — all five source kinds, inference, `AttachmentError` |
| per-language send | **done** — one message per language group |
| preview view + send-test | **done** — Manager-only, iframe, switcher, token panel, send-test |
| *first real notification sent end-to-end* | **substituted — see below** |

### The clause not met as written

Sending to a real mailbox needs an MTA and a recipient, which is the same authority limit as Phase
1's production site. What is demonstrated instead, and it is most of the distance:

- the message reaches `IMailHost` through the **real** `MailHost` → `_mungeHeaders` →
  `DirectMailDelivery` → `MailDataManager` path, with only `SMTPMailer.send/vote/abort` recorded;
- the queued message is asserted on: envelope, headers, both MIME parts, encodings, attachments;
- the send-test button drives the identical path to a real address on a live instance.

The last hop — SMTP to a real inbox, and what Outlook and Gmail actually make of the markup — is the
maintainer's, and it is what the send-test button exists to make cheap.

## Evidence

```
$ python -m pytest tests -q
282 passed, 1 skipped, 1 xfailed in 163.17s

$ make check            # ruff check + format + pyroma + check-python-versions + zpretty
exit 0
$ make check-emails
exit 0    (4 templates ok, including the plaintext twin)
$ zconsole run instance/etc/zope.conf scripts/verify_install.py
ALL EXIT-CRITERION CHECKS PASSED
```

The queued message, from a real send:

```
envelope MAIL FROM: iMio Émailkit <noreply@imio.be>
envelope RCPT TO  : ['Alice Dupont <alice@commune.be>', 'greffe@commune.be', 'audit@imio.be']
  Subject: Notification                      Content-Type: multipart/alternative
    part text/plain charset=utf-8 cte=8bit             >>> Séance du conseil communal du 12 août
    part text/html  charset=utf-8 cte=quoted-printable >>> <!DOCTYPE html>
CRLF line endings: True | bare LF: False
Bcc header present in wire bytes: False        <-- envelope kept it, header did not
```

FR + NL in one call → two messages, each with its own subject *and* its own render:

```
builder order (group order): ['Notification', 'Melding']
  RCPT TO ['Bram Janssens <bram@gemeente.be>']   Subject: Melding       <html lang="nl">
  RCPT TO ['Alice Dupont <alice@…>', 'No Lang <nolang@…>']
                                                 Subject: Notification  <html lang="fr">
attachments identical across groups; bodies genuinely different, not a copy
```

The abort test, which §7 names explicitly:

```
after .send():   built=1  mailer.sent=0   data managers joined to txn: 1
after abort():   mailer.sent=0            mailer.abort() calls=1
control, commit: after .send() 0  ->  after commit() 1
immediate=True:  after .send() 1  data managers joined: 0
```

## What Phase 2 found

**A silently wrong `From` header.** `.sender("Greffe <greffe@commune.be>")` produced
`From: "Greffe <greffe"@commune.be` — syntactically valid, wrong mailbox, no error anywhere. Caught
only because the check asserted on the substituted header value rather than on presence. Both the
adapter and `as_address()` now parse.

**`MailHost.smtp_queue` defaults to `False`, and that does not mean "not transaction-safe".**
`immediate=False` still goes through `DirectMailDelivery`, which joins a data manager and sends in
`tpc_finish`. §6.2's "queued send" is the *transaction* binding, not MailHost's maildir queue. Worth
knowing before someone "fixes" a site by turning `smtp_queue` on.

**`MailDataManager.sortKey()` is `str(id(self))`**, so the order messages reach the mailer is
arbitrary. Only `.send()`'s return value is in group order; no test may assume delivery order.

**The instance died at startup** on `permission="cmf.ManagePortal"`: the generated `site.zcml`
includes this package *before* `<five:loadProducts />`, so CMFCore's permissions had not been
registered. The error names the permission, not the include ordering.

**`request.get("REQUEST_METHOD")` and `request.method` disagree after mutation.** The former reads
`environ` live; the latter is frozen at construction. Only relevant to test harnesses, but it cost
time.

## The spec contradicts itself, once

§6.3 says the send-test mails "template + fixture + **language**". §6.2 gives `Email` **no** language
argument — language comes from the recipient, via grouping. As written, §6.3 asks for something the
frozen builder cannot express.

Resolved in favour of §6.2, which is the frozen one. `request["LANGUAGE"]` was tried and **measured
inert**; rewriting the member's stored language was rejected as silent mutation of user data. The view
computes the send language from §6.2's own public contract, labels the button with it, and warns when
it differs from the preview switcher. **§6.3's wording may want correcting.**

## Process note

I ran the suite while the test workstream was still editing it, and spent real effort diagnosing
failures that were already fixed. Three of the "failures" I chased passed in isolation the moment I
looked. The lesson is procedural, not technical: do not sample a moving target — wait for the
workstream that owns a directory to finish before drawing conclusions from it.

Separately, an earlier `git add -A` swept another workstream's in-progress files into an unrelated
commit. Staging explicit paths from that point on.

## Deferred

| Item | Why | Lands in |
|---|---|---|
| Real-client verification of dark mode | needs the send-test against Gmail/Outlook; structurally verified only | maintainer, now unblocked |
| `[data-ogsc]` Outlook.com dark path | Outlook Windows ignores `prefers-color-scheme` anyway, so light rendering stands alone | if a client asks |
| `cid:` inline images | §10.5 keeps them out of v1 | revisit only on a policy need |
