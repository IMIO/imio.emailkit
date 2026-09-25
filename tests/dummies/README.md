# Two dummy consumer add-ons

These two dummy add-ons provide discovery tests and double as living
documentation — the smallest answer to *"how do I ship an email template?"*.
CI keeps them current.

| | `dummy.minimal` | `dummy.complete` |
|---|---|---|
| templates | 1 | 2 |
| `directory` attribute | omitted (default `templates`) | stated |
| `preheader` msgid | none | on both templates |
| `.txt.pt` twin | none (auto plaintext fallback) | hand-authored, both templates |
| golden languages | `fr` | `fr` + `en` |
| kit components | `KitMain` only | `KitMain`, `KitPanel`, `KitButton`, `KitDataTable` |
| runtime constructs | `${...}` only | `${...}`, `tal:condition`, `tal:repeat`, `${python: format_date(...)}`, `i18n:translate` |

Read `dummy.minimal` first, then
`dummy.complete/emails/src/templates/convocation.vue`, the busiest template here.

## The seven files an add-on needs

```
dummy/complete/
├── configure.zcml                    # the registration: one <emailkit:templates> block
├── emails/                           # Maizzle project; dev only, pruned from the sdist
│   ├── maizzle.config.js             #   two settings long, whatever the add-on's size
│   ├── src/templates/*.vue           #   what you author
│   └── twins/*.txt.pt                #   hand-authored plaintext, copied in after the build
├── templates/                        # ✅ committed build output; what production renders
│   ├── convocation.pt
│   └── convocation.txt.pt
└── tests/
    ├── test_complete_emails.py       # four lines; subclasses the shipped base class
    ├── fixtures/convocation.py       # a CONTEXT dict
    └── golden/convocation.fr.html    # snapshots
```

`configure.zcml` is the whole registration:

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="dummy.complete"
    >

  <include package="imio.emailkit" file="meta.zcml" />

  <emailkit:templates directory="templates">
    <emailkit:template
        name="convocation"
        subject="[email_subject_convocation] Convocation to the municipal council"
        preheader="[email_preheader_convocation] Agenda and documents ..."
        />
  </emailkit:templates>

</configure>
```

No `__init__.py`, no `MessageFactory`: the msgid domain is the file's
`i18n_domain`, the lookup namespace its own package. Zope's autoinclude runs
a real add-on's ZCML at startup, where "missing plaintext twin" warnings
appear too.

Two `MANIFEST.in` lines: ship the compiled output, prune the Maizzle
project.

```
recursive-include src/dummy/complete/templates *.pt
prune src/dummy/complete/emails
```

## The same template basename in three distributions

`notification` is registered by `dummy.minimal`, `dummy.complete`, **and**
`imio.emailkit`: no clash, since every lookup is namespaced by package.

```python
render("dummy.minimal:notification", context=…)     # three different files,
render("dummy.complete:notification", context=…)    # three different templates
render("imio.emailkit:notification", context=…)
render("notification", context=…)                   # TemplateNotFound, on purpose
```

The bare name resolves to nothing by design: the answer never depends on
ZCML load order. `tests/test_discovery_dummies.py` asserts all four lines.

## Registering through ZCML, without being installed

Each dummy carries the same `configure.zcml` a real consumer would use; a
real add-on gets *execution* for free via pip install and Zope's
autoinclude. Living in another package's test tree, these two instead run
their ZCML through `tests/dummyaddons.py`, via
`imio.emailkit.scan.scan_package()`, scoped to a fixture so the rest of the
suite sees only `imio.emailkit`'s templates
(`tests/test_dummy_isolation.py` guards this). Teardown removes the two
registrations directly — see `installed()`.

A real add-on needs none of this.

## Running their CI contract

The same CI checks apply here, like any consumer:

```bash
# the staleness check, plus the authoring lint (needs Node)
pytest tests/test_consumer_ci.py -q

# runtime rendering stays intact
pytest tests/dummies -q

# the authoring lint on its own
python -m imio.emailkit.lint tests/dummies

# regenerate the snapshots, deliberately, after an intended template change
EMAILKIT_UPDATE_GOLDEN=1 pytest tests/dummies -q -rs
```

`make update-golden` regenerates only *this* package's snapshots
(`tests/test_golden.py`); use the command above for the dummies'.

`tests/test_consumer_ci.py` also runs both checks **backwards**: it tampers
with a compiled template and a snapshot, asserting each check fails and
names the file.

Two differences from a real add-on come from living in `imio.emailkit`'s
test tree:

- Test modules are named `test_minimal_emails.py` / `test_complete_emails.py`,
  not `test_emails.py`: pytest requires unique basenames per rootdir.
- `emails/` has no `package.json` or `node_modules`. The staleness test
  symlinks in the checkout's Maizzle install for the build, then removes it.
  Never leave that symlink: `MANIFEST.in`'s `graft tests` plus setuptools'
  symlink-following puts ~20 000 `node_modules` files into the sdist,
  silently (it is gitignored). The symlink is also required: without a
  `node_modules` ancestor, Tailwind cannot resolve
  `@import "@maizzle/tailwindcss"`, and **Maizzle ships the uncompiled
  stylesheet with exit code 0** (output shrinks from 5.3 KB to 3.5 KB; the
  build still reports "Built 1 template").

The real Maizzle build compiles `.vue` sources against the real kit;
`templates/*.pt` is its committed output.
