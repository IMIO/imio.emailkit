Add `render_shell(subject, body_html, language=None)`, a `render()` sibling that
wraps an existing HTML mail body in the kit shell with no template redesign.
`${...}` inside the injected body is emitted literally, never evaluated. SPEC §9
phase 3.
