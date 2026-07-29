# Hand-authored plaintext twins

`<name>.txt.pt` files live here as **source**, and `make build-emails` copies them
into `src/imio/emailkit/templates/` after Maizzle has run.

Two reasons they cannot live in `templates/` directly:

1. `maizzle build` **empties its output directory**, silently. It deleted a
   committed twin, and Maizzle 6.0.7 exposes no `output.clean` / `emptyOutDir`
   option to stop it. Keeping the only copy there means losing it on the next
   build, with no error.
2. They are hand-authored, not generated. Maizzle's own plaintext output destroys
   every `tal:` and `i18n:` construct — conditionals vanish, headers come out
   empty, `i18n:translate` freezes at the English default — so generating a twin
   would ship a plausible-looking body with the wrong content in the wrong
   language.

SPEC §4 wants the twin resolved as `<directory>/<name>.txt.pt`, which is what the
copy produces in the installed package.
