# Decision log — `imio.emailkit`

Every choice `SPEC.md` leaves open, and every deviation considered, is recorded here:
context, options, choice, why. A decision that would contradict the spec is not recorded
here — it is escalated to the maintainer first.

Newest entries at the top.

---

## 2026-09-14 — the preview gains a third mode that shows the `.pt` unrendered, and §5's objection to it is what bounds it

**Context.** The preview shows `render()`'s two return values: the HTML part in the iframe,
the plaintext part beside it. Both need a committed fixture, so a template with none shows
nothing at all — an accurate refusal, and a useless one for the two cases where it fires.
Authoring order is the first: the `.pt` is compiled and committed before anyone writes
`tests/fixtures/<name>.py`, and the window in which you most want to look at a new layout is
exactly the window in which the preview declines. A released egg with no source tree is the
second, already documented as the normal production case.

**The objection, which is §5's and is correct.** §5 rejects `maizzle --watch` outright:
its dev server shows *build-time* output — raw `${item/title}`, unexpanded `tal:repeat` —
"a miserable authoring loop, and one that hides exactly the class of bug the authoring rules
are about". A mode that serves the committed `.pt` straight to a browser shows that same
build-time output. Adding one is, on its face, adding back the thing §5 threw out.

**Why it is not the same thing.** §5's objection is to an authoring loop whose *only* output
is unsubstituted markup — one you could work in all day and never learn that
`${item/created}` silently renders nothing. Here the unrendered view is one labelled mode of
three, sitting beside the two that do render, on a page that says in so many words that
nothing is substituted in it. It answers "what does this layout look like"; the two modes
next to it answer "does this template render", which is the question §5 is protecting. The
failure mode §5 names requires the *absence* of the rendering loop, not the presence of a
source view.

**What that bought, and what it did not.** It is deliberately not a fallback: the HTML mode
does not quietly degrade to source when the fixture is missing. It still refuses, still
prints the full explanation of where §7 puts a fixture, and now offers a link to the mode
that needs none. A preview that silently showed you `${item/title}` where you expected a
value would be the §5 failure exactly.

**Two details.** The file is served as `text/html` rather than escaped into a `<pre>`, because
TAL attributes are unknown attributes to a browser and it draws the markup around them —
a `<pre>` would show the CSS instead of applying it, which is the opposite of the point. And
it goes through the new `render.resolved_path()`, so a jbot-overridden template shows the
override: a source view that kept showing the original while `render()` compiled somebody
else's file would be a trap rather than a tool.

`bin/preview-emails` gets the same thing as a `.pt` link per template, written for every
registered template whether its fixture resolved or not — the one artifact in that directory
that cannot fail for lack of a fixture.

---

## 2026-09-14 — v3: the brand artwork enters the shell, and the title band stops being magenta

**Context.** The v3 design (`Modeles email v3`) is one change of subject: the iMio brand
shapes enter the mail as two raster cuts. A head visual sits behind the logo band, and a cap
closes the white body above the negative footer. Everything else about the card is v2.

**The design folder contradicts itself, and the maintainer chose.** `v3/notification-contenu.html`
uses a 400x120 head cut with a #f8f8f8 title band carrying an 80 px tail of the same artwork;
`v3/bienvenue-compte.html` and `v3/reinitialisation-mot-de-passe.html` use a 500x92 cut whose
magenta joins a title band that stays #e6007e, which is also what the design's own notes
describe. Two different mastheads, and the shell can only have one. The maintainer picked the
notification variant, so that is what `KitMain` implements and what all five templates get.

**`primary_color` lost its largest surface, and that is the cost of the change.** The token
painted the title band. It now paints `KitCard`'s rail and `KitButton`'s fill and nothing
else, while the brand colour at the top of every mail is a PNG that is iMio magenta for every
consumer. A commune that sets the token to its own colour therefore gets its own rails and
buttons under iMio's artwork. The token cannot drive a raster; the escape is the resource
directory, where `art-head.png`, `art-head-tail.png` and `art-hero.png` can be replaced
without touching markup, and the design's own notes offer the same escape for official
crops. Recorded rather than solved: a per-site artwork mechanism is a feature, not a
redesign, and nothing has asked for one.

Consequence in the suite: `render_shell`'s output no longer contains `primary_color` at all,
because a shell around a legacy body has no rail and no button. Three `TestThemeTokens` tests
moved onto `logo_url`, which is the token the shell still renders, and a fourth now pins the
absence so the decision is revisited deliberately rather than by accident. Caveat A1's guard
on a colour in a closed attribute is unaffected: `tests/test_theme_tokens.py` keeps it on the
four templates that do paint with the token.

**The head cut is a background; the cap is an image.** Not a style choice. The logo and the
status pill sit ON the head cut, and nothing can sit on an image in a table cell, so the head
has to be a background. Nothing sits on the cap, so it is an image, which is the shape every
client renders without help.

**The url rides on the `background` attribute, never on `background-image`.** This is caveat
A1 again, one step further out. `${asset_base}` inside a literal `style` attribute is the
silent catastrophe the authoring lint exists for, and a background image in CSS means exactly
that. So the runtime half (the url) goes on the `background` HTML attribute, which Juice never
parses as CSS, and the static half (`background-size`, `background-position`,
`background-repeat`) stays in classes that Juice inlines on top. Browsers treat the attribute
as a presentational hint for `background-image` and author CSS outranks a hint, so the two
halves compose; verified in Chrome before the shell was written. `tal:attributes` rather than
a literal value, so an empty `asset_base` drops the attribute instead of emitting a relative
url that would resolve against the reader's webmail.

**NO VML FALLBACK, and this one is a hard limit rather than a judgement.** The design ships a
`v:rect` for Outlook on Windows, which ignores `background-image`. Every way of writing it puts
the url inside an Outlook conditional comment, and **Chameleon does not interpolate a
placeholder inside a comment at all** — the compiled `.pt` ships `${asset_base}` to the
recipient verbatim. Measured, not assumed: Maizzle's `OutlookBg` produced exactly that and
`test_no_unresolved_placeholder_in_html` caught it, which is the one failure this package's
whole suite is built around.

Nothing is lost that Outlook was going to show. Word's engine honours the `background`
attribute on its own, so Outlook renders the artwork; it ignores size, position and repeat, so
it tiles the PNG at natural size from the top left instead of anchoring it at 400x120 top
right. The left third of the cut is transparent either way, so the logo keeps its clear space.
A `v:rect` would have been worse: VML has no equivalent of a sized, anchored background, and
`type="frame"` stretches the art across the full 600 px and drags magenta under the logo. If a
client renders neither, the band is plain white with the logo and the pill intact, which is
the v2 rendering and the fallback the design itself specifies.

**The 3 px `primary_color` rule for a title-less template became a 1 px #d2d2d2 rule.** The
3 px bar was a stub of the magenta flat that used to sit there. With the flat gone the stub
stands for nothing, and a magenta line under artwork that is already magenta reads as a
mistake. What separates the masthead from the content well in v3 is the title band's own
closing rule, so that is what an untitled mail keeps.

**Dark mode: `raised` over `body`, and the artwork is left alone.** The title band is a tinted
block inside the card, which is exactly what the `raised` token already means, and its type
needs `body`. One element cannot carry both `data-dark` values, so the cell takes `raised` and
the table inside it takes `body`; no new token, no new CSS. The two artwork bands set no
background colour of their own, so the card's `surface` flip reaches them through the PNGs'
transparency. What the flip cannot do is recolour a raster: the cuts' opaque light-grey shapes
read as bright white against #1c1c1c. Left as it is. The design has no dark variant of the
cuts, dropping them in a dark client would remove the brand from the one place v3 exists to put
it, and nothing is illegible — the logo, the pill and the title all keep their contrast.

**The pill went white on every tone, on the maintainer's call.** `v3/notification-contenu.html`
gives the info pill a white fill and a solid blue disc icon (`pill-info-solid.png`); the other
two v3 models keep the v2 coloured fills. Shipped as flagged, the pale blue #c7e4f7 fill sat
on the magenta cut washed out. The maintainer extended the design's own answer to all four
tones: white pill, dark label, and the tone carried by a coloured disc under the glyph.

**The colour left the markup entirely.** `KitPill`'s `TONES` was `{fill, ink, icon}` per tone
and is now `{icon}`: the disc is baked into the PNG, so `bg-imio-info` and its three siblings
are generated by nothing. They stay declared in `kit/tailwind.css` as the design system's
semantic palette, in the state `negative` was already in. Consequence worth stating plainly,
because it is a real loss: a pill used to degrade to a coloured fill with a bold label when a
client blocked images, and it now degrades to a bold label on white with no colour anywhere.
Accepted — the label is words and always carried the meaning; the tone only ever carried it
faster.

**Baked into the PNG rather than a coloured cell behind the glyph.** A cell would keep the
colour under image blocking, which is the one real argument for it, and it costs a
`border-radius` that Outlook squares into a coloured box plus three more nested tables to
centre a 14 px glyph in a 22 px cell. The design ships the composited form; a PNG renders
identically everywhere it renders at all.

**Three of the four icons are drawn here, to match the one the design supplied.** Geometry,
so they can be redrawn or replaced by official ones: 48x48 canvas, disc centred at (24,24)
with radius 22, glyph strokes 6 px with round caps, glyph roughly within y 11..35 — all of it
measured off `pill-info-solid.png`. `success` is a check, `warning` an exclamation mark (the
info glyph turned over), `danger` a cross.

Disc colours: `info` #1b6c9c (the design's own), `success` #00e667, `warning` #e6da00,
`danger` #c8102e. Light disc takes a #1c1c1c glyph, dark disc takes a white one, which is the
rule the pill LABELS followed before the fill left the markup. The blue and the red remain the
two values that are not charte colours, for the reason already recorded: the iMio palette has
no blue at all and no red distinct from the dark magenta. Their standing is unchanged and the
substitution got cheaper — it is now four files in `browser/static/` and no markup.

**`mail_password_template` moved from `warning` to `info`, which retires the warning triangle.**
The case for `warning` was that this is the one mail whose link stops working. The case against
won: this mail and `get_username` carry the same label, "Your account", and two mails saying the
same words while showing different colours and different glyphs assert a distinction that does
not exist. v3 sharpened it — reduced to a disc, the difference was a yellow circle with an
exclamation mark against a blue one with an `i`, and an exclamation mark on a password mail
reads as "something is wrong with your account", which is the one thing it must not imply. The
deadline is stated where it belongs, in the callout that can give the actual date. `warning`
and `danger` now ship with no template using them; they stay, because the tone set is public
API and a consumer's own template is exactly where an incident mail would live.

---

## 2026-09-11 — The registration mail stops claiming an account needs activating

**Context.** The "an account has been created for you" mail said *Activate my account*, under
an *Activation deadline*, pointing at an `activation_url`. Plone activates nothing.
`RegistrationTool.registeredNotify` runs after the account exists and is usable;
`RegisteredNotifyView.build_context` calls `portal_password_reset.requestReset()` and builds
an ordinary password-reset url. There is no pending state and nothing the recipient can fail
to do that leaves the account unusable.

The wording was not merely imprecise. A reader told to activate looks for a state change, and
one whose link has expired reasonably concludes the account is dead — when the answer is
"use forgotten password". Raised by the maintainer, who was right.

**What changed.** `email_registered_notify_created`, `_cta`, `_expiry` and the preheader
reworded around choosing a password; the callout reuses `mail_password_template`'s
`email_callout_link_validity` instead of a second msgid saying the same thing about a
different imaginary thing, and `email_callout_activation_deadline` is gone. The context key
`activation_url` became `password_url`. FR, NL and DE moved with them.

**The card carries three rows now**, on the maintainer's call: username, full name, email
address. The card's `#title` went with it — it held the fullname, which is now a row, and a
title repeating the row under it is the one thing a rail card must not do. The email comes
from the `email` kwarg `registeredNotify` already passes (it reads it off the member and
validates it before deciding to send at all), with `member.getProperty("email")` as the
fallback for the other callers the `for="*"` registration allows.

**The sign-off went too.** "Kind regards, <email_from_name>" was the pre-v2 layout's way of
closing a mail that had no footer. The v2 shell names the sender in the banner subtitle and
again in the footer, so it was a third repetition.

**A trap in the i18n loop, worth more than this entry.** `python -m imio.emailkit.locales`
marks an entry `#, fuzzy` when the msgid's English default changes — and **msgfmt skips
fuzzy entries**, so a mail whose wording was edited and correctly retranslated in all three
`.po` files still went out in English. Nothing failed: the sync reported "0 added, 0
removed", the `.mo` timestamps were newer than the `.po` files, and the golden files were
regenerated from the same broken catalogs, so they agreed with the bug. It was visible only
by reading a rendered preview in French. Recorded in `SKILL.md` next to the other
silent-failure modes: after rewording an existing msgid, clear the fuzzy markers and
recompile, then read the output in a language you can check.

---

## 2026-09-11 — `preview-emails` serves the kit's resources and owns its own `portal_url`

**Context.** The preview rendered the v2 fidelity work and showed almost none of it. Every
image in the design, and now the Quicksand stylesheet too, is gated on
`tal:condition="asset_base"`, and `asset_base` is built from `portal_url`, which is empty
without a request. The header logo, the status pill's icon, the footer mark and the web
font were therefore *absent* — no markup, no broken-image icon, no warning. A tool whose
stated purpose is "what render() produces, not what Maizzle emits" was silently dropping
the four things that make the design recognisable, and the module docstring recorded the
empty `portal_url` as a known limitation rather than as the bug it had become.

The gating itself is right and stays: a golden file and a unit test *should* render no
image, because a relative `/++resource++…` in an inbox is a broken-image icon. What was
wrong is that the preview inherited a degradation meant for a render with no reader.

**The preview now stands in for the site on this too.** `seed_portal_url()` points
`render.portal_url` at the preview server's own base url, and the request handler answers
`/++resource++<package>/<file>` out of each project's `browser/static`. That is the same
move `seed_theme()` already makes for `plone.app.registry`, in the same place, for the same
reason — the preview is a site-less renderer that substitutes the few site-shaped things
`render()` reads.

**Monkeypatching, not a context key.** `render()` injects `portal_url` into the namespace
itself, and an injected name beats anything the caller passes (SKILL.md's pitfall 14), so
there is no way in through the context. Changing `render()` to defer to a caller-supplied
value was rejected: it would loosen a production API to fix a dev tool.

**A trap inside the fix.** `from imio.emailkit import render` gets the `render` FUNCTION,
not the `imio.emailkit.render` module — §6.1 spells the public API that way, so
`__init__.py` rebinds the name and shadows the submodule. Written the obvious way, the
patch assigns an unused attribute to a function object, patches nothing, and the preview
goes on dropping every image with no error at all. It is `importlib.import_module` for that
reason, with the reason next to it.

**The resource name is a convention, not a lookup.** `++resource++<dotted package name>`,
because that is how `browser:resourceDirectory` is registered here. Reading the real name
means parsing each package's ZCML for a directive this tool otherwise has no reason to
know about; a consumer that names its directory something else loses images in the preview
and nothing else.

**Scope of the path check.** The handler resolves the file and requires the resource
directory to be one of its parents. This binds to 127.0.0.1 and serves a developer's own
checkout, so the url is attacker-controlled in no meaningful sense — but `..` reaching an
`open()` is the kind of code that gets copied somewhere it does matter.

---

## 2026-09-11 — v2 fidelity pass: what a side-by-side with the mockups still showed

**Context.** The v2 shell and components landed structurally correct, but rendering the
four mockups next to the four goldens in one page showed the result reading as a different
design. The gaps were not in the bands; they were in what the kit ships with, what a block
claims for spacing, and three pieces of markup. Recorded together because they were found
together, in one comparison, and because the comparison is the method: the design is a
picture, and only a picture disagrees with it.

**The white band was empty out of the box.** `logo_url` is a registry token with no default
and no sensible one — it is the *consumer's* product logo, which a shared kit cannot know —
so every site rendered a blank 46 px strip until someone filled the record in, which is
every site on the day it is installed. The shell now falls back to a kit-shipped
`imio-logo.png` at 110 px. iMio built every consumer of this package, so its own mark is
the one honest placeholder; a site that sets `logo_url` is unaffected.

**The footer lost two thirds of itself.** Every mockup ends on three blocks (the sender's
contact details, who runs the service, the mark); the shell had the first and the third.
The middle line is the kit's own signature and identical for every consumer, so it is a
msgid (`email_footer_powered_by`) rather than a fourth registry token nobody would fill
in. `footer_html` remains the first block and stays site-specific.

**Spacing compounded at the bottom of every mail.** `KitCard`, `KitPanel`, `KitDataTable`
and `KitButton` carried `my-5`; a mail ending in a button spent 20 px of button margin plus
the well's 24 px of padding, 44 px where the design draws 22. They now carry `mt-5` and
nothing underneath, which is the mockups' own model (each row is `padding: <gap> 40px 0`
and only the last sets a bottom). This is forced rather than stylistic: `:last-child` does
not survive CSS inlining, so "except the last one" cannot be expressed at all, and the only
stable rule is that no block claims space under itself.

**The button's click target was the label.** Padding sat on the `<td>` with a bare inline
`<a>` inside, so a recipient who aimed at the coloured area around the text hit nothing.
The anchor is now `display: block` and carries the padding, with `mso-padding-alt` on the
cell for Word's renderer. A bug fix that happened to be found by a fidelity pass.

**Outlook's square corners are kept, deliberately.** The mockups give Outlook a
`<v:roundrect>`; it needs a width in pixels, which a component whose label is a translated
slot cannot know, and a `width` prop measured by hand would be wrong in at least two of the
three languages shipped. Ghost padding (`mso-text-raise` and a spacer `<i>`) sizes a fluid
button without a width but does not round it, so it would buy nothing `mso-padding-alt`
does not. Padding, colour and click target are right in Outlook; only the corners are not.

**Two buttons stacked where the design draws a row.** `KitButtonGroup` is the row, with
`#primary` and `#secondary` named slots. Named rather than one default slot because a
component cannot wrap children it has not been told about, and the 12 px gap would then
have nowhere to live; naming them also states the design's rule in the API, that the pair
is one primary action with an alternative and never two equal choices.

**The rule between `KitDataList` rows had no way to exist.** The mockups draw a 1 px rule
between rows and none under the last. Written as a bottom border it needs omitting on the
final row, which is the same `:last-child` problem as above; written as a *top* border it
needs omitting on the first, and "first" is something `tr + tr` knows without being told.
So the rule lives in `kit/tailwind.css` keyed on `KitDataList`'s own class, Juice inlines it
onto the matching cells at build time, and `KitDataRow` carries the two cells. `KitDataRow`
may be a component where `KitDataTable`'s rows may not: a data list is a fixed handful of
pairs, never a `tal:repeat`, so SPEC §3 rule 1 does not bite.

**The copy-this-link fallback was plain grey text.** A client that autolinked it styled it
its own way, and one that did not left the reader retyping a sixty-character url by hand.
It is now a real `<a>` in `#b3004b`, with `data-dark="accent"` so it moves to `#ffadd9`
where `#b3004b` is about 2:1.

**The preheader was hidden with `display: none` alone**, which Outlook.com strips from a
block element. It now carries the five further declarations every mail framework converged
on, as the mockups write them.

**Quicksand is served from the portal, not from Google.** The kit had no web font at all,
on the reasoning that remote fonts in mail are unreliable and privacy-hostile. The second
half is the real objection and it is specific to Google: a font fetched from
`fonts.gstatic.com` reports the IP address, the time and the mail client of every citizen
who opens a message from a Walloon local authority. Self-hosting from
`++resource++imio.emailkit` costs 30 KB in the egg and leaks nothing, and reaches exactly
the clients the mockups' own Google Fonts link reached (Apple Mail, iOS, Thunderbird,
Samsung). Delivered as a `<link>` to a stylesheet rather than an `@font-face` block in the
document, because the url must carry `${asset_base}` and a Chameleon placeholder inside a
`<style>` element is parsed as CSS by Juice, which kills inlining for the whole document
while the build still exits 0. An `href` is never parsed as CSS.

**The dark ramp was invented and is now the mockups'.** The `data-dark` block used a
blue-tinted ramp (`#14161a` / `#23262b` / `#2b2f36` / `#e9eaec` / `#b7bbc2`) answering to
nothing. It is now the greys the mockups' own dark model uses (`#121212`, `#1c1c1c`,
`#242424`, `#d2d2d2`, `#a8a8a8`, accent unchanged at `#ffadd9`). Those are **not** charte
colours and the mockups flag them as awaiting sign-off, same standing as the two pill
fills above. Reused anyway so the package has ONE unvalidated dark ramp rather than two:
the deferred fourth model is a forced-dark alert, and a client flipping a normal mail has
to land on the colours that model is drawn in.

**`<title>` is runtime-only, and that is a parser limit.** Vue treats `<title>` as a
rawtext element exactly as it treats `<style>`, so a `<slot>` written inside it is escaped
into literal text and shipped. A Chameleon placeholder is plain text and survives, so the
element renders for a template whose title is *data* and not for one whose title is a
translated slot. `tests/support.head_of` excludes it from the shell/authored parity
assertion for that reason: a title is content, and it is the only part of the head that
varies with the context.

**A trap worth naming: `<style>` written in prose inside an HTML comment.** The authoring
lint's `markup_only` blanks everything between a literal `<style>` and the next `</style>`,
comments included, so a comment mentioning the element by name swallows its own `-->` and
the next comment's `<!--` is reported as a stray `--`. Spell it `&lt;style&gt;` in prose.
The same shape is already a named rule for `<Raw>` (`raw-in-comment`); this one is not, and
the failure surfaces as a `comment-double-dash` violation pointing at the wrong line.

**What is still not done.** The fourth model, the forced-dark technical alert, remains
deferred on the same reasoning as the entry below. Outlook's button corners stay square.

---

## 2026-09-11 — The v2 design: the shell owns the title, and two pill colours are not charte yet

**Context.** The v2 email design (`Modeles email v2`, four models) replaces the pre-v2
shell: a white card on an #ededed canvas, with a white logo band, a `primary_color` title
banner, the content well and a negative footer. Three of its four models map onto mails
this package already ships. The fourth, a forced-dark technical alert, does not, and is
deferred — no template needs it, its greys are marked unvalidated in the design itself,
and a forced-dark variant would double the shell's colour logic to serve nothing.

**The title moved, and that is a contract change.** Templates used to write their own
`<h1>` into the content well. The banner is where the design puts a title, and a banner is
the shell's, so `KitMain` now renders the heading. Two ways in, and the difference is not
cosmetic: a `#title` SLOT is build-time markup and the only shape that can carry
`i18n:translate`, which is what a title that is *wording* needs; a `title` NAME in the
render context is a runtime string, which is what a title that is *data* needs. The three
restyled Plone mails take the slot, `notification` and `shell` take the name.

A template that supplies neither gets the pre-v2 3 px `primary_color` rule where the
banner would be. That is the compatibility hinge, and it is a partial one: a template
with no `title` in its context keeps rendering exactly as before, but a template that
*has* one and still writes its own `<h1>` now prints the title twice — once in the banner
and once in the well. Both dummy add-ons did, which is how it was caught; porting is one
deleted line per template, and it is visible on the first preview rather than silent.

**`shell.pt` keeps its heading on `subject`, through the slot.** The obvious move was to
have `render_shell` pass `title` and let the layout's runtime path handle it. That path
resolves through `title | options/title | nothing`, so a caller who omitted the subject
would get a silently headless mail — exactly what `TestTheCompiledShellRequiresASubject`
exists to prevent. `shell.vue` therefore fills the `#title` slot with `${subject}`: a bare
name with no `|` default, so the compiled artifact still raises `KeyError` on a missing
subject. `render.py` is unchanged.

**Two pill fills are not charte colours.** `KitPill`'s `info` (#c7e4f7) and `danger`
(#c8102e) come from the design, which flags them itself: the iMio palette provides neither
a blue nor a red distinct from the dark magenta, and communication has not signed them
off. Options were to substitute charte colours now (`pink-soft` and `negative`, both
already tokens with the right contrast) or to ship the design as drawn and flag it. Ship
as drawn, on the maintainer's call. `kit/tailwind.css` carries the substitution next to
the tokens, so reversing it is a two-line change and nothing else moves — the tone names
are semantic, not colour names.

**Images had to become browser resources.** The pill icons and the footer's iMio logo are
the first raster assets the kit needs, and a mail client fetches an image over HTTP days
later, from outside the site. So: a `++resource++imio.emailkit` directory, and an
`asset_base` the shell builds from `portal_url`. `portal_url` is empty whenever there is
no request, so every one of those images carries `tal:condition="asset_base"` and is
simply absent from such a render. Emitting a relative `/++resource++…` instead would put a
broken-image icon in the inbox, which is worse than no icon; both places degrade to
something still legible.

**Dark mode grew two tokens.** `raised`, because the v2 layout nests three fills (card,
rail card, metadata table) where the old one had a single white surface, and one dark fill
for all three flattens the layout to one colour. And `accent`, because the card and
callout overlines are #b3004b, which is about 2:1 on a dark surface; without it the
`[data-dark="body"]` rule wins and the last brand accent in the content well goes grey.

**One wording change, and its translations.** The account-activation mail's opening
sentence no longer names the username, which now has a labelled row in the rail card —
which is what the design's own "bienvenue" model does. The msgid is unchanged but its
interpolation is (`${username}` is gone), so FR, NL and DE were edited with it. A
translation left carrying the old placeholder would have rendered it unresolved.

---

## 2026-09-11 — SUPERSEDES "Default-mail templates are built once and copied to the jbot overrides dir": `imio.emailkit` owns the two stock views

**Context.** `mail_password_template` and `registered_notify_template` were `z3c.jbot`
overrides of stock CMFPlone page templates. jbot could reach them, so jbot was used, and
§8's "no new mechanism" pointed the same way. The earlier entry recorded the consequence
honestly and moved on: they are rendered by a stock view, so their bodies use
`options/…` and `python:member.getProperty(…)`, `render()` can never render them, and
§8's claim that the default mails are "authored, compiled, discovered, tested and shipped
exactly like consumer templates" was true for every verb except *discovered*.

**What that cost, concretely.** Not discovered means not previewable. The password-reset
mail — the single most likely thing a commune wants in its own colours — was the one mail
nobody could open in `bin/preview-emails` or `@@emailkit-preview`. It had no fixture and
no golden files, so its rendered output was only ever asserted through the stock view. And
an author touching it had to learn a dialect used by exactly two files in the package:
kwargs in `options`, a `MemberData` that is not path-traversable at all, no locale helpers,
no `theme`, plus a hand-written `Subject:` header in a Maizzle `useDoctype()` block where a
forgotten `tal:omit-tag=""` ships `Subject: <span>Password reset request</span>`.

**Choice.** Own the views. `browser/default_mails.py` registers `mail_password_template`
and `registered_notify_template` under the same `name`, `for` and `permission` as stock,
differing only by layer, subclassing `PasswordResetToolView` so `encoded_mail_sender`,
`construct_url`, `expiration_timeout` and `portal_state` stay stock's. Each builds a flat
context and renders a registered template through `render()`.

**Why this is not a new mechanism.** It is the *existing* one.
`browser/login_help.py` has owned the `login-help` view since the beginning, because stock
Plone has no template for the username reminder and jbot had nothing to key on. Its
docstring already said what the pay-off was: "because we own the view, the template speaks
the flat dialect, renders through `render()` and goes out through the `Email` builder. It
is therefore genuinely discovered, golden-tested and previewable." The only reason the
other two were different is that jbot *could* reach them, which turned out to be a reason
to use jbot rather than a reason it was right.

**What could not move.** `RegistrationTool` does not send what the view returns: it runs
`message_from_string()` on it and pulls `Subject`/`To`/`From`/`Content-Type` back out, then
hands the whole string to `MailHost`. So the return value must still be an RFC822 document.
That block is now built in Python from data, which is the single biggest gain: the subject
is a msgid in the §4 registration like every other subject in the package, translated per
recipient by the same code path, instead of markup in a template.

**Consequences, all verified.**

- Four registered templates, one dialect, one preview list: `bin/preview-emails` goes from
  6 previews to 12.
- `registered_notify_template` formats its expiry through the kit's `format_datetime`,
  bound to the *recipient's* language. Stock used `context.toLocalizedTime`, which follows
  the request — a Dutch member got a French date whenever a French visitor triggered it.
- A site layer now overrides `imio.emailkit.templates.mail_password_template.pt` rather
  than the CMFPlone file. §8.2 level 1 is unchanged in mechanism and simpler in
  description: one filename convention for every template the package ships.
- No `browser:jbot` directory is registered any more. `<include package="z3c.jbot" />`
  **stays**, and the comment above it now says why: the `ViewPageTemplateFile.__get__`
  patches are what `render()._page_template` invokes so a consumer can override *our*
  resolved `.pt` (§4's last bullet), and what keeps stock's `login_help.pt` overridable
  where `login_help.py` reuses it by path. Removing it is silent — no error, no warning,
  overrides simply ignored.
- `tests/test_golden.py::test_the_default_mails_are_not_registered_for_discovery` is
  inverted into `test_every_shipped_template_is_registered_for_discovery`, and
  `tests/test_preview.py`'s matching negative becomes
  `test_the_default_mails_are_listed_too`. If a future template genuinely cannot go
  through `render()`, those are the tests that will say the decision changed back.

**Cost accepted.** We own a stock calling convention: the kwargs `mailPassword` and
`registeredNotify` pass. `tests/test_default_mails.py::test_stock_kwargs_are_what_we_build_from`
pins them against the upstream source, the same drift guard `login_help.py` carries for its
fork of `update()`. This is not new coupling — the jbot templates read `options['member']`
and `options['reset']` and would have broken on the same upgrade, less visibly.

**Not done.** The mails stay single-part `text/html`, exactly as stock sends them. A
`multipart/alternative` would be ours to assemble and `RegistrationTool`'s to mishandle.
The plaintext twins exist and are rendered, for the preview and for completeness; the
hosting tool discards that half today.

---

## 2026-08-05 — Template registration moved from an entry point + dict to the `<emailkit:templates>` ZCML directive

**Context.** §4 registration rode on a setuptools entry point pointing at a module-level
dict, scanned once at startup and cached. It worked, but it was not the idiomatic Zope
registration mechanism: duplicate names silently overwrote each other, there was no
`overrides.zcml` story, and msgid domains had to be wired by hand through a
`MessageFactory`. The runtime also carried a scan/cache/warm-up dance
(`invalidate_cache`, `warm_cache` on `IDatabaseOpenedWithRoot`) purely to simulate what
ZCML execution gives for free.

**Decision.** Replace the entry point with a `meta:complexDirective`,
`<emailkit:templates>`/`<emailkit:template>`, defined in `imio.emailkit`'s own
`meta.zcml` (`src/imio/emailkit/zcml.py`). Each `<emailkit:template>` becomes a
configuration action that resolves the `.pt`/`.txt.pt` files on disk and writes one
entry into a plain module-level registry (`src/imio/emailkit/discovery.py`) — no scan,
no cache, no warm-up subscriber: ZCML execution *is* the startup scan, so the
missing-plaintext-twin warning already lands in the startup log by construction.

**Why.**

1. **Conflict detection for free.** Two templates registering the same name is now a
   `ConfigurationConflictError` at startup, exactly like every other duplicate Zope
   registration — not a silent overwrite nobody notices until the wrong body ships.
2. **`overrides.zcml` works with no bespoke mechanism.** Replacing a registration is the
   stock `includeOverrides` story every consumer already knows from `browser:page` and
   friends.
3. **The msgid domain comes from `i18n_domain`.** `subject`/`preheader` are
   `zope.configuration.fields.MessageID`s (`"[msgid] Default text"` syntax), taking their
   domain from the enclosing ZCML file — consumers no longer hand-build msgids in Python
   with their own `MessageFactory`.
4. **One registration idiom.** Every other piece of `imio.emailkit`'s own wiring
   (adapters, views, the content-rule action, the vocabulary) is ZCML; the templates were
   the one thing that was not, for no reason that survived scrutiny.
5. **No scan/cache/warm-up machinery to keep correct.** The registry has exactly one
   write path (`discovery.register_template`), called by the directive handler. Nothing
   invalidates it because nothing caches ahead of it.

**Build-time discovery.** The buildout recipe and the generated `bin/` scripts cannot
import Plone, so they cannot execute real ZCML the way an instance does. They instead run
a `PermissiveConfigurationMachine` (`src/imio/emailkit/scan.py`) — a
`zope.configuration.config.ConfigurationMachine` subclass whose `factory()` swallows any
directive outside the emailkit namespace (returning a no-op stack item) instead of raising
`ConfigurationError`. Only `imio.emailkit`'s own `meta.zcml` is loaded for real, so
`<emailkit:templates>` executes through the exact same handler, into the exact same
registry, as a live instance start — `<include>`, `zcml:condition` and `overrides.zcml`
all behave with genuine semantics, because they *are* genuine `zope.configuration`. The
one documented divergence: `zcml:condition="have some-feature"` reads false at build time,
since nothing loads the full instance ZCML that would provide the feature. The recipe's
install step only does a cheap filesystem marker scan (`namespaces.imio.be/emailkit`
substring in a package's `.zcml`) — it imports nothing, so a buildout run stays a buildout
run; the generated scripts, which run with the instance eggs on `sys.path`, do the real
scan.

**Fail loud vs. swallow, drawn at the namespace boundary.** A malformed
`<emailkit:template>` (bad attribute, duplicate name) raises exactly as it would at
instance startup, in both the recipe's scan and a real boot — a broken *emailkit*
registration must not go unnoticed just because it was found by a build tool. Everything
outside that namespace (`browser:page`, `plone:*`, `genericsetup:*`, …) is swallowed
without its handler or the classes it names ever being imported: an unknown directive
never resolves its schema or handler, so a foreign directive whose target class raises on
import cannot break the scan. `tests/test_scan.py` pins this with a fixture
`browser:page` whose target class's module raises `ImportError` on import.

**The i18n regression, and its fix.** `i18ndude rebuild-pot` extracts msgids from `.py`
and `.pt` only, never from ZCML, so a `subject`/`preheader` msgid that lives solely in
`configure.zcml` would silently vanish from a locales rebuild. `imio.emailkit` ships
`src/imio/emailkit/msgids.py`, a module whose only job is to call the message factory on
each ZCML msgid so `i18ndude` sees it; `tests/test_msgids.py` fails if the shim and
`configure.zcml` drift apart. This is a real cost versus the dict approach (which needed
no shim) and is documented as such rather than hidden.

**Clean cut.** No deprecation shim, no entry-point fallback. The entry point is deleted
everywhere it existed, including both dummy test add-ons
(`tests/dummies/dummy/{complete,minimal}`), which now carry a `configure.zcml` exactly
like a real consumer. Nothing in this repository, or in any addon it is aware of, depended
on the old mechanism surviving alongside the new one.

---

## 2026-07-29 — REVERSED (my error): the content-rule action registers via plain ZCML, not GenericSetup

**Context.** §8.3 adds a "Send styled email" content-rule action. §8.2 level 3 makes `:base` the opt-out
profile.

**What went wrong, and it was mine.** I briefed the implementer to "register in `profiles/default/`, not
`base`". That instruction was wrong, and it was honoured faithfully. The only GS-native way to satisfy it
is to register the action element as a **local utility** via `componentregistry.xml` — with a
`component=` rather than `factory=` subtlety, because GS's factory branch `_setObject`s the result into
the portal and that needs an OFS item.

**Why it is wrong.**

1. **The mission's own rule:** "if a solution needs a paragraph to justify its cleverness, it's the wrong
   solution." The justification needed several.
2. **The pickled-singleton cost is a silent drift.** A GS registration stores a *copy* of the element, so
   a change to the action's title or description reaches an existing site only when someone re-applies
   the profile. Drift with no symptom is precisely the defect class this project spent five phases
   eliminating.
3. **§8.2's opt-out is about not restyling stock mails, not hiding an action type.** An action type is
   inert until a rule uses it, and the vocabulary has nothing useful in it without registered templates.
   A global registration therefore gives a `:base` site nothing it opted out of.

**Choice.** A plain `plone:ruleAction` directive in ZCML, exactly like every other Plone add-on. The GS
files are deleted and `plone.contentrules` owns the utility object again.

**The gate got stronger, not weaker.** The test now asserts the element is in the *global* registry, that
the site lookup returns **the same object**, and that the site has **no registration of its own** — so a
silent slide back to a local utility fails. A `:base`-only site is asserted to *have* the action type,
with a sibling test that `IEmailkitLayer` is still absent so the two cannot be confused.

**Accepted cost, flagged not hidden.** `IRuleElementDirective.title`/`description` are `TextLine`/`Text`,
not `MessageID`, so the panel entry is **English** — exactly like Plone's own "Send email" and "Notify
user". The strings are extracted into the `.pot` and translated, but inert until `plone.contentrules`
switches those fields. Everything *inside* the action's own forms is translated normally.

**Process lesson.** The implementer surfaced the tradeoff explicitly, priced it ("a two-line change if
you'd rather"), and said it departed from convention — which is the only reason I could catch that my own
brief was the problem. It should also have escalated when the justification started needing paragraphs;
so should I have noticed when writing the brief.

---

## 2026-07-29 — Content-rule decisions the spec leaves open

**1. `cta_label` is passed as a msgid, not a translated string.** `.with_context()` runs **once**, before
§6.2 groups recipients by language. A string translated at that point would send one language's wording
to every recipient — a silent per-language bug. Zope's page-template engine translates the message object
per group instead; verified FR and NL differ and each lands in its own group's HTML.

**Generalises beyond this action:** anything passed through `.with_context()` that is user-facing text
should be a msgid, for the same reason. Recorded in the README.

**2. The render context is a fixed set of five names** — `item`, `title`, `intro`, `cta_label`, `cta_url`
— pinned as `RENDER_CONTEXT_NAMES`. §8.3 says nothing about it, and a rule cannot know what a template
wants. A template needing another name **fails loudly at render** rather than producing a mail with a gap.
A consumer needing more sends from their own code with `Email(...)`.

**3. The owner resolves as a userid, not an address**, so the member adapter can supply `fullname` *and*
`language` and per-language sending works from a rule. An unresolvable owner raises `RecipientError`
rather than mailing everyone else.

**4. Three separate summary msgids rather than one with interpolation**, because `zope.i18n` `str()`s
mapping values and an interpolated label would render as a bare msgid.

**5. No second cache for the vocabulary.** It reads `discovery.available_templates()` directly; a cache
here would survive `invalidate_cache()` and go stale in tests and after a restart.

---

## 2026-07-29 — Both `kit-mode`s materialise `emails/.kit/`, so a consumer's config never changes

**Context.** §5 offers `kit-mode = path | copy` and §4 mentions `emails/.kit/` as "gitignored,
materialized by the recipe if copy mode is used". Read literally, `path` mode would have no `.kit/`,
so a consumer's `maizzle.config.js` would have to import the kit from a *different place* depending on
a buildout setting.

**Choice.** **Both** modes materialise `emails/.kit/`. In `path` mode it holds a two-line re-export of
the real files inside the installed egg, so Maizzle still resolves components straight out of
`site-packages` — genuine zero-copy, which §10.1 settled as viable. In `copy` mode it holds the real
files.

**Why.** The consumer writes one import, once:

```js
import { kitBaseConfig } from './.kit/maizzle.config.base.js'
```

and `kit-mode` becomes a pure deployment switch rather than something that changes committed source.
Under the literal reading, flipping the mode would edit a file the consumer maintains — which is the
opposite of what a buildout option should do, and would mean a consumer's repo differs by deployment.

**Cost.** `path` mode writes two small generated files where a strict reading would write none. They are
gitignored, and no Node runs to produce them: wiring is file copying and two text files.

---

## 2026-07-29 — NEW silent failure: a consumer's `i18n:translate` inherits the kit's `i18n:domain`

**Context.** Caveat A3 established that `Main.vue` must emit `i18n:domain="imio.emailkit"` on `<html>`,
or nothing translates. That fix has a consequence nobody anticipated.

**Finding.** `i18n:domain` **inherits**. A consumer add-on's own `i18n:translate` nested inside the kit
layout therefore resolves against the **`imio.emailkit` catalog**, not the consumer's own. Their msgid
is not found, so it renders its default text — in *every* language, identically,
**indistinguishable from success**. It is caveat A3 again, one level out, and it hits consumers rather
than us.

**The fix authors must apply.** Declare `i18n:domain="<your.package>"` on your own element inside the
template. `tests/dummies/dummy.complete`'s `convocation.vue` demonstrates it, and its golden files show
the contrast deliberately: the kit's footer translates per language while an add-on line without the
declaration does not.

**Why this is the worst one yet.** Every earlier silent failure was ours to hit while building the
package. This one is a **consumer's** failure, in *their* language files, discovered by their client
reading a Dutch mail in English. And there is no visual symptom: the text is real, grammatical and
plausible.

**Follow-up, recommended not done.** A ninth lint rule — `i18n:translate` in a consumer template with
no nearer `i18n:domain` — is the natural guard, and it is why the lint exists. Not added yet because
distinguishing "author forgot" from "author is deliberately reusing a kit msgid" needs care, and a false
positive on a legitimate case is how a gate gets switched off (the same reasoning that narrowed rule 2).
`SKILL.md` documents the hazard meanwhile.

---

## 2026-07-29 — `MANIFEST.in`'s `graft` follows symlinks into `node_modules`

**Context.** The dummy consumer add-ons need a `node_modules` symlink at build time, because without a
`node_modules` **ancestor** Tailwind cannot resolve the `@import "@maizzle/tailwindcss"` the shell
emits — and Maizzle then **ships the uncompiled stylesheet with exit 0** while printing "Built 1
template" (measured: 5.3 KB → 3.5 KB, zero inline styles). That is the same class of silent failure as
everything else here, and it was briefly committed as broken output.

**Finding.** `MANIFEST.in` does `graft tests`, and setuptools' file walk **follows symlinks**. A link
left in the tree therefore puts roughly **20,000 `node_modules` files into the sdist**, silently — and
invisibly to `git status`, because the link is gitignored.

**Choice.** The dummies' rebuild helper creates the symlink for the build and removes it afterwards.
Verified: the built sdist contains **0** `node_modules` entries and all 57 dummy files.

**Why recorded.** Two independent silent failures meeting in one place, and the packaging half would only
have been noticed by whoever downloaded a 200 MB sdist.

---

## 2026-07-29 — The golden base class ships as `imio.emailkit.golden`, a separate module

**Context.** §7 promises consumers "a provided test base class". It lived in `tests/`, which does not
ship in the egg, so §7 was unmet in practice.

**Choice.** A new module, `src/imio/emailkit/golden.py` — **not** folded into
`imio.emailkit.testing`.

**Why separate.** `golden.py` imports `pytest` at module level, and `testing.py` holds the Plone layers
that consumers on `zope.testrunner` import. Folding them together would make the layers unimportable for
anyone not using pytest. A test asserts `testing.py` never imports pytest, so the two cannot merge by
accident.

**Verified shipped.** A built wheel contains `imio/emailkit/golden.py`. No `package-data` entry was
needed — it is a `.py` module inside a found package — and a test records that, with the reason it would
have been needed had the harness been data instead of code.

**Dogfooding preserved.** `tests/golden_harness.py` is now a four-attribute subclass of the shipped
class, with a test asserting it overrides no test method. This package therefore runs exactly what it
hands consumers, which is the property §7 is really asking for.

**One `S101` exemption** in `pyproject.toml` for that file, with a comment: it *is* test code, and
`assert actual == expected, <diff>` is what pytest reports usefully.

---

## 2026-07-29 — `imio.recipe.emailkit` lives in this repository, as a sibling directory

**Context.** §2's artifact table lists two distributions — `imio.emailkit` and
`imio.recipe.emailkit` — without saying where the second one lives.

**Options.** (A) a sibling directory in this repo (`recipe/`), released as its own distribution;
(B) its own repository.

**Choice.** **A.**

**Why.** One checkout, one CI run, and — the deciding reason — the recipe's tests can exercise the
**real kit next door** instead of a pinned release of it. Every Phase 0–3 finding says this pipeline
fails silently, so a recipe tested against a stale pinned kit is a recipe that passes while the thing
it wires up has changed. Splitting later is cheap and has an explicit trigger: release cadences
diverging. That is the same argument §3 makes for keeping the kit in the egg rather than on npm, applied
one level up.

**Consequence.** Two `pyproject.toml` files in one repo, and CI must build and test both. The
`imio.emailkit` sdist must not accidentally ship `recipe/`.

---

## 2026-07-29 — A legacy body's own `<style>` block is dropped by most clients

**Context.** `render_shell` injects arbitrary legacy HTML, and some legacy notification bodies carry a
`<style>` block.

**Finding.** The injected block lands inside the document **`<body>`**, which is invalid placement, and
Gmail and Outlook.com strip it. The shell does **not** hoist it into `<head>`, because the shell wraps
and does not rewrite (plan §5). Inline `style="…"` attributes in the body survive untouched.

**Choice.** Documented as a migration caveat in the README rather than fixed by hoisting. Hoisting would
mean the shell rewriting a consumer's markup, and it would silently change cascade order against the
shell's own inlined styles.

**Why it needs saying out loud.** It works perfectly in a browser preview, so a consumer cannot discover
it before real clients do. It is a candidate `check-emails` warning in Phase 4.

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
`imio/emailkit/kit/`, §4 registration namespace `http://namespaces.imio.be/emailkit`, §5 recipe
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

## 2026-08-03 — RESOLVED (§8.1 amendment): the username reminder needs a *view* override, not jbot

**Context.** §8.1 said the restyled Plone default mails ship "as `z3c.jbot` overrides", and named two
(password reset, registration). The username reminder from the login-help form was missing, and it cannot
be added the same way.

**Finding.** Stock Plone has no template for that mail. It is `SEND_USERNAME_TEMPLATE`, a module-level
i18n string in `Products/CMFPlone/browser/login/login_help.py`, declared `text/plain`, interpolated with
`str.format()` and handed straight to `MailHost` by `RequestUsername.send_username()`. `z3c.jbot` keys on
a resolved filename; there is no file, so there is nothing to displace.

**Decision.** Override the `login-help` browser page on `IEmailkitLayer` with a subclass whose subform is
our own `RequestUsername`, delegating to `Email(...)`. This keeps §8.2's opt-out intact (a `:base` site
gets stock Plone's view and stock Plone's mail) and keeps the stock mail action untouched.

**Consequence, and it is a gain.** Because the view is ours, the template gets the flat dialect back: it
renders through §6.1 `render()`, so it is registered for discovery, previewable and golden-tested. It is
the one restyled default mail for which §8's "authored, compiled, discovered, tested and shipped exactly
like consumer templates" is true of *every* verb. `tests/support.py` therefore lists it in
`RENDERABLE_TEMPLATES` and deliberately **not** in `DEFAULT_MAIL_TEMPLATES`.

**The one cost.** `LoginHelpForm.update` is *forked*, not extended. Stock instantiates `RequestUsername`
by direct class reference and the mail is sent inside the subform's own `update()`, so `super().update()`
would already have sent the plaintext mail — there is no seam. Temporarily rebinding the module global
was rejected: Zope's publisher is threaded and two concurrent requests would race. The fork is twelve
lines and is guarded by `test_stock_update_is_what_we_forked_from`, which pins the upstream source so a
Plone upgrade fails loudly instead of silently un-styling the mail.

**Reachability.** Plone only renders the subform when `use_email_as_login` is off. On email-as-login sites
this mail is never sent — inert, not broken. Both registry states are covered by tests.

## 2026-08-03 — Upstream bug: the origin IP in the password-reset mail renders empty

Our `mail_password` template carried stock Plone's expression verbatim:

```
tal:define="host request/HTTP_X_FORWARDED_FOR|request/REMOTE_ADDR"
```

It renders **empty** whenever no `X-Forwarded-For` header is present, and stock
`Products/CMFPlone/browser/login/templates/mail_password_template.pt` has the same defect. Two behaviours
combine:

- `HTTPRequest.get()` special-cases CGI and `HTTP_` keys and returns `''` for a missing one **instead of
  raising** (`ZPublisher/HTTPRequest.py`);
- `ZopePathExpr._eval` falls through a `|` chain only on a traversal **exception**, never on a falsy value
  (`Products/PageTemplates/Expressions.py`).

So the first subexpression succeeds with `''` and the `REMOTE_ADDR` fallback is dead code.

**Fix.** `request/getClientAddr`, Zope's supported accessor, in both login-help mails.

**Deployment requirement.** `getClientAddr` honours `X-Forwarded-For` only for proxies declared as
`trusted-proxy` in `zope.conf`; `HTTPRequest.trusted_proxies` defaults to empty, so behind an
undeclared nginx it reports `127.0.0.1`. Documented in the README rather than worked around. Reading the
raw header instead needs no configuration and was **rejected**: the header is client-settable, so the
sender could choose which IP the mail names.

Pinned by `TestClientAddressSemantics` in `tests/test_get_username.py`, which asserts the Zope-level
behaviour directly so a future Zope change surfaces there rather than as an empty line in a mail.

## 2026-08-03 — `spike/` removed

The Phase 0 spike has been deleted, as the entries above anticipated ("throwaway
evidence, slated for deletion"): the kit, the build pipeline and the golden files
supersede every question it existed to answer.

Earlier entries still cite paths inside it (`spike/build/theme-token-literal.pt`,
`spike/maizzle/strip-comments.js`). Those citations are left as written — they are
dated records of how a decision was reached, not live pointers. The shipped
equivalent of the second one is `src/imio/emailkit/kit/strip-comments.js`.
