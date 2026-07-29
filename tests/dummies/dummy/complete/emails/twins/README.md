# Hand-authored plaintext twins — `dummy.complete`

`<name>.txt.pt` is the plaintext half of a template (SPEC §4). It is **source**,
lives here, and is copied into `../templates/` after Maizzle has run — exactly what
`imio.emailkit` itself does, for the same two reasons:

1. `maizzle build` **empties its output directory**, silently, with no option to
   stop it. A twin kept in `templates/` is deleted by the next build and nothing
   says so.
2. Twins are hand-authored, never generated. Maizzle's own plaintext output
   destroys every `tal:`/`i18n:` construct — `tal:repeat` vanishes,
   `i18n:translate` freezes at the English default — so a generated twin would
   ship a plausible-looking body with the wrong content in the wrong language.

## Why bother, when `render()` has a fallback

Without a twin, §4's naive text extraction runs, logs a deprecation, and produces
text derived from the HTML — which **drops every link**, because the URL lives in
an `<a href>` the extraction throws away. Compare the two committed snapshots:

- `tests/golden/convocation.fr.txt` (this twin) ends with the CTA label *and* its
  URL, and lists the agenda rows as `* Point : Decision`.
- `../../../minimal/tests/golden/notification.fr.txt` (no twin) is what the
  fallback gives you.

A transactional mail whose plaintext part has no link is a mail that is unusable
for anybody reading in plaintext, so any template with a call to action wants a
twin.

## The two things that catch people

- Keep the placeholders. A twin is a **template**, not a rendering: `${...}`,
  `tal:repeat` and `tal:content` all work and all run at send time.
- `<tal:body>` and `tal:omit-tag=""` are how you emit text without emitting tags.
  A stray real tag in a `text/plain` part reaches the reader as literal markup.
