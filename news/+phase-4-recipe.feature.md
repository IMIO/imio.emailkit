Add `imio.recipe.emailkit`, generating `bin/compile-emails`, `bin/check-emails`
and `bin/preview-emails` from a buildout part, with `kit-mode = path | copy` and
`compile-on-install` off by default so a plain buildout run invokes no Node.
SPEC §5.
