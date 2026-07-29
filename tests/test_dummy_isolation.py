"""The dummy add-ons must be invisible outside the fixture that installs them.

This module has **no autouse installation fixture**, on purpose: it is the one
place that observes discovery from the outside, so it can assert the invariant the
rest of the suite depends on.

It exists because that invariant was broken once, and the way it broke is worth
recording. ``tests/dummies/conftest.py`` installs the add-ons per test and removes
them again -- but with pytest's default ``--import-mode=prepend``, importing that
conftest *also* puts ``tests/dummies/`` on ``sys.path``, permanently. A teardown
that only undid its own insertion therefore undid nothing: the dummy templates
stayed registered for the rest of the session, and
``tests/test_golden.py::test_every_registered_template_has_a_fixture`` and
``tests/test_preview.py`` failed on ``convocation`` -- a template that belongs to
``dummy.complete`` and has no fixture in *this* package -- while both passed in
isolation.

Those two tests assert on the **exact** registered set rather than on a subset.
That is what caught this, and it is the reason the assertions here are equalities
too.
"""

import dummyaddons
import support


support.require_runtime()


def registered():
    from imio.emailkit import discovery
    from imio.emailkit.discovery import available_templates

    discovery.invalidate_cache()
    return set(available_templates())


#: What discovery must answer in this package's own test session: its own
#: templates, and nothing else.
OWN = {support.qualified(name) for name in support.RENDERABLE_TEMPLATES}

DUMMY = set(dummyaddons.all_qualified_names())


class TestTheDummiesAreScoped:
    def test_they_are_invisible_by_default(self, integration):
        """No fixture, no dummy templates. The baseline every other module needs."""
        leaked = sorted(DUMMY & registered())

        assert leaked == [], (
            f"{leaked} are discoverable in a test that never installed them. Every "
            "module that asserts on the exact registered set now fails, in whatever "
            "order pytest happens to run them."
        )

    def test_only_this_packages_own_templates_are_registered(self, integration):
        assert registered() == OWN, (
            "discovery answers something other than imio.emailkit's own templates "
            f"outside the dummy fixture: {sorted(registered() - OWN)} extra, "
            f"{sorted(OWN - registered())} missing"
        )

    def test_installation_is_fully_reversible(self, integration):
        """Enter, observe, leave, observe again -- in one test, so ordering cannot
        make it pass by accident."""
        with dummyaddons.installed():
            inside = registered()

        after = registered()

        assert inside >= DUMMY, (
            f"the dummies were not discoverable inside installed(): "
            f"{sorted(DUMMY - inside)}"
        )
        assert after == OWN, f"installed() leaked on the way out: {sorted(after - OWN)}"

    def test_the_sys_path_entry_does_not_survive(self, integration):
        """The mechanism, not just its effect.

        Asserted separately because the effect is only visible through a discovery
        rescan: a stale ``sys.path`` entry with a warm cache looks clean right up
        until something invalidates the cache, which is the worst possible time to
        find out.
        """
        import sys

        with dummyaddons.installed():
            assert str(dummyaddons.DUMMIES_DIR) in sys.path

        assert str(dummyaddons.DUMMIES_DIR) not in sys.path

    def test_nested_installation_still_leaves_nothing(self, integration):
        """``installed()`` is absolute, not a counter, and that is deliberate.

        The gate modules install per test *and* call ``installed()`` directly. An
        incremental implementation would then depend on which one exits first;
        this one cannot.
        """
        with dummyaddons.installed(), dummyaddons.installed():
            assert registered() >= DUMMY

        assert registered() == OWN
