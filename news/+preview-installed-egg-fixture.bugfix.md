Stop `bin/preview-emails` reporting FAILED for a fixture an installed egg cannot
ship. The script discovers every package that registers templates, `imio.emailkit`
included; taken from PyPI rather than as a checkout, its sdist has pruned `tests/`
(SPEC §4), so the §7 fixture is not there and no consumer buildout could put it
there. All four stock mail templates were reported as failures and the script
exited non-zero on a buildout working exactly as intended. A missing fixture in a
checkout is still the omission §7 wants caught; only a package with no source tree
at all is now reported as a plain fact, which is the judgement
`@@emailkit-preview` already makes (§6.3). The template stays listed either way,
because its `.pt` part needs no fixture.
