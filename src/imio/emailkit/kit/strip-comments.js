/**
 * Strip authoring comments from compiled output. Keep Outlook conditional
 * comments (recognised by `[if` / `[endif]` in the body).
 *
 * Required: Chameleon refuses to parse `--` inside an HTML comment, so one
 * em-dash-style comment in a `.vue` source makes the compiled `.pt`
 * unparseable at runtime while the Maizzle build still reports success.
 */
export function stripAuthorComments(html) {
  return html.replace(/<!--([\s\S]*?)-->/g, (match, inner) =>
    /\[if|\[endif\]/.test(inner) ? match : ''
  )
}

/**
 * Put every Outlook conditional comment back on one line.
 *
 * Chameleon re-serialises the markup inside a conditional comment with
 * its own whitespace rules. If the HTML formatter has spread it over
 * several lines, this breaks the `[if mso]`/`[endif]` markers apart and
 * Outlook silently drops the MSO fallback.
 */
export function flattenConditionalComments(html) {
  return html.replace(/<!--([\s\S]*?)-->/g, (match, inner) =>
    /\[if|\[endif\]/.test(inner) ? match.replace(/\s*\n\s*/g, ' ') : match
  )
}

/**
 * Pull punctuation back onto the line of the tag it belongs to.
 *
 * The HTML formatter can break the line between an inline element and its
 * trailing punctuation. HTML collapses that newline to a space, so a
 * translated sentence gets a stray space before the punctuation, which
 * then lands in the `.pot` file and shows in every language.
 *
 * Narrow on purpose: only removes a newline right after `>` and before
 * leading punctuation, so it cannot join two lines of prose or CSS.
 */
export function unbreakPunctuation(html) {
  return html.replace(/>\n[ \t]*(?=[.,;:!?)\]»…])/g, '>')
}
