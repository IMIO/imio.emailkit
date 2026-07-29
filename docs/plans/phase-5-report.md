# Phase 5 — Adoption: report

**Date:** 2026-07-29
**Plan:** `docs/plans/phase-5.md`

---

## Exit criteria — partially met, and the gap is structural

Verbatim from §9:

> | **5 — Adoption** | Content-rule action; migrate remaining notifications to purpose-built templates; second consumer addon | Two independent addons shipping templates |

| Deliverable | Status |
|---|---|
| **Content-rule action** (§8.3) | **done** — 72 tests |
| Migrate remaining notifications to purpose-built templates | **not delivered** — needs the PloneMeeting codebase |
| Second consumer addon | **not delivered as a product** — see below |

**The two adoption halves are not mine to complete**, and the mission brief says so: *"Phase 5 starts only
when I explicitly hand you a pilot addon."* Migrating PloneMeeting's notifications needs that codebase, and
a genuine second product needs a real add-on.

Three add-ons already ship templates through the real entry-point mechanism —
`tests/dummies/dummy.minimal`, `tests/dummies/dummy.complete` and
`recipe/tests/consumer/emailkitdemo` — so §9's *"two independent addons shipping templates"* is
**technically satisfied**. It is not counted as met here, because they are test doubles and counting them
would be exactly the quiet redefinition the earlier phases avoided.

## Evidence

```
$ python -m pytest tests/test_contentrules.py -q      72 passed
$ python -m pytest tests -q                          566 passed, 1 skipped, 2 xfailed
$ cd recipe && python -m pytest tests -q             115 passed, 1 skipped
$ make check                                         exit 0    (pyroma 10/10)
$ make check-emails                                  exit 0    (both §5 gates)
$ zconsole … scripts/verify_install.py               ALL EXIT-CRITERION CHECKS PASSED
```

A real fired rule, on a real site:

```
GATE 1  element in ZCML   title: Send styled email   addview: imio.emailkit.actions.StyledMail
GATE 2  vocabulary from discovery
        tokens: ['dummy.complete:convocation', 'dummy.complete:notification',
                 'dummy.minimal:notification', 'imio.emailkit:notification']
GATE 4  one message per language group
        nl.lid@gemeente.example.be    Subject: Melding        lang: nl
        fr.membre@commune.example.be  Subject: Notification   lang: fr
        parts: ['text/plain', 'text/html']
GATE 5  [nl] cta label: Deze inhoud bekijken   inline styles: 20   unresolved ${}: []
        [fr] cta label: Consulter ce contenu   inline styles: 20   unresolved ${}: []
```

Gates 6–9 are asserted **both ways**: `RecipientError` / `TemplateNotFound` raise *and* `mailhost.sent ==
[]`. Gate 9 asserts the whole triangle — pending, `aborted == 1` (2 for two language groups), and commit
delivering — so §6.2's transaction guarantee is proven to survive the executor rather than assumed. Gate 8
executes a stock `MailAction` for real and confirms it is unmodified.

## The reversal, and it was my error

An earlier revision registered the action element as a **GenericSetup local utility** so it would live in
`:default` and not `:base`. I reverted it to a plain `plone:ruleAction` ZCML directive.

**The cause was my brief**, which said "register in `profiles/default/`, not `base`". That is only
satisfiable through a local utility, and the implementer honoured it correctly. Three reasons it was wrong:

1. **The mission's own rule** — "if a solution needs a paragraph to justify its cleverness, it's the wrong
   solution." The justification needed several, including a `component=` vs `factory=` subtlety about GS's
   factory branch needing an OFS item.
2. **The pickled-singleton cost is a silent drift.** A GS registration stores a *copy*, so a title change
   reaches an existing site only when someone re-applies the profile — no symptom, which is the defect
   class these five phases exist to eliminate.
3. **§8.2's opt-out is about not restyling stock mails, not hiding an action type.** An action type is
   inert until a rule uses it, and the vocabulary is empty of useful entries without registered templates.

**The gate got stronger, not weaker.** It now asserts global registration, that the site lookup returns
*the same object*, and that the site has **no registration of its own** — so a silent slide back to a local
utility fails. A `:base`-only site is asserted to *have* the action type, with a sibling test that
`IEmailkitLayer` is absent so the two cannot be confused.

**What made the catch possible:** the implementer surfaced the tradeoff explicitly, priced it ("a two-line
change if you'd rather"), and said it departed from convention. It should also have escalated when the
justification started needing paragraphs — and so should I have noticed when writing the brief.

## Decisions the spec left open

- **`cta_label` is a msgid, not a translated string.** `.with_context()` runs **once**, before `.send()`
  groups by language, so translating there would send one language's wording to every recipient. This
  generalises: *anything user-facing passed through `.with_context()` should be a msgid.* Now in the README.
- **The render context is five fixed names** (`item`, `title`, `intro`, `cta_label`, `cta_url`). A template
  wanting more **fails loudly** rather than producing a mail with a gap. Consumers needing more send from
  their own code.
- **The owner resolves as a userid, not an address**, so the member adapter supplies `fullname` *and*
  `language` and per-language sending works from a rule.

## Accepted cost, flagged not hidden

`IRuleElementDirective.title`/`description` are `TextLine`/`Text`, not `MessageID`, so the action's entry
in the content-rules panel is **English** — exactly like Plone's own "Send email" and "Notify user". The
strings are extracted into the `.pot` and translated for FR/NL/DE, but inert until `plone.contentrules`
changes those fields. Everything *inside* the action's own forms is translated normally, verified in four
languages.

## Handover

What the maintainer needs for the rest of Phase 5:

1. **A pilot addon.** Then: register its templates via the entry point (`tests/dummies/dummy.complete` is
   the worked example), and either author purpose-built templates or drop existing bodies into the shell —
   the README's *"Migrating a mail you already send"* covers both routes.
2. **The two open spec questions** — §6.3-vs-§6.2 on the send-test language, and whether to register the
   shell so `Email("imio.emailkit:shell")` works. Both are `strict` xfails, so the suite goes red if
   someone makes either pass without settling it.
3. **Dark mode in a real client.** Structurally verified only; the send-test button makes it a five-minute
   check against Gmail and Outlook.
4. **The recommended ninth lint rule** for `i18n:domain` — the consumer-facing silent failure Phase 4
   found.
