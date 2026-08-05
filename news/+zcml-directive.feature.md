Templates from consumer add-ons are now registered with the
`<emailkit:templates>` ZCML directive instead of the
`imio.emailkit.templates` entry point + dict. Duplicate names become
configuration conflicts, `overrides.zcml` works, and the subject/preheader
msgid domain comes from the ZCML file's `i18n_domain`. The buildout recipe
and the `bin/` scripts discover consumers by executing their ZCML through a
permissive configuration machine — no entry point, no hand-rolled parsing.
