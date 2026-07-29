/**
 * Strip authoring comments from compiled output, keeping Outlook conditional
 * comments -- those are load-bearing markup, not commentary.
 *
 * This is required, not cosmetic. Chameleon refuses to parse `--` inside an
 * HTML comment ("The string '--' is not allowed in a comment"), so one
 * em-dash-style comment in a `.vue` source makes the compiled `.pt`
 * unparseable at runtime -- and the Maizzle build reports success, so the
 * failure only shows up when a real mail is sent. Maizzle 6 has no
 * comment-removal option of its own; `css.purge` drops only some comments.
 *
 * Authoring commentary has no business shipping in a transactional email
 * anyway, so stripping is the right default regardless.
 *
 * MSO conditionals are recognised by `[if` / `[endif]` in the comment body,
 * which also covers the downlevel-revealed `<!--[if !mso]><!-->` form.
 */
export function stripAuthorComments(html) {
  return html.replace(/<!--([\s\S]*?)-->/g, (match, inner) =>
    /\[if|\[endif\]/.test(inner) ? match : ''
  )
}
