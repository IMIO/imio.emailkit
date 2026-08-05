"""The dummy add-ons must be invisible outside the fixture that installs them.

This module has **no autouse installation fixture**, on purpose: it is the one
place that observes the registry from the outside, so it can assert the invariant
the rest of the suite depends on.

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

Two properties are checked separately, because they break separately: the registry
(what ``installed()`` adds, and gives back afterwards) and ``sys.path`` (what makes
the packages importable at all).
"""

import dummyaddons
import support


support.require_runtime()


def registered():
    from imio.emailkit.discovery import available_templates

    return set(available_templates())


#: What the registry must hold in this package's own test session: its own
#: templates, and nothing else.
OWN = {support.qualified(name) for name in support.RENDERABLE_TEMPLATES}

DUMMY = set(dummyaddons.all_qualified_names())


class TestTheDummiesAreScoped:
    def test_they_are_invisible_by_default(self, integration):
        """No fixture, no dummy templates. The baseline every other module needs."""
        leaked = sorted(DUMMY & registered())

        assert leaked == [], (
            f"{leaked} are registered in a test that never installed them. Every "
            "module that asserts on the exact registered set now fails, in whatever "
            "order pytest happens to run them."
        )

    def test_only_this_packages_own_templates_are_registered(self, integration):
        assert registered() == OWN, (
            "the registry holds something other than imio.emailkit's own templates "
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
            f"the dummies were not registered inside installed(): "
            f"{sorted(DUMMY - inside)}"
        )
        assert after == OWN, (
            f"installed() leaked on the way out: {sorted(after - OWN)} extra, "
            f"{sorted(OWN - after)} missing. Restoring the snapshot has to give back "
            "exactly the host's own registrations -- no more, and no fewer."
        )

    def test_the_host_registrations_survive_the_snapshot(self, integration):
        """``installed()`` snapshots the registry, so it also *restores* it.

        Asserted from the host's side rather than the dummies', because that is the
        expensive way for this to go wrong: a snapshot put back wrongly takes
        ``imio.emailkit``'s own registrations with it, and the symptom is every
        later module failing with ``TemplateNotFound`` for a template nobody
        touched.
        """
        with dummyaddons.installed():
            assert registered() >= OWN, (
                "the host's own templates went missing *inside* installed(): "
                f"{sorted(OWN - registered())}"
            )

        assert registered() >= OWN, (
            f"the host's own templates did not come back: {sorted(OWN - registered())}"
        )

    def test_the_sys_path_entry_does_not_survive(self, integration):
        """The other half of the mechanism, and the half the registry cannot show.

        The packages have to be importable while they are installed -- the scan
        resolves them by dotted name and their fixtures are loaded from beside them
        -- so ``installed()`` manages ``sys.path`` as well as the registry. A stale
        entry left behind is invisible until something imports from it, which is the
        worst possible moment to find out.
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
