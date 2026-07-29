# Two dummy consumer add-ons

SPEC §7 asks for "discovery tests with two dummy addons (**also serving as living
documentation**)". This is them. They are the smallest complete answer to *"how do
I ship an email template from my add-on?"*, and they are executed by CI, so they
cannot rot into a stale README.

| | `dummy.minimal` | `dummy.complete` |
|---|---|---|
| templates | 1 | 2 |
| `directory` key | omitted (defaults to `templates`) | stated |
| `preheader` msgid | none | on both templates |
| `.txt.pt` twin | none — uses §4's fallback | hand-authored, both templates |
| golden languages | `fr` | `fr` + `en` |
| kit components | `KitMain` only | `KitMain`, `KitPanel`, `KitButton`, `KitDataTable` |
| runtime constructs | `${...}` only | `${...}`, `tal:condition`, `tal:repeat`, `${python: format_date(...)}`, `i18n:translate` |

Read `dummy.minimal` first: it is the floor, and it is short. Then read
`dummy.complete/emails/src/templates/convocation.vue`, which is the busiest
template in the repository on purpose.

## The seven files an add-on needs

```
dummy/complete/
├── __init__.py                       # the `emailkit` registration dict (§4)
├── emails/                           # Maizzle project; dev only, pruned from the sdist
│   ├── maizzle.config.js             #   two settings long, whatever the add-on's size
│   ├── src/templates/*.vue           #   what you author
│   └── twins/*.txt.pt                #   hand-authored plaintext, copied in after the build
├── templates/                        # ✅ committed build output; what production renders
│   ├── convocation.pt
│   └── convocation.txt.pt
└── tests/
    ├── test_complete_emails.py       # four lines; subclasses the shipped base class
    ├── fixtures/convocation.py       # a CONTEXT dict (§7)
    └── golden/convocation.fr.html    # snapshots (§7)
```

plus one entry point in `pyproject.toml`:

```toml
[project.entry-points."imio.emailkit.templates"]
"dummy.complete" = "dummy.complete:emailkit"
```

and two `MANIFEST.in` lines, because the compiled output must ship and the Maizzle
project must not:

```
recursive-include src/dummy/complete/templates *.pt
prune src/dummy/complete/emails
```

## The same template basename in three distributions

`notification` is registered by `dummy.minimal`, by `dummy.complete` **and** by
`imio.emailkit` itself. There is no clash, because §4 namespaces every lookup by
the entry-point name:

```python
render("dummy.minimal:notification", context=…)     # three different files,
render("dummy.complete:notification", context=…)    # three different templates
render("imio.emailkit:notification", context=…)
render("notification", context=…)                   # TemplateNotFound, on purpose
```

The bare name resolving to nothing is deliberate: accepting it would make the
answer depend on entry-point scan order. `tests/test_discovery_dummies.py` asserts
all four of those lines.

## How they are discovered without being installed

`imio.emailkit.discovery` reads `importlib.metadata.entry_points(group=…)`, which
enumerates `*.dist-info` directories found on `sys.path`. So the two committed
`*-1.0.dist-info/` directories here, plus `tests/dummies/` on `sys.path`, make
these two "installed" as far as the entry-point machinery is concerned — and
`entry_points.txt` is byte-for-byte what `pip` writes from the `pyproject.toml`
block above.

Nothing is monkeypatched and no private API is used: the code under test runs the
same `entry_points()` call production runs, over real metadata. The wiring is in
`tests/dummyaddons.py` and is scoped to a fixture, so the rest of the suite sees
only `imio.emailkit`'s own templates.

A real add-on needs none of this. It is pip-installed, and its entry point is
simply there.

## Running their CI contract

§7's contract, for these two as for any consumer:

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
