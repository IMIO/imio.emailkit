# Two dummy consumer add-ons

Discovery needs tests with two dummy add-ons that also serve as living
documentation. This is them. They are the smallest complete answer to *"how do
I ship an email template from my add-on?"*, and they are executed by CI, so they
cannot rot into a stale README.

| | `dummy.minimal` | `dummy.complete` |
|---|---|---|
| templates | 1 | 2 |
| `directory` attribute | omitted (defaults to `templates`) | stated |
| `preheader` msgid | none | on both templates |
| `.txt.pt` twin | none — falls back to automatic plaintext extraction | hand-authored, both templates |
| golden languages | `fr` | `fr` + `en` |
| kit components | `KitMain` only | `KitMain`, `KitPanel`, `KitButton`, `KitDataTable` |
| runtime constructs | `${...}` only | `${...}`, `tal:condition`, `tal:repeat`, `${python: format_date(...)}`, `i18n:translate` |

Read `dummy.minimal` first: it is the floor, and it is short. Then read
`dummy.complete/emails/src/templates/convocation.vue`, which is the busiest
template in the repository on purpose.

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

where `configure.zcml` is the whole registration:

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

Nothing in `__init__.py`, and no `MessageFactory`: the msgid domain of `subject` and
`preheader` is the file's `i18n_domain`, and the lookup namespace is the package the
file belongs to, so neither can disagree with reality. A real add-on's ZCML is
executed by Zope's autoinclude at startup, which is also where the "missing
plaintext twin" warnings land.

Two `MANIFEST.in` lines are needed as well, because the compiled output must ship and
the Maizzle project must not:

```
recursive-include src/dummy/complete/templates *.pt
prune src/dummy/complete/emails
```

## The same template basename in three distributions

`notification` is registered by `dummy.minimal`, by `dummy.complete` **and** by
`imio.emailkit` itself. There is no clash, because every lookup is namespaced by the
registering package:

```python
render("dummy.minimal:notification", context=…)     # three different files,
render("dummy.complete:notification", context=…)    # three different templates
render("imio.emailkit:notification", context=…)
render("notification", context=…)                   # TemplateNotFound, on purpose
```

The bare name resolving to nothing is deliberate: accepting it would make the answer
depend on the order the three packages' ZCML happens to execute in.
`tests/test_discovery_dummies.py` asserts all four of those lines.

## Registering through ZCML, without being installed

The registration itself is not special-cased for the tests: each dummy carries the
`configure.zcml` shown above, exactly as a real consumer does. What a real consumer
gets for free is *execution* — it is pip-installed, and Zope's autoinclude runs its
ZCML at startup.

These two live inside another package's test tree, so `tests/dummyaddons.py` runs
their ZCML on purpose, through `imio.emailkit.scan.scan_package()` — the same
permissive-machine scan the build tooling uses on a real consumer, over the same
directive handler and into the same registry as an instance start. Nothing is
monkeypatched and no private API is used.

It is scoped to a fixture, so the rest of the suite sees only `imio.emailkit`'s own
templates; `tests/test_dummy_isolation.py` is the guard on that. Teardown removes the
two add-ons' registrations rather than restoring a whole-registry snapshot, because
the Plone test layer loads the *host's* ZCML lazily and can do so from inside such a
block — see `installed()` for the measurement.

A real add-on needs none of this. It is pip-installed, and its ZCML is simply run.

## Running their CI contract

The same CI contract applies to these two as to any consumer:

```bash
# gate 1 -- build output is not stale, and the authoring lint (needs Node)
pytest tests/test_consumer_ci.py -q

# gate 2 -- runtime rendering is intact
pytest tests/dummies -q

# the authoring lint on its own
python -m imio.emailkit.lint tests/dummies

# regenerate the snapshots, deliberately, after an intended template change
EMAILKIT_UPDATE_GOLDEN=1 pytest tests/dummies -q -rs
```

Note that `make update-golden` only regenerates *this* package's snapshots
(`tests/test_golden.py`); the dummies' are regenerated with the command above.

`tests/test_consumer_ci.py` also runs both gates **backwards** — it tampers with a
compiled template and with a snapshot and asserts each gate goes red, naming the
file. A gate that has only ever been seen green is not known to be a gate.

Two differences from a real add-on, both artefacts of living inside
`imio.emailkit`'s own test tree:

- the test modules are called `test_minimal_emails.py` / `test_complete_emails.py`
  rather than `test_emails.py`, because pytest requires unique test-module
  basenames within one rootdir;
- `emails/` has no `package.json` and no `node_modules`. The staleness test
  symlinks the checkout's Maizzle install in for the duration of the build and
  removes it afterwards — `MANIFEST.in` does `graft tests` and setuptools' file walk
  follows symlinks, so a link left lying around puts ~20 000 files from
  `node_modules` into the sdist, and it is gitignored so nothing would tell you.
  The symlink itself is not optional: without a `node_modules` ancestor, Tailwind
  cannot resolve the `@import "@maizzle/tailwindcss"` the shell emits, and **Maizzle
  ships the uncompiled stylesheet with exit code 0** (measured: 5.3 KB of output
  with inlined styles becomes 3.5 KB with none, and the build says
  "Built 1 template").

Nothing else here is a shortcut: the `.vue` sources are compiled by the real Maizzle
build against the real kit, and the `.pt` files in `templates/` are that build's
committed output.
