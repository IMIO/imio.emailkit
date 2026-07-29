Test suite, golden-file harness and CI for Phase 1: `imio.emailkit.testing` layers for
both the `:default` and `:base` profiles, discovery / `render()` / locale-helper /
theme-token tests, the §8.2 override matrix (restyled defaults, opt-out, site-layer
precedence), and a GitHub Actions job that fails when the committed `.pt` files differ
from a fresh Maizzle build.
