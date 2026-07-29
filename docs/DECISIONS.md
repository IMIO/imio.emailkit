# Decision log — `imio.emailkit`

Every choice `SPEC.md` leaves open, and every deviation considered, is recorded here:
context, options, choice, why. A decision that would contradict the spec is not recorded
here — it is escalated to the maintainer first.

Newest entries at the top.

---

## 2026-07-29 — Plaintext: table cells get a ` | ` separator (approved fix)

**Context.** `naive_text()` broke lines on `</tr>` but not on `</td>`/`</th>`, so adjacent cells
concatenated: a header row rendered as `PointDécision` and a data row as `Budget 2026approuvé`.

**Why it matters more than it looks.** Legacy notification bodies (§9 phase 3) are table-heavy, and
`render_shell` has **no plaintext twin to fall back on** — naive extraction *is* its plaintext part,
by design. So this was the plaintext quality of every migrated PloneMeeting mail.

**Choice.** `</td>`/`</th>` become ` | `, and the separator the last cell leaves at end of line is
stripped. A row therefore stays on one line and stays readable:
`Point | Decision` / `Budget 2026 | approuve`.

**Why a separator and not a line break.** One cell per line loses the row structure entirely, which is
worse for a table than a slightly noisy separator.

**Process note.** The workstream that found this deliberately did **not** fix it, because it changes
`render()`'s fallback output and therefore committed golden files — a decision plus approval, not a
quiet edit. That was the right call and the fix was then made deliberately.

---

## 2026-07-29 — `render_shell` injects no preheader, and has no plaintext twin

**Context.** Plan §4 gate 2 listed the preheader among the shell's defaults; §4 of the spec makes the
`.txt.pt` twin the primary plaintext path.

**Choice 1 — no preheader.** The shell's first visible text is already the subject, so filling the
hidden line with it would spend the entire inbox snippet repeating what the client already displays.
Left empty, the div collapses and clients continue the snippet into the legacy body, which carries
information. This contradicts the plan's gate wording; the template that owns the slot won the
argument. The layout's runtime `preheader` path is untouched, so a future `preheader=` argument
forecloses nothing.

**Choice 2 — no `shell.txt.pt`.** A twin could not exist even in principle: its only content would be
`body_html`, which is HTML, so the twin would put tags in the plaintext part. Naive extraction is
therefore the **designed** path here, not §4's missing-twin fallback, and it emits no deprecation
warning.

---

## 2026-07-29 — Pathological bodies all render; a pasted `<html>` document yields invalid HTML

**Context.** Plan §2 item 3 asked what happens to unclosed tags, a `<style>` block, and a whole
`<html>` document dropped into the shell.

**Measured answer: all three render, none fails loudly.** Also verbatim and without exception: a bare
`&`, `--` inside a comment, a stray closing tag, an unquoted attribute, uppercase `<FONT>`, an MSO
conditional, and a naked `<`. The reason is the same one that makes the slot safe: Chameleon parses the
*template* at compile time, and the body is inserted as a string afterwards, never parsed.

**The one case worth knowing.** A pasted full `<html>` document produces output with `<html>`, `<body>`
and `<!DOCTYPE>` **twice** — technically invalid HTML that mail clients tolerate in practice.

**Choice.** Left as is. Plan §5 forbids cleaning, and the alternative is the shell silently rewriting a
consumer's markup. Recorded as the documented answer rather than papered over; a `check-emails`-style
warning for a consumer that does this is a reasonable Phase 4 lint addition.

---

## 2026-07-29 — Two documented routes for sending a legacy body, and neither adds a builder method

**Context.** Plan gate 8 said "`Email(...)` can send a shell-rendered body with no builder change".
That is true of the **message assembly**, verified end to end — but `Email` always renders internally
from a template *name*, so there is no way to hand it a `render_shell()` pair.

**Consequence, and it is a happy one.** Consumers have two routes, both with no new API, and they
should be documented as distinct:

1. **Already own their sending code** (PloneMeeting calls MailHost directly today) →
   `render_shell(subject, body_html)` + `build_message(...)`.
2. **Want the builder** → `Email("imio.emailkit:notification").with_context(body_html=<legacy>, …)`,
   because the kit layout defines the `body_html` slot for **every** template, not just the shell.
   Verified: the legacy body is injected on that path too. This route additionally keeps the
   registration's subject and preheader and the hand-authored `.txt.pt` twin, which `render_shell` has
   neither of.

**Why recorded.** Route 2 was not designed; it falls out of the layout owning the slot, and it is
strictly better than route 1 for a consumer willing to register a template. Worth telling people.

---

## 2026-07-29 — Additions around §6.2 that the spec does not describe

Recorded after a spec review found them undocumented. None changes §6.2's nine-method surface; all are
things the spec is silent about, and the agent contract says silence gets an entry rather than a quiet
choice.

**1. `.send()` returns the list of built `EmailMessage` objects.** §6.2's example discards the return
value and the spec says nothing about one. The send-test needs it, and §7's assertions need it.
Returning data the caller can ignore does not make the builder grow behaviour.

**2. Three fail-loud errors the spec does not enumerate.**

| Condition | Raises | What it replaces |
|---|---|---|
| zero recipients at `.send()` | `RecipientError` | a silent no-op that looks like a successful send |
| no subject anywhere (registration and `.subject()` both absent) | `EmailkitError` | `[No Subject]` on the wire |
| `plone.email_from_address` unset | `EmailkitError` | MailHost's `"Message missing SMTP Header 'From'"`, which never names the registry record |

§6.2 defines `RecipientError` for *unresolvable* recipients; "none at all" is the same class of mistake
and gets the same error rather than a new one. No new exception classes were introduced.

**3. `.reply_to()` and `.sender()` accept the full polymorphic recipient set.** §6.2 shows only a
literal address for `reply_to` and scopes "string / member / userid / iterable" to `.to()/.cc()/.bcc()`.
Accepting the same values through the same adapter means one resolution path instead of two, and
`.reply_to(item_author)` works. Signatures are unchanged, so this is a widening of accepted input, not
a change to the surface.

**4. §6.3 says "renders **each** in an iframe"; the page renders the selected one.** Per-template
iframes would render every registered template on every page load, and the language switcher and token
panel are page-global. Functionally complete — every template is reachable — but a departure from the
wording, noted rather than left implicit.

---

## 2026-07-29 — FIXED: a member with two addresses in `email` was silently dropped

**Context.** §6.2 is emphatic: "fail loud, not silent drop".

**Finding.** The `str` adapter refused a multi-address string, but the **member** adapter did not.
`parseaddr("a@b.be, c@d.be")` returns `('', '')`, so the header came out as `Full Name <>` and that
recipient **vanished from the envelope while every other recipient in the same call was delivered** —
no `RecipientError`, no warning. It is the same defect that was found and fixed for
`.sender("Greffe <greffe@commune.be>")`, on the one path that had not been fixed.

**Fix.** The member adapter now runs the same `getaddresses` length check and returns `None`, which
`resolve()` turns into a `RecipientError` naming the member. It also *parses* a
`"Zoe <z@b.be>"`-shaped property instead of passing it through, so an address can never end up nested
inside another display name, and falls back to the parsed display name when the member has no
`fullname`.

**Why it is worth an entry.** Silent recipient loss is the worst failure this package can have — the
sender believes the mail went out. The lesson generalises: both halves of a polymorphic contract need
the same guard, and the second half is the one that gets forgotten.

---

## 2026-07-29 — `structure` does NOT evaluate placeholders in an injected body (verified)

**Context.** Phase 3's `render_shell(subject, body_html)` drops arbitrary legacy HTML into the shell
with `structure` (§3 rule 4's one sanctioned use). Legacy notification bodies are often assembled by
string concatenation, so one could plausibly contain `${...}`. If Chameleon evaluated that, an
attacker-influenced or merely careless body could read the render namespace — a security question, not
a cosmetic one.

**Verified empirically before building anything on it.** A compiled template doing
`tal:content="structure body_html"` was rendered with
`body_html = '<p>Bonjour ${member/fullname} and ${python:__import__("os").environ}</p>'` and a real
`member` in the namespace:

```
rendered: <div><p>Bonjour ${member/fullname} and ${python:__import__("os").environ}</p></div>
literal ${member/fullname} preserved : True
did it evaluate to LEAKED            : False
python: expression evaluated         : False
```

**Conclusion.** `structure` inserts the string as markup **data**, not as a template. The page template
is compiled once and the injected characters are never re-parsed as TAL. **No template injection is
possible through `body_html`.**

**What `structure` does still mean, by design.** The body is inserted **unescaped**, so it can carry
arbitrary markup — that is the entire purpose of the slot, and §3 rule 4 reserves `structure` for it
precisely because it is the one place markup is wanted. The consequence is ordinary HTML injection,
which in a mail body is bounded by what mail clients render (they strip scripts) and by the fact that
the body already came from the sending application. The shell therefore **wraps and does not
sanitise**: silently rewriting a consumer's markup would be a worse failure than rendering it.

---

## 2026-07-29 — The MailHost test double replaces `_makeMailer`, not `_send`

**Context.** §7 names one test explicitly: "Transaction abort test: `.send()` + abort → MailHost queue
empty."

**Finding.** The obvious double, `Products.CMFPlone.tests.utils.MockMailHost`, overrides **`_send`** —
which is precisely the method that forks between the transaction-joined path and the immediate one. On
that double the message lands in the mock's list at `.send()` and **survives an abort**. §7's test
would therefore be *untestable while looking tested*: green, and proving nothing.

**Choice.** The double replaces **`_makeMailer`**, one level below the fork, so real
`Products.MailHost` and real `zope.sendmail` code runs. A queued delivery then has three observable
states — pending, delivered, cancelled — and the abort test asserts `sent == []` **and**
`aborted == 1`: positive proof that a delivery was joined and then cancelled, not merely that nothing
appeared. A real `transaction.commit()` counterpart proves the same message does arrive.

**Why it matters beyond this test.** It is the same category as every other finding in this project: a
green result that carries no information. Recorded so nobody "simplifies" the harness back to the
stock mock.

---

## 2026-07-29 — `attach(bytes, filename="x.dat")` raises rather than defaulting to octet-stream

**Context.** §6.2: "`filename` and `mimetype` are inferred where the source carries them … and
required for `bytes`; missing/unguessable metadata raises `AttachmentError` at `.send()` time,
consistent with `RecipientError` (fail loud, not silent drop)."

**Reading taken.** The literal one. An extension `mimetypes.guess_type` cannot resolve raises
`AttachmentError`; it does **not** fall back to `application/octet-stream`.

**Why.** The spec names "unguessable" as an error condition in the same breath as fail-loud, and
`application/octet-stream` is the kind of plausible default that gets a document delivered as an
unopenable blob to a commune with no explanation. The caller knows what they are attaching and can say
so in one keyword argument.

**Revisit if** a real consumer hits it often with legitimately opaque payloads; the change is one line
and a decision entry.

---

## 2026-07-29 — §6.3 and §6.2 contradict each other on the send-test language; §6.2 wins

**Context.** This is not spec silence — it is the spec disagreeing with itself.

- §6.3: the Send test button "mails the currently previewed template + fixture + **language** to the
  logged-in user's own address".
- §6.2: `Email` has **no language argument**. It "groups recipients by resolved language, renders
  once per language group". The language comes from the *recipient*, never from the caller.

So §6.3 asks for something §6.2's frozen surface cannot express.

**Options.** (A) add a language argument to `Email` or `.send()`; (B) set `request["LANGUAGE"]` around
the send; (C) temporarily rewrite the member's `language` property; (D) accept §6.2's rule and make
the preview *show* the truth.

**Choice.** **D.**

**Why.** (A) changes the frozen §6.2 surface, which needs approval and would also break the one-rule
model — a per-send language override and per-recipient grouping would then both exist. (B) was
implemented and **measured inert**: previewing `de` still mailed `fr`, because
`recipients.default_language()` deliberately reads the *site* default rather than the request. (C) is
silent mutation of a user's stored preferences to work around a UI mismatch.

**What the view does instead.** It computes the send language from §6.2's own public contract —
`IEmailRecipient(member).language or default_language()` — labels the button with it ("Send test to
… **in fr**"), and warns when it differs from the preview switcher, pointing the developer at their
own preferred-language setting. The preview switcher still does what §6.3 wants for *rendering*; only
the *mail* follows §6.2.

**Flagged for the maintainer.** §6.3's wording may want correcting, since as written it promises
something the frozen builder cannot do.

---

## 2026-07-29 — ZCML using a CMF permission must include `Products.CMFCore`'s `permissions.zcml`

**Context.** The preview view is `permission="cmf.ManagePortal"` (§6.3: Manager-only).

**Finding.** The instance **died at startup** with
`ComponentLookupError: (IPermission, 'cmf.ManagePortal')`. `cookiecutter-zope-instance` writes a
`site.zcml` that includes `imio.emailkit` *before* `<five:loadProducts />`, so
`Products.CMFCore/permissions.zcml` has not run when our directives execute — the permission is not
merely misspelled, it does not exist yet.

**Choice.** An idempotent `<include package="Products.CMFCore" file="permissions.zcml" />` beside the
directives that need it, same placement rationale as the existing `z3c.jbot` include.

**Why recorded.** Any future ZCML in this repo using a CMF permission hits this, and the error message
points at the permission name rather than at include ordering — an easy hour lost concluding the name
is wrong.

---

## 2026-07-29 — The `--`-in-a-comment hazard applies to ZCML and XML, not just `.pt`

**Context.** Recorded earlier for Chameleon templates (caveat A2). It is more general than that entry
implies, and has now cost time four separate times.

**Finding.** `--` is illegal inside *any* XML comment, so it breaks **ZCML at instance startup** and
GenericSetup profile XML at import, not only compiled templates at render time. Occurrences so far:
a `.vue` authoring comment, `profiles.zcml`, `profiles/uninstall/browserlayer.xml`, and
`adapters.zcml` (which blocked instance startup while it was diagnosed).

**Choice.** No `--` in any comment, anywhere in the repo. The compiled `.pt` output is guarded
structurally by the comment stripper; ZCML and XML are not, so this is discipline plus a Phase 4 lint
check. Prefer `;` or a full stop.

---

## 2026-07-29 — `@@emailkit-preview` is registered on `IEmailkitLayer`, unlike `@@emailkit_theme`

**Context.** Two views, two different registration scopes, deliberately.

**Choice.** The preview view is on `IEmailkitLayer`, so a `:base`-only site does not get it. The theme
view is on the default layer, so a `:base`-only site does.

**Why the asymmetry.** `@@emailkit_theme` is needed at *render* time — a `:base` site still renders
its own templates and must reach the tokens, so narrowing it would remove §8.2 level 2's escape
hatch. The preview view renders nothing that anything else depends on; it is a developer tool, and a
site that opted out of the default profile has not asked for it.

---

## 2026-07-29 — Plaintext twins live in `emails/twins/` and are copied into the package

**Context.** The previous entry put the hand-authored twin at
`src/imio/emailkit/templates/notification.txt.pt`, beside the compiled output, because §4 resolves
twins as `<directory>/<name>.txt.pt`.

**Finding — data loss.** `maizzle build` **empties its output directory**, silently. It deleted the
committed twin. Reproduced deliberately: unrelated files dropped into `templates/` were also gone
after a build. Maizzle 6.0.7 exposes no `output.clean` / `emptyOutDir` option. `make check-emails`
masked it, because its restore trap put the snapshot back — so only `make build-emails` lost the
file, and only for someone who then committed.

**Choice.** Twins are source and live in **`emails/twins/`**. `make build-emails` copies them into
`src/imio/emailkit/templates/` after Maizzle has run; `make check-emails` reproduces the copy and
then diffs, so the twins are covered by the staleness gate again rather than skipped as orphans.

**Why not the alternatives.** Authoring twins as `.vue` templates that Maizzle emits via
`useOutputPath()` would put them inside the build, but every transformer would then run over
plaintext and each twin would need its own `useTransformers: false` — clever, and clever is what §3
warns against. Protecting `templates/` with a stash-and-restore trap in `build-emails` would work
only for people who go through `make`.

**Cost.** `emails/` is pruned from the sdist, so the twins ship only as the copies under `src/`,
which is what §4 needs. The source is in git, one directory away.

---

## 2026-07-29 — Dark mode uses attribute selectors, and depends on Maizzle stripping `!important`

**Context.** §3 lists dark mode among `Main.vue`'s responsibilities; it was deferred out of Phase 1
as OPEN.

**Choice.** One `@media (prefers-color-scheme: dark)` block in `kit/tailwind.css`, keyed on
`data-dark="page|surface|body|muted"` attributes that `Main.vue`, `Panel.vue` and `DataTable.vue`
put on the surfaces they own. Every declaration `!important`.

**Why attribute selectors.** `css.purge` only models `class=` and `id=`, so an attribute selector is
outside what it can match — there is nothing for it to fail to find. Demonstrated: a
`[data-dark="body"] li` rule survived into all three compiled templates even though no `<li>` exists
anywhere in the kit. `css.purge.safelist` was rejected because it puts the guard in the build config,
a different file from the rule it protects.

**The dependency that makes it work, and could silently break it.** `css.inline` has already
flattened the light theme into `style` attributes, and an inline declaration beats a media query. This
works *only* because Maizzle **drops `!important` when it inlines** — verified: no inlined `style`
attribute contains `!important`, so the light side never competes back. That is undocumented
behaviour. If a future Maizzle preserved `!important` on inlining, dark mode would die with a green
build. Recorded here so the next person has somewhere to look.

**Scope, honestly.** Verified only structurally: rules survive purge, sit in a real `<style>` in
`<head>`, and come out of Chameleon byte-intact. **Nothing has been seen in an actual dark-mode
client** — that needs §6.3's send-test. Outlook Windows ignores `prefers-color-scheme` entirely, so
the light rendering remains self-sufficient and this is purely additive. The `[data-ogsc]`
Outlook.com path is not attempted.

**Accepted losses.** Small print inside the content well flattens to the body colour (no structural
difference to select on — both are `<p>`; font size still carries the hierarchy), and the
`DataTable` head row loses its tint (told apart by `<th>`'s bold weight). The dark greys
(`#14161a` / `#23262b` / `#e9eaec` / `#b7bbc2`) are **invented** — the kit has no brand dark
neutrals. Contrast is 12.8:1 body and 9.5:1 footer, comfortably RGAA, but the exact values are open
to being overruled.

---

## 2026-07-29 — `render()` injects `target_language`, and injected names beat the caller's context

**Context.** §6.1 enumerates what `render()` injects: the context, `theme/*`, `portal_url`,
`translate`, the three locale helpers, and `lang`. Two things go beyond that list.

**1. `target_language`.** Zope's page-template i18n machinery reads the render language from this
name. Without it, `i18n:translate` negotiates from the *request* — so passing `language="nl"`
renders French to a Dutch recipient, **silently**, which is precisely the failure §6.2's
per-language sending exists to prevent. Injected deliberately.

**2. Precedence.** Low to high: the registration's `preheader`, then the caller's `context`, then
the names this package injects. §6.1 is silent on collisions.

**Why injected names win.** The kit layout uses `theme`, `lang` and `target_language`
unconditionally. A caller who shadowed one would break the shell for everyone, not just their own
template — a much worse failure than losing a name they chose badly. The caller still owns every
name the kit does not.

---

## 2026-07-29 — `Main.vue` has a named `preheader` slot as well as the msgid path

**Context.** §3/§4 define the preheader as coming from the registration's optional `preheader`
msgid, rendered into the hidden div ("omitted → the div collapses to nothing").

**Finding.** The two Plone-default mails have no registration — a stock view renders them — so the
msgid path cannot reach them, and they would ship with an empty preheader: the highest-visibility
line in the inbox, blank, on the two mails Phase 1 exists to improve.

**Choice.** `Main.vue` also exposes a named `preheader` slot, which the two default mails fill with
build-time markup. The runtime msgid still wins whenever it is present.

**Why recorded.** It is a second mechanism for one spec concept, which is exactly the shape of thing
that should not be invented quietly. It is narrow (build-time fallback only, runtime always wins)
and it exists because §8's stock-view constraint leaves no alternative.

---

## 2026-07-29 — Plaintext hygiene: hidden elements and zero-width characters are stripped

**Context.** §4's fallback is "naive text extraction", and §6.1 returns a plaintext part.

**Finding.** The naive extraction kept the hidden preheader `<div>`, so every plaintext mail opened
with the inbox-preview line followed by ~20 invisible filler characters (U+2007, U+FEFF, U+034F)
that the kit adds to fill the preview budget, plus a stray zero-width joiner. That had been
committed as the expected golden output.

**Choice.** `naive_text()` drops elements hidden with `display:none` and strips zero-width
characters. Separately, `notification` now ships a **hand-authored `notification.txt.pt`**.

**Why the twin too.** §4 makes the twin the primary path and the fallback the deprecated one, yet no
twin existed anywhere in the repo — the specified path was unexecuted code while only the deprecated
path was covered. The twin also produces genuinely better output: it includes the CTA **URL**, which
naive extraction drops with the `<a>` tag.

**Two consequences.**

- The staleness gate ignores `*.txt.pt`: twins are hand-authored **source**, not build output, and
  the gate would otherwise report every twin as an `ORPHAN`.
- `render()` re-checks that the twin still exists before rendering it. `text_path` comes from the
  cached startup scan, so a rebuild or a branch switch can leave it naming a deleted file; that
  raised `FileNotFoundError` instead of §4's warn-and-fall-back. Found only once a twin existed to
  lose.

---

## 2026-07-29 — No formatter may touch `SPEC.md` or `docs/`

**Context.** `make format` invoked `ruff format` with no path argument, so it walked the whole repo.

**Finding.** Ruff's preview formatter rewrites fenced Python blocks inside markdown. It reformatted
`SPEC.md` — collapsing §6.2's fluent `Email(...)` builder chain onto a single line. Semantically
harmless, but it is an edit to the **approved source of truth**, made by a tool, unnoticed, and it
destroyed the readability of the one illustration of the frozen API.

**Choice.** `SPEC.md` and `docs/` are in ruff's `exclude`; `make lint`/`format` pass explicit
`RUFF_TARGETS=src tests scripts`. The reformatted `SPEC.md` was reverted to the committed original.

**Why.** The spec is an input to this project, not a source file in it. Nothing automated is
entitled to edit it, and belt-and-braces is warranted because the damage was silent.

---

## 2026-07-29 — `@@emailkit_theme` is registered for the default layer, not `IEmailkitLayer`

**Context.** The view exists so a stock-view-rendered mail can reach the theme tokens.

**Choice.** Registered `for="*"` on the default browser layer with `permission="zope2.View"`, so it
is traversable on a `:base`-only site too.

**Why not `IEmailkitLayer`.** That layer only exists under `:default`. A site that installed `:base`
to keep Plone's stock mails still wants the tokens available to its own templates, and narrowing the
registration would take that escape hatch away for no gain: the view exposes three branding values
a visitor can already see in any mail they receive.

---

## 2026-07-29 — Uninstall DOES remove the theme records

**Context.** Plone's instinct is never to destroy settings on uninstall, and the first
implementation left `imio.emailkit.theme.*` in place on that basis.

**Finding that overrides it.** These records are defined by an interface shipped in this egg,
and `plone.app.registry` resolves that interface when reading them. Once the egg is gone,
`IEmailkitTheme` is not importable and **the registry control panel raises** on the orphaned
records.

**Choice.** `profiles/uninstall/registry.xml` removes them with `remove="true"`.

**Why.** A broken control panel is a hard, site-wide failure. The three values lost are branding
for mails that no longer exist, and reinstalling re-creates the records from the interface
defaults — the real cost is re-entering a logo URL and a colour. Preserving settings is a good
default; it is not worth a broken control panel.

---

## 2026-07-29 — §8.2 level 2 reaches the two shipped mails by a different mechanism

**Context.** §8.2 level 2 offers theme tokens as the branding-only override path, and it works
for both consumer templates and the two Plone-default mails — but **not by the same route**, and
the difference is worth knowing before someone debugs it.

**How it differs.** For consumer templates, `render()` injects `theme` into the namespace. For the
two jbot-hosted mails there is no `render()` call, so the override template reaches the registry
directly (via `@@emailkit_theme`). Verified working in both paths.

**Consequence.** The stock view's namespace also has **no locale helpers** — a jbot-hosted override
cannot call `format_datetime` (`NameError`) — and no `theme` variable of its own. Anything a
default-mail template needs must come from the registry, the view, or `options`.

**Why not unified.** Unifying would mean owning the view that renders those mails, which §8
deliberately avoids ("no new mechanism", jbot only). Two routes to the same three tokens is the
cheaper trade.

---

## 2026-07-29 — `zpretty` must never touch the compiled `.pt` files

**Context.** The house lint runs `zpretty` over `src`. The compiled templates live under `src`.

**Finding.** `zpretty`'s formatting is not Maizzle's, so letting it rewrite the generated `.pt`
files puts two gates in direct conflict: `make check` would reformat them and `make check-emails`
would then report them stale **forever**.

**Choice.** `zpretty` is pointed at hand-written markup and configuration only (`*.zcml`, `*.xml`),
never at `templates/` or `browser/overrides/`. Recorded in the Makefile at the point of use.

**Why this way round.** When a formatting gate and a correctness gate disagree, the correctness gate
wins: `check-emails` is what stands between a stale template and production.

**Related.** `ruff` excludes `spike/` (throwaway Phase 0 evidence, slated for deletion) and
`.claude/` (agent definitions whose fenced examples are illustrative, not runnable).

---

## 2026-07-29 — `is_product_installed()` is False on a `:base`-only site

**Context.** §8.2 level 3 makes `:base` a first-class install, not a half-installed state.

**Finding.** Plone's quick-installer answers "was the `default` profile applied?", so on a
`:base`-only site `is_product_installed("imio.emailkit")` returns `False` even though the runtime is
fully present and working.

**Choice.** Accept the quirk; do not add a shim. Tests check `portal_setup` profile versions
instead, and the README documents it.

**Why.** It is Plone's definition of "installed", not ours to redefine, and §8.2's opt-out is about
which *profile* you applied. A shim would misreport the opposite way for anyone reading the
add-ons panel.

---

## 2026-07-29 — RESOLVED (§4.2): plaintext twins are hand-authored, not generated

**Context.** §4 requires a `<name>.txt.pt` twin "placeholders intact"; §6.1 returns `(html, text)`.
Phase 1 was to settle generation with evidence.

**Finding.** Maizzle's plaintext output is unusable as a `.txt.pt`. Measured: `${}` survives, but
every `tal:`/`i18n:` construct is destroyed — conditionals vanish, header lines come out empty,
`i18n:translate` freezes at the English default, and `structure body_html` disappears entirely.

**Choice.** Twins are **hand-authored** where plaintext quality matters. Where absent, `render()`
uses §4's documented naive-extraction fallback with a startup warning and a once-per-template
logged deprecation. Maizzle's `plaintext` option is not used.

**Why.** A generated twin that silently loses conditionals and translations is worse than no twin:
it would ship a plausible-looking plaintext body with the wrong content in the wrong language. §4
already anticipated the fallback, so nothing downstream changes.

**Phase 1 scope.** The two default mails need no twin — the stock view sends a single body whose
`Content-Type` the template declares. `notification` exercises the fallback path.

---

## 2026-07-29 — Four more silent-failure modes in the Maizzle→Chameleon seam

**Context.** Phase 1's kit work surfaced four defects that, like every Phase 0 caveat, produce a
**successful build**. Recorded because each needs a permanent guard, and two of them mean Phase 0's
committed output was subtly wrong.

1. **`@import "@maizzle/tailwindcss"` cannot live in `kit/tailwind.css`.** Tailwind resolves bare
   specifiers by walking up from the *importing* file, and a kit directory inside an egg has no
   `node_modules` ancestor. **Maizzle catches CSS errors and ships the uncompiled stylesheet with
   exit 0** — so this fails completely silently. Fix: `Main.vue` emits the import itself (where
   Maizzle's PostCSS plugin rewrites it to an absolute path) and `@import`s the kit CSS by absolute
   path. This is a documented deviation from §3's implied `tailwind.css` role: the file holds the
   `@theme` tokens, not the framework import.
2. **`<Outlook :open="…" />` with an empty slot emits `<!--[endif]---->`** — a `--` inside a
   comment, i.e. caveat A2, making the `.pt` unparseable by Chameleon. Use real slot content, or
   `v-html`.
3. **The formatter breaks conditional comments across lines, and Chameleon then re-serialises them
   as `<!--[if mso ]>…<! [endif]-->`.** Outlook silently ignores **every** MSO fallback.
   **Phase 0 shipped this latent** — its single-line comments happened to mask it. Fix: a
   `flattenConditionalComments` pass in `afterTransform`.
4. **`htmlWhitespaceSensitivity: 'ignore'` breaks the line between an inline element and following
   punctuation**, rendering "account x ." — and because that text is also the `i18n:translate`
   default, the stray space is baked into the `.pot`. `'css'` or a larger `printWidth` fixes the
   prose but breaks the conditional comments or the line-granular diffs, so the fix is a narrow
   `unbreakPunctuation` pass instead.

Also: **`Subject: <span i18n:translate=…>` needs `tal:omit-tag=""`.** Without it the header ships as
`Subject: <span>Reset your password</span>` — a corrupt mail header. The Phase 0 spike had this bug.

**Why this matters more than the individual fixes.** Every one of these is invisible to the build
and to a browser preview. It is now the settled position of this project that **the Maizzle exit
code carries almost no information about correctness**, and that the only trustworthy gates are the
committed-output diff (§5) and rendering assertions on substituted values (§7).

---

## 2026-07-29 — Theme tokens colour cells via `bgcolor`, not `style`

**Context.** The amended theme-token decision settled on `tal:attributes="style string:…"`.

**Refinement.** For background colours the kit uses `bgcolor="${…}"` rather than a `style`
attribute. `bgcolor` is never parsed as CSS, so caveat A1 cannot apply to it, and it remains the
most bulletproof way to colour a table cell across mail clients. `tal:attributes="style string:…"`
stays the rule for anything that genuinely needs CSS.

---

## 2026-07-29 — `lang` chain includes `request/LANGUAGE`

**Context.** Plan §4.1 gave `Main.vue` the chain `lang | options/lang | string:en`.

**Finding.** Under the two jbot-rendered stock mails neither `lang` nor `options/lang` is present,
so every mail rendered `lang="en"` — defeating §3's `lang` a11y default and the FR/NL/DE
requirement outright.

**Choice.** `lang | options/lang | request/LANGUAGE | string:en`. Verified to yield
`<html lang="fr">`.

---

## 2026-07-29 — OPEN: dark mode in `Main.vue`

**Context.** §3 lists "dark mode" among `Main.vue`'s responsibilities.

**Status.** Phase 1 ships only `color-scheme` / `supported-color-schemes` meta tags, not real
`prefers-color-scheme` CSS. Flagged rather than silently skipped.

**Why deferred.** A working dark-mode block needs element-level (class-free) selectors to survive
`css.purge`, plus per-client testing that browser previews cannot give. Scheduled with the
send-test button (§6.3, Phase 2), which is the first point at which it can actually be verified in
Outlook and Gmail.

---

## 2026-07-29 — `@@emailkit_theme` view: how theme tokens reach a stock-view-rendered mail

**Context.** §8.2 level 2 says branding adjustments happen through the three theme tokens in
`plone.app.registry`. §6.1 has `render()` inject `theme/*` into the namespace. But the two
Plone-default mails are rendered by a **stock view**, so `render()` never runs and nothing puts
`theme` in the namespace.

**Finding.** Without a route, `Main.vue`'s `theme | options/theme | nothing` fallback resolved to
`nothing` and the layout fell back to its hard-coded default colour — the registry was **silently
ignored for exactly the two mails Phase 1 ships**. §8.2 level 2 was broken where it mattered most.

**Choice.** A small browser view, `@@emailkit_theme`, returning the token mapping from the
registry. `Main.vue`'s chain becomes
`theme | options/theme | context/@@emailkit_theme | nothing`.

**Why.** A view is the boring Plone mechanism for "expose some data to a template that a view I do
not control is rendering", and it costs one file. Verified: a registry value of `#123456` reaches
the rendered stock mail and the kit default disappears.

**Scope note.** Not in §6's API surface, and not a builder method, so §6.2's freeze is untouched.
Recorded because it was added outside the original workstream brief.

---

## 2026-07-29 — Locale helpers use `zope.i18n` CLDR, not `plone.api.portal.get_localized_time`

**Context.** §6.1 requires `format_date`, `format_datetime`, `format_number` "bound to the render
language", and describes `render()` as a "pure function of (template, context, registry state)".

**Options.** (A) `plone.api.portal.get_localized_time` / Plone's `translation_service`;
(B) `zope.i18n`'s CLDR locale data.

**Choice.** **B.**

**Why.** (A) formats in the *request's* negotiated language and needs a request, a portal and the
translation service. It cannot be pointed at an arbitrary language, which §6.2's per-language
sending requires, and the request dependency contradicts §6.1's "pure function… used directly by
previews and tests".

**Trade-off, accepted knowingly.** Plone's control-panel date-format overrides do **not** reach
mails. Given that emails are a separate visual channel with their own shell, that is defensible;
if a client ever needs it, the helper is one function to change.

**Sub-decisions.** Date length `long`, time length `short`, because zope.i18n's bundled CLDR data
is stale: `medium` fr/nl dates emit two-digit years and `long` times append a broken `+000`.
Also noted: `fr` groups thousands with NBSP while `fr-BE` uses `.` — Belgian French differs from
French French, which matters for this audience.

---

## 2026-07-29 — Locale helpers must be called as `${python: format_date(x)}`

**Context.** §6.1 injects the helpers into the render namespace.

**Finding.** TAL **path** expressions cannot call functions: `${format_date(when)}` raises
`Invalid variable name`. The working form is `${python: format_date(when)}`.

**Choice.** Document it as a §3 authoring rule and add it to §5's lint checks in Phase 4.

**Why recorded.** It is exactly the class of mistake this project keeps finding: it is a *parse*
error rather than a silent one, so it fails loudly — but authors will hit it constantly, and the
lint is nearly free.

---

## 2026-07-29 — Default-mail templates are built once and copied to the jbot overrides dir

**Context.** §8 states the restyled Plone mails are "authored, compiled, discovered, tested and
shipped exactly like consumer templates". §4's discovery resolves `<directory>/<name>.pt`, while
z3c.jbot demands a **dotted** filename such as
`Products.CMFPlone.browser.login.templates.mail_password_template.pt`.

**Finding.** Phase 1's first pass emitted the compiled output only into `browser/overrides/` under
the dotted names, so discovery skipped both templates and `available_templates()` came back empty
— §8's "discovered … exactly like consumer templates" was false.

**Options.** (A) build to `templates/<name>.pt` as canonical, then copy to
`browser/overrides/<dotted>.pt`; (B) register discovery against the dotted names; (C) accept that
the two default mails are jbot-only and amend §8.

**Choice — revised to (C).** Option A was chosen first and is **withdrawn**: it does not work.

**Why A fails.** Copying the file makes it *discoverable* but not *renderable*. These two templates
are rendered by a stock Plone view, so per Phase 0 caveat D2 they must speak the hosting view's
dialect (`options/…`, `python:member.getProperty('…')`) — `MemberData` cannot be path-traversed at
all. `render()` supplies a flat context and would fail on them wherever the file sits. The blocker
is the **dialect**, not the path, so relocating the file only produces a registration that raises
`TemplateNotFound`'s cousin at render time. Measured by the kit workstream.

**What we do instead.** The two default mails are jbot-only and are not registered as discoverable
templates. `templates/notification.pt` — an ordinary template in the flat dialect — is what
demonstrates and tests the normal consumer flow end to end.

**Consequence for §8.** Its claim that the default mails are "authored, compiled, discovered,
tested and shipped exactly like consumer templates" is true for *authored, compiled, tested and
shipped* but **not for discovered**, and cannot be while a stock view renders them. §8's dogfooding
intent still holds: they go through the same kit, the same build, the same staleness gate and the
same golden tests. Recorded as a spec correction rather than engineered around.

---

## 2026-07-29 — jbot wiring: include the whole `z3c.jbot` package, never just `meta.zcml`

**Context.** §8.1 registers the jbot directory on `IEmailkitLayer`. How jbot itself is loaded is
not specified.

**Finding.** `<include package="z3c.jbot" file="meta.zcml"/>` registers only the `browser:jbot`
*directive*. The `ViewPageTemplateFile.__get__` monkeypatches live in `z3c.jbot/configure.zcml`.
With `meta.zcml` alone, the directive parses, the `TemplateManager` is built with the correct path
mapping, and **the stock template still renders — silently**. No error, no warning.

**Choice.** `<include package="z3c.jbot"/>`. In a real instance `z3c.autoinclude` handles it, but
`PLONE_FIXTURE` disables autoinclude, so the test layer must include it explicitly and must not
rely on autoinclude.

**Why it matters beyond the one line.** This failure mode is invisible to any test that asserts
only "the override file was resolved". Every jbot test in this project must assert on **rendered
output** — a positive assertion that our markup appears and the stock markup does not. Recorded
because it nearly produced a green test for the wrong reason.

---

## 2026-07-29 — OPEN: how kit templates reach data when hosted by a stock Plone view

**Context.** §8 has our compiled templates replace stock Plone mail templates via jbot. §6.1 has
`render(template, context)` for our own templates. The two paths have different namespaces and the
spec does not reconcile them.

**Finding.** A jbot override is rendered *by the stock view*, and view kwargs land in `options`,
not at top level (`Products/Five/browser/pagetemplatefile.py` → `pt_getContext(..., options=keywords)`).
So `${member/fullname}`, `${reset_url}` and `${lang}` do not resolve against
`PasswordResetToolView`. Additionally **`MemberData` is not path-traversable at all** —
`${member/email}` raises `LocationError` even bound top-level, which is why the stock template
uses `python:member.getProperty('email')`.

**Options.**

- **A — the kit layout emits a `tal:define` preamble** mapping `options/member` → `member`, etc.,
  so authored templates always see flat names regardless of who renders them.
- **B — a kit-owned view class** registered on `IEmailkitLayer` exposing flat, traversable names,
  with jbot overriding only the template.
- **C — accept two dialects**: `options/…` + `python:` expressions for Plone-default overrides,
  flat names for our own templates via `render()`.

**Status.** Open, decided in Phase 1 when `Main.vue` and `render()` are both being written — they
are the two ends of this seam. Leaning A, because it keeps one authoring dialect (§3's whole
premise is that authors learn one set of rules) and puts the adaptation in kit-owned markup where
§3 already puts `lang`, `role="presentation"` and `i18n:domain`. C is explicitly the fallback, not
the goal.

**Why not decided now.** This is a template-authoring constraint, not a pipeline defect, and
choosing well needs the real `Main.vue` in front of us. Phase 0's job was to prove it is a
constraint at all.

---

## 2026-07-29 — §3 AMENDMENT: theme tokens use `tal:attributes`, not a literal `style` attribute

**Context.** §3 specifies that kit components emit theme tokens as
`style="background-color: ${theme/primary_color}"` — "Chameleon placeholder, literal in build
output". Phase 0 proves this does not work.

**Finding.** Juice parses every `style` attribute as CSS, so the `{` opens a block. Two effects,
both silent (the build reports success):

1. the closing `}` is eaten — output is `style="background-color:${theme/primary_color"`, which
   at runtime is not an expression at all, just broken literal text;
2. **CSS inlining stops for the entire document.** One such attribute anywhere took the spike
   template from 31 inline styles to 6.

Measured on identical source, changing only the token form:

| Form | Inline `style` attrs |
|---|---|
| `style="background-color: ${theme/primary_color}"` (§3 as written) | 6 — inlining dead |
| `tal:attributes="style string:background-color: ${theme/primary_color}"` | 31 — correct |

Evidence: `spike/build/theme-token-literal.pt`.

**Choice.** Kit components emit theme tokens via
`tal:attributes="style string:<prop>: ${theme/<token>}"`.

**Why this is not really a deviation.** §3 rule 2, two paragraphs below the sentence being
amended, already blesses exactly this construct: "Conditional styling at runtime uses
`tal:attributes="style ..."` with literal values." The spec's own idiom was already correct; only
the theme-token sentence pointed at the wrong mechanism. The three tokens, the registry records
and the locked-kit model are all unchanged.

**Consequence.** §3's rule 2 is upgraded from cautious advice to a hard constraint, and it now
covers `style` as well as `class`: **no Chameleon placeholder may appear in a literal `style` or
`class` attribute, ever.** Both are `bin/check-emails` lint rules (§5).

---

## 2026-07-29 — Compiled output must have authoring comments stripped

**Context.** Not addressed by the spec.

**Finding.** Chameleon refuses to parse `--` inside an HTML comment
(`ParseError: The string '--' is not allowed in a comment`). An ordinary em-dash-style comment in
a `.vue` source therefore makes the compiled `.pt` unparseable **at runtime**, while the build
reports success. `css.purge` strips only some comments; Maizzle 6 has no comment-removal option.

**Choice.** Strip authoring comments in an `afterTransform` hook, preserving Outlook conditional
comments (load-bearing markup, recognised by `[if` / `[endif]`, including the downlevel-revealed
form). Reference implementation: `spike/maizzle/strip-comments.js`. Moves into the kit's shared
base config in Phase 1.

**Why.** Authoring commentary should not ship in a transactional email regardless; stripping is
the right default and it makes the `--` hazard structurally impossible rather than a lint rule
authors must remember.

---

## 2026-07-29 — `Main.vue` must emit `i18n:domain`

**Context.** §4/§8.1 assume `i18n:translate` translates. Phase 0 found the compiled output
contained **zero** `i18n:domain` declarations.

**Finding.** Without a domain, every `i18n:translate` renders its msgid as an untranslated
default — **indistinguishable from success**, because the msgid text appears in the output either
way. Only after declaring `i18n:domain="imio.emailkit"` did substitution actually occur.

**Choice.** The kit's `Main.vue` emits `i18n:domain="imio.emailkit"` on `<html>`.

**Why there.** The kit owns that markup, so §3 rule 1 (no `tal:`/`i18n:` on kit components from
*consumers*) is untouched, and no author has to remember it — same reasoning §3 already applies
to `lang` and `role="presentation"`.

---

## 2026-07-29 — §6.1 `render()` uses `Products.PageTemplates.PageTemplateFile`; §4's jbot claim corrected

**Context.** §4 states "z3c.jbot works on the resolved `.pt` files (per-site or per-client
overlays), no additional mechanism". §6.1 describes rendering "through Chameleon".

**Finding — two independent constraints converge on the same class.**

1. **Path expressions.** Standalone `chameleon.PageTemplateFile` has no TAL path expressions:
   `${member/fullname}` raises `NameError: fullname`. Plone-idiomatic `/` paths need Zope's
   engine.
2. **jbot reach.** z3c.jbot 3.1 patches `Products.PageTemplates.PageTemplateFile`,
   `Products.Five...ViewPageTemplateFile`, `zope.pagetemplate`/`zope.browserpage` template
   classes, and CMF skins objects. It does **not** patch `z3c.pt.pagetemplate.ViewPageTemplateFile`
   or raw `chameleon.PageTemplateFile` (both measured `patched_by_jbot=False`).

**Choice.** `render()` loads templates via `Products.PageTemplates.PageTemplateFile`.

**Why.** It is the only option that gives both TAL path expressions and jbot overridability. §4's
claim is true *only* under this choice — as written it would be false if `render()` used bare
Chameleon, which the phrase "through Chameleon" invites. Recorded as a spec clarification.

**Related trap.** The Chameleon engine is a runtime `IPageTemplateEngine` utility registered by
`Products.PageTemplates`' ZCML, reached in Plone only via `plone.z3cform`. Without it,
zope.pagetemplate falls back to zope.tal, where `${...}` passes through **verbatim with no
error** while `tal:repeat` still works. Therefore: tests must assert on *substituted values*,
never on marker strings alone, or a green test can coexist with raw `${}` shipping to production.

---

## 2026-07-29 — §8.2 override story requires extending `IEmailkitLayer`

**Context.** §8.2 level 1 says "register a jbot directory on a *more specific* browser layer…
z3c.jbot layer precedence applies — the most specific layer wins."

**Finding.** True only for a layer that **subclasses** `IEmailkitLayer`. Measured against the
request's `__sro__`: for a child layer, `IEmailkitLayer` ordering is stable regardless of
declaration order; for a **sibling** layer, precedence follows declaration order, which comes
from `getAllUtilitiesRegisteredFor(ILocalBrowserLayerType)` and is effectively arbitrary.
Additionally, multiple jbot directories on the *same* layer sort by directory-path string.

**Choice.** Document §8.2 level 1 as "your site layer must **extend** `IEmailkitLayer`", and say
so in the override docs rather than leaving "more specific" to interpretation.

**Why.** It is the difference between a documented guarantee and a coin flip that happens to work
on the developer's machine.

---

## 2026-07-29 — Plone default-mail subjects: the override template emits its own `Subject:` header

**Context.** §8.1 says subjects are "re-registered as i18n msgids in the `imio.emailkit` domain".

**Finding.** The stock subjects are **Python-side**: `view/mail_password_subject` and
`view/registered_notify_subject` are methods on `PasswordResetToolView` that translate hardcoded
`plone`-domain msgids. z3c.jbot swaps template *files* only, so it cannot reach them.

**Options.** (A) the override template emits its own `Subject:` line with an `imio.emailkit`
msgid; (B) override the view class as well, via an adapter/ZCML registration.

**Choice.** **A.** Plone parses the mail headers back out of the rendered template text
(`message_from_string(mail_text)` in `RegistrationTool`), so a template-emitted `Subject:` is
already the supported path and needs no new mechanism.

**Why.** KISS, and it keeps the whole override inside the one artifact jbot already governs — no
second registration to keep in sync, per §8's "no new mechanism" preference.

---

## 2026-07-29 — Maizzle config gotchas worth encoding in the shared base config

**Context.** Phase 0 lost real time to two silent misconfigurations. Recorded so the kit's
`maizzle.config.base.js` (§3) encodes them once.

**Findings.**

- **Restate every `css` key in the kit's base config.** ⚠️ **The original reason given here was
  wrong and is corrected:** Maizzle merges config with `defu`, which *does* deep-merge — a config
  supplying only `css.purge` still resolves `inline: true`. That claim was an untested hypothesis
  formed while chasing the dead-inlining symptom, whose real and only cause was caveat A1. The
  advice survives on different grounds: §3 has consumers **extend** the base config, and a consumer
  that spreads it (`{...base, css: {…}}`) shadows whole keys, because object spread is shallow.
  Restating the keys makes that shadowing harmless.
- **A top-level SFC `<style>` block never reaches the email** (standard Vue semantics — the
  bundler extracts it). Purge then strips the now-orphaned class from the `class` attribute too.
  Custom CSS must be a real `<style>` **element** inside `<template>`, or live in the kit's CSS
  entry.
- **Maizzle's Tailwind utilities carry `!important`**, so they beat custom CSS of equal
  specificity even when the custom rule comes later.
- **Kit components need a namespace `prefix`.** Maizzle ships a built-in `Button`; an unprefixed
  kit `Button.vue` shadows it. Maizzle throws on genuine two-source collisions rather than
  silently choosing.
- **Kit components must stay import-free.** Vite resolves `node_modules` by walking up from the
  importer, and a `site-packages` directory has no `node_modules` ancestor. Maizzle's
  auto-imports make this free.
- **The raw-escape component is extracted by a naive global regex that also matches inside HTML
  comments.** Mentioning it in angle brackets in a comment swallows the real block and deletes it
  from the output silently. Phase 4 lint rule.
- **Build output is deterministic** (two builds byte-identical) with `html.format: true`, so §5's
  staleness gate works and diffs stay line-granular.

---

## 2026-07-29 — OPEN: plaintext `.txt.pt` twin not yet settled

**Context.** Carried from the pre-Phase-0 entry below. Phase 0 marked assumption (e) non-gating
and did not reach it, once (a) surfaced three caveats worth more attention.

**Status.** Still open, still unblocking: §4 already specifies the runtime fallback ("missing
`.txt.pt` twin → warning at startup, `render()` falls back to a naive text extraction"). Decide in
Phase 1 alongside `render()`, which is where the `(html, text)` tuple is actually built.

---

## 2026-07-29 — GAP / needs approval: development tooling is `uv` + `mxdev`, not buildout

**Context.** `SPEC.md` is silent on how *this repository* is developed and tested. It only
addresses **deployment**: §5 specifies a buildout recipe and rejects buildout-time compilation
because "it would make Node a production dependency across ~350 applications". §7 mentions
`bin/test --update-golden`, which reads as buildout-generated.

**Finding.** `imio.reportproblem` — the reference iMio Plone 6 addon — is a **Cookieplone**
package with no buildout at all: `uv` + `mxdev` + a `Makefile` for dev, constraints from
`dist.plone.org`, `pytest` + `pytest-plone` for tests, `ruff` for lint, `towncrier` for the
changelog, and CI on `plone/meta@2.x` reusable workflows. It carries a deliberate `setup.py`
shim whose docstring explains it exists precisely so the package can still be a `zc.buildout`
develop egg when iMio buildouts check it out into `src/`.

**Reading.** These are not in conflict, they are two layers: **development and CI use
uv + mxdev; deployment uses buildout.** The `setup.py` shim is the seam. This also means §9's
"package-local Makefile precursor" for the preview loop is the *house convention*, not a
stopgap — and §5's recipe serves deployment buildouts, which is where Node must not intrude.

**Options.**

- **A — follow the house convention:** Cookieplone layout, `uv` + `mxdev` + `Makefile` for
  dev/CI, `setup.py` shim for buildout develop-egg compatibility. Consistent with the
  maintainer's own most recent addon.
- **B — buildout for development too**, matching the spec's literal `bin/test` phrasing.
  Diverges from current iMio practice and from the toolchain the CI reusable workflows expect.

**Choice.** **A — approved by the maintainer 2026-07-29.** Cookieplone layout, `uv` + `mxdev`
+ `Makefile` for dev/CI, `pytest` + `pytest-plone`, `ruff`, `towncrier`, `plone/meta@2.x`
reusable workflows, and the `setup.py` shim for buildout develop-egg compatibility. §7's
`bin/test` is read as "the project's test entry point", not literally a buildout-generated
script.

**Why.** Consistency with the maintainer's own most recent addon, and it is the toolchain the
`plone/meta` reusable CI workflows expect. Deployment remains buildout; the `setup.py` shim is
the seam between the two layers. §9's "package-local Makefile precursor" is therefore the house
convention rather than a stopgap.

---

## 2026-07-29 — RESOLVED (§3 amendment): the kit ships `kit/tailwind.css`, not `tailwind.preset.js`

**Context.** §3 lists `imio/emailkit/kit/tailwind.preset.js` — "email-safe preset (px units,
no CSS vars, safelist)". Maizzle 6 ships Tailwind **4**, which is CSS-first: the Maizzle docs
state flatly that "Tailwind CSS 4 is configured in CSS, there's no `tailwind.config.js`
anymore", and v5's `tailwindcss-preset-email` is replaced by `@maizzle/tailwindcss`, imported
from CSS (`@import "@maizzle/tailwindcss";`) with theme tokens in an `@theme { }` block.
A JS preset file has no supported loading path.

**Options.**

- **A — kit ships a CSS entry instead of a JS preset** (`kit/tailwind.css`): `@import
  "@maizzle/tailwindcss";` plus an `@theme { }` block carrying the email-safe tokens. §3's
  file listing is amended; §3's *intent* (one shared, locked, email-safe Tailwind config
  owned by the kit) is unchanged.
- **B — keep a `.js` preset via Tailwind 4's `@config` escape hatch.** Unverified through
  Maizzle's PostCSS pipeline, which strips `@layer`/`@property` at-rules by default. No
  Maizzle documentation confirms it survives.
- **C — pin Maizzle 5 + Tailwind 3** to keep §3's file layout literal. Contradicts the
  spec's own "built on Maizzle 6" mandate and starts on an EOL toolchain.

**Choice.** **A — approved by the maintainer 2026-07-29.** The kit ships
`imio/emailkit/kit/tailwind.css`: `@import "@maizzle/tailwindcss";` plus an `@theme { }` block
carrying the email-safe tokens. §3's file listing is amended to replace `tailwind.preset.js`
with `tailwind.css`.

**Why.** The only option that is both current and supported. §3's intent — one shared, locked,
email-safe Tailwind config owned by the kit, which consumers compose against but do not extend
— is fully preserved; only the file format changes. Option B (`@config` escape hatch) is
unverified through Maizzle's PostCSS pipeline, and option C (pin Maizzle 5) would contradict
the spec's own Maizzle 6 mandate and start on an EOL toolchain.

**Consequence for the theming model.** §3's "consumers do not extend the Tailwind config" is
now enforced by *where the tokens live* rather than by convention: `@theme { }` sits inside the
kit's CSS entry. The three runtime-variable tokens (`logo_url`, `primary_color`, `footer_html`)
are unaffected — they remain Chameleon placeholders in literal inline styles, not Tailwind.

---

## 2026-07-29 — RESOLVED (§10.2): output extension is configured directly, no post-build rename

**Context.** §10.2 left open whether the Vite pipeline can emit `.pt` directly or whether the
compile script renames post-build, noting "either is fine; rename is the assumed default".

**Finding.** Maizzle 6 has a first-class `output.extension` option (default `'html'`), plus a
`--ext` CLI flag; the maintainers' own documented example is `extension: 'blade.php'`, so
non-HTML extensions are an intended use case. Per-template override is `useOutputPath()`
inside `<script setup>`, which replaced v5's frontmatter `permalink`.

**Choice.** `output: { extension: 'pt' }`. No rename step in `bin/compile-emails`.

**Why.** One fewer moving part than the spec's assumed default, and it is the supported
path rather than a workaround. Verified empirically in Phase 0.

---

## 2026-07-29 — LIKELY RESOLVED (§10.1): `kit-mode = path` is supported by design

**Context.** §10.1 asked whether pointing Maizzle at the egg's kit directory works, or
whether we must fall back to `copy`.

**Finding.** Maizzle 6's `components.source` accepts absolute paths and its own type
documentation says paths are "resolved relative to `cwd` (**not** `root`), so paths outside
the email root directory work as expected". The implementation resolves via `path.resolve`,
which returns an absolute path unchanged. Maizzle renders server-side via SSR, and the
framework never sets `server.fs.allow` — the Vite restriction that would have blocked this
guards browser-fetched files, not SSR disk reads.

**Choice.** Plan for `kit-mode = path` as the default, as the spec prefers. `copy` stays the
documented fallback.

**Residual risks to settle in Phase 0.** (1) the *dev server* path specifically, not just
`maizzle build`; (2) bare `import` specifiers inside kit components — Vite resolves
`node_modules` by walking up from the importer, and a site-packages directory has no
`node_modules` ancestor. Mitigation, if needed: keep kit SFCs import-free and rely on
Maizzle's auto-imports.

---

## 2026-07-29 — Maizzle 6 API/config names differ from the spec's prose; pin `>=6.0.5`

**Context.** The spec was written against Maizzle's v5-era vocabulary. Several names changed
in the Vite rewrite. Recorded so implementation reads the spec's *intent* correctly rather
than its literal option names.

**Findings and consequences.**

| Spec says | Maizzle 6 actually | Consequence |
|---|---|---|
| `removeUnusedCSS` (§3, §9) | `css.purge` — **on by default** in v6 | Same transformer, new name. §9's exit criterion is read as "after `css.purge`". |
| `maizzle.config.base.js` (§3) | `maizzle.config.{ts,js}`, ESM `export default defineConfig({})` | `.js` still accepted, so §3's filename stands. The v5 `build: {}` wrapper is gone. |
| `npx maizzle build production` (§5) | `maizzle build -c production.config.ts` | Corrected in the generated script. |
| "wrapped in `v-pre`" (§3 rule 3) | `v-pre` works; `<Raw>` is the v6 block-level escape | `<Raw>` extracts pre-compile into a static VNode. Prefer `<Raw>` for blocks, `v-pre` for a single element. |

**Additional decisions taken from this.**

- **`css.purge.backend` must be extended.** Its default delimiter shield covers
  Handlebars/Liquid/Jinja (`{{ }}`, `{% %}`) but not Chameleon; add
  `backend: [{ heads: '${', tails: '}' }]`.
- **`html.format` is `true` by default** and re-indents output via `oxfmt`. Since we commit
  generated `.pt` and gate on a byte diff (§5 `check-emails`), evaluate `html: { format:
  false }` in Phase 0 to keep diffs meaningful.
- **Pin `@maizzle/framework >= 6.0.5`**: v6.0.3 fixed whitespace preservation in compiled
  HTML and v6.0.5 fixed entity encoding in comment nodes before purge — both directly affect
  fidelity of committed output.
- **A programmatic Node API exists** (`build()`, `render()`, `createRenderer()`), which is a
  cleaner basis for `bin/preview-emails` (§5) than shelling out to the CLI. Phase 4 concern;
  noted now.
- **`replaceStrings` is a poor tool for injecting TAL** — keys compile to case-insensitive
  global regexes, and `${`, `{`, `}`, `?`, `*`, `+`, `^`, `.`, `|`, `(`, `)` are all regex
  metacharacters present in TAL syntax. Authors use `<Raw>`/`v-pre` instead.

**Why it matters.** §3's authoring rule 2 ("no runtime-computed `class` values") is now
*confirmed load-bearing*, not merely cautious: `css.purge` is `email-comb` plus a DOM-aware
step that only understands `class=` and `id=`, and it will delete class references it cannot
match — including from the `class` attribute itself. Separately, `css.safe` maps `$`→`-`,
`{`/`}`→`` and `:`→`-` inside class atoms, so Chameleon syntax in a `class` attribute is
actively corrupted. Both are exactly the silent-failure modes §5's lint step targets.

---

## 2026-07-29 — GAP: how the `.txt.pt` plaintext twin is produced

**Context.** §4 requires a `<name>.txt.pt` twin per template with "placeholders intact", and
§6.1 has `render()` return `(html, text)`. The spec does not say how the twin is *built*.

**Finding.** Maizzle 6 has plaintext support (a `plaintext` config key, `--plaintext` flag,
and an exported `createPlaintext()`), so the twin can plausibly come from the same build
rather than being hand-written — but only if `${}`/`tal:` survive the HTML→text conversion,
which is unverified.

**Status.** Open. Added to the Phase 0 spike as a cheap extra assertion, since the template
under test already carries every placeholder form. If placeholders do not survive, the
options are a hand-authored `.txt.pt` per template or a `<Raw>`-wrapped text block; that
choice comes back here with evidence.

---

## 2026-07-29 — PyPI name availability checked (spec §10.4)

**Context.** §10.4 requires checking PyPI availability for the planned distribution names
"now regardless" of the deferred `collective.emailkit` split.

**Finding.** All names are unregistered (`GET https://pypi.org/pypi/<name>/json` → HTTP 404,
checked 2026-07-29):

| Name | Status |
|---|---|
| `imio.emailkit` | free |
| `imio.recipe.emailkit` | free |
| `collective.emailkit` | free |
| `imio.mailkit` | free |
| `imio.recipe.mailkit` | free |

**Choice.** No action needed; the names in the spec are available. Recorded so the check is
not repeated. Registration happens at first release, not now.

---

## 2026-07-29 — RESOLVED: repository renamed to `imio.emailkit`

**Context.** The git remote was `github.com/IMIO/imio.mailkit`, but `SPEC.md` names the
distribution `imio.emailkit` throughout (§2 artifacts table, §3 kit path
`imio/emailkit/kit/`, §4 entry-point group `imio.emailkit.templates`, §5 recipe
`imio.recipe.emailkit`, §8 profiles `imio.emailkit:base`/`:default`, registry records
`imio.emailkit.theme.*`).

**Choice.** The maintainer renamed the GitHub repository to `IMIO/imio.emailkit`; the local
remote was repointed to match. Repository name, distribution name and Python namespace all
read `imio.emailkit`, exactly as the spec has it.

**Why.** One name for one artifact. The spec was already unambiguous; the repository was the
outlier.

**Note.** The local working directory is still `imio.mailkit` — cosmetic only, no effect on
packaging, and left alone to avoid breaking in-flight tooling paths.

---

## 2026-07-29 — Subagent definitions live in `.claude/agents/`

**Context.** The mission requires five project subagents (`spec-guardian`, `maizzle-author`,
`plone-dev`, `test-writer`, `researcher`) so exploration and build output stay out of the
main context.

**Choice.** Committed as project-scoped agent definitions in `.claude/agents/*.md`, each
instructed to read `SPEC.md` first and each carrying the subset of §3/§6/§7 rules it owns.

**Why.** Project-scoped rather than user-scoped so the rules travel with the repository and
apply to every contributor's assistant, not just one machine.

**Note.** Claude Code loads the agent registry at session start, so definitions created
mid-session are not selectable until the next session; during this session the same roles
are run with their instructions passed inline.
