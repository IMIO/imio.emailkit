"""A stand-in for a site/client package that overrides our overrides.

This is the test double for SPEC §8.2 level 1 -- "replace the template markup per
site/client: register a jbot directory on a *more specific* browser layer". It is
test support, not a draft of anything shipped.

Phase 0 established that "more specific" only means something for a layer that
**extends** ``IEmailkitLayer``: for a *sibling* layer, precedence follows
``getAllUtilitiesRegisteredFor(ILocalBrowserLayerType)`` registration order,
which is effectively arbitrary (``docs/DECISIONS.md``, 2026-07-29 "§8.2 override
story requires extending ``IEmailkitLayer``"). So this package extends it, and
the test asserting the win is only ever run in that configuration -- writing it
with a sibling layer would produce a test that passes on one machine and fails on
the next.
"""
