# Hand-authored plaintext twins

`<name>.txt.pt` files live here as **source**. `make build-emails` copies
them into `src/imio/emailkit/templates/`.

They cannot live in `templates/` directly, for two reasons:

1. `maizzle build` **empties its output directory**, silently, with no way
   to stop it. A twin left there is lost, with no error.
2. Twins are hand-authored, not generated: Maizzle's plaintext output
   destroys every `tal:`/`i18n:` construct, so a generated twin ships wrong
   content in the wrong language.

The twin resolves as `<directory>/<name>.txt.pt` in the installed package.
