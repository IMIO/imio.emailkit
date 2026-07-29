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

/**
 * Put every Outlook conditional comment back on one line.
 *
 * Also required, also for a runtime reason the build cannot see. Chameleon does
 * not treat a conditional comment as opaque text -- it parses the markup inside
 * it and re-serialises it with its own whitespace rules. When the compiled `.pt`
 * has the comment spread over several lines (which the HTML formatter does by
 * default), Chameleon emits
 *
 *     <!--[if mso
 *       ]><style>…</style><!
 *     [endif]-->
 *
 * and Outlook no longer recognises the condition, so every MSO fallback in the
 * mail is silently dropped. Single-line conditionals come out byte-identical.
 *
 * Run after the formatter: `afterTransform` is the first hook that sees
 * prettified HTML, which is exactly why both of these live there.
 *
 * The regex matches one comment node at a time, so the downlevel-revealed pair
 * (`<!--[if !mso]><!-->` … `<!--<![endif]-->`) is handled as two short comments
 * and the real markup between them is never touched.
 */
export function flattenConditionalComments(html) {
  return html.replace(/<!--([\s\S]*?)-->/g, (match, inner) =>
    /\[if|\[endif\]/.test(inner) ? match.replace(/\s*\n\s*/g, ' ') : match
  )
}

/**
 * Pull punctuation back onto the line of the tag it belongs to.
 *
 * The HTML formatter runs with `htmlWhitespaceSensitivity: 'ignore'`, so it is
 * free to break the line between an inline element and the punctuation that
 * follows it. HTML collapses that newline to a space, which turns
 *
 *     …of the account <span i18n:name="userid">x</span>. Your previous…
 *
 * into "of the account x . Your previous" -- and because that text is also the
 * `i18n:translate` default, the stray space is what lands in the `.pot` and what
 * every untranslated language shows. Every mail here is prose with inline
 * `i18n:name` spans in it, so it would show up everywhere.
 *
 * Deliberately narrow: the newline is removed only when the character before it
 * is `>` (the end of a tag) and the first character after the indentation is
 * punctuation. That cannot join two lines of prose, two CSS declarations, or two
 * clauses of a multi-line `tal:define`.
 *
 * The alternative -- `htmlWhitespaceSensitivity: 'css'` -- was measured and is
 * worse: the formatter then reflows Outlook conditional comments and splits
 * `<![endif]-->` into `<!` + `[endif]-->`, which no repair can safely undo.
 */
export function unbreakPunctuation(html) {
  return html.replace(/>\n[ \t]*(?=[.,;:!?)\]»…])/g, '>')
}
