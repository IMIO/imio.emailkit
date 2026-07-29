# Phase 0 spike — throwaway

This directory is **evidence, not code.** Nothing here is imported by the package, and none
of it ships in an sdist. It exists to back the verdicts in
[`docs/plans/phase-0-report.md`](../docs/plans/phase-0-report.md), and it is deleted in a
single `chore:` commit once the real kit supersedes it in Phase 1.

Read the report first. This README only says how to re-run it.

## Layout

```
spike/
├── kit-outside/            two kit component stubs, deliberately OUTSIDE the
│   ├── Button.vue          Maizzle project root -- that is the whole point of
│   └── Panel.vue           assumption (c), `kit-mode = path`
├── maizzle/                the Maizzle 6 project
│   ├── maizzle.config.js           purge ON  -> dist/
│   ├── maizzle.nopurge.config.js   purge OFF -> dist-nopurge/  (control build)
│   ├── strip-comments.js           afterTransform hook; see caveat A2
│   └── emails/
│       ├── spike.vue               the torture-test template
│       ├── mail_password.vue       compiled into the jbot override for (d)
│       └── theme-token-literal.vue minimal proof that SPEC §3's literal
│                                   theme-token form breaks CSS inlining
├── build/                  COMMITTED EVIDENCE (compiled output + the diff)
├── rendered/               COMMITTED EVIDENCE (Chameleon-rendered HTML)
├── fixture.py              context data for the render
├── render.py               renders a compiled .pt and asserts 15 properties
└── plone/                  throwaway addon + pytest for assumption (d)
```

`.venv/` and `maizzle/node_modules/` are gitignored.

## Re-running

```bash
# Stage 1 -- build (Node). Both configs, so the purge diff can be regenerated.
cd maizzle
npm ci
npx maizzle build                                   # -> dist/*.pt
npx maizzle build -c maizzle.nopurge.config.js      # -> dist-nopurge/*.pt
cd ..

cp maizzle/dist/spike.pt build/spike.pt
cp maizzle/dist-nopurge/spike.pt build/spike.nopurge.pt
diff -u build/spike.nopurge.pt build/spike.pt > build/purge.diff

# Stage 2 -- render (Python only, no Node).
.venv/bin/python render.py build/spike.pt
```

Expected: `ALL CHECKS PASSED`, 15 checks.

The venv is built with `uv` against the Plone 6.2.1 constraints file:

```bash
uv venv --python 3.12 .venv
curl -sSfL -o /tmp/c.txt https://dist.plone.org/release/6.2.1/constraints.txt
VIRTUAL_ENV=.venv uv pip install -c /tmp/c.txt \
    Products.CMFPlone plone.app.testing plone.api z3c.jbot pytest pytest-plone
```

## Two things that will bite you if you edit the template

Both cost real debugging time here, and both produce a **successful build** with plausible
output — see the report for the full list.

1. **Never put a Chameleon placeholder in a `style` or `class` attribute.** In `style` it eats
   the closing brace *and silently disables CSS inlining for the entire document*. In `class`
   it gets mangled by `css.safe` (`$`→`-`, braces stripped). Use
   `tal:attributes="style string:..."`.
2. **Never write the raw-escape component's name in angle brackets inside a comment.** Its
   extraction is a naive global regex over the file source that also matches inside comments,
   so the mention swallows the real block and it vanishes from the output.
