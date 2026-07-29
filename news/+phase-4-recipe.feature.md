`imio.recipe.emailkit`, the buildout recipe of SPEC §5, ships as a second
distribution in this repository (`recipe/`). A part generates `bin/compile-emails`,
`bin/check-emails` and `bin/preview-emails` from the `imio.emailkit.templates` entry
points in its `eggs`, and resolves the design kit out of the `imio.emailkit` egg.
`compile-on-install` defaults to false, so a plain buildout run invokes no Node,
touches no `emails/` directory and imports no consumer code. `kit-mode = path`
(zero-copy, the default) and `kit-mode = copy` both produce byte-identical output.
`test-buildout.cfg` and `make buildout-test` run §9 phase 4's acceptance test end to
end, buildout included, with `node` removed from `PATH`.
