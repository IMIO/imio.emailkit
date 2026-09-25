# Hand-authored plaintext twins — `dummy.complete`

`<name>.txt.pt` is the plaintext half of a template: **source**, copied into
`../templates/` after Maizzle runs, for two reasons:

1. `maizzle build` **empties its output directory**, silently, with no way
   to stop it: a twin left in `templates/` is deleted by the next build.
2. Twins are hand-authored, never generated: Maizzle's plaintext output
   destroys every `tal:`/`i18n:` construct, shipping wrong content in the
   wrong language.

## Why bother, when `render()` has a fallback

Without a twin, the fallback extraction derives text from the HTML and
**drops every link** — the URL lives in an `<a href>` it discards.
`tests/golden/convocation.fr.txt` (this twin) keeps the CTA label and its
URL; `../../../minimal/tests/golden/notification.fr.txt` (no twin) does not.
Any template with a call to action needs a twin.

## The two things that catch people

- Keep the placeholders: a twin is a **template**, not a rendering.
  `${...}`, `tal:repeat` and `tal:content` all run at send time.
- Use `<tal:body>` / `tal:omit-tag=""` to emit text without tags. A stray
  real tag in a `text/plain` part reaches the reader as literal markup.
