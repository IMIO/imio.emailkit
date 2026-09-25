"""The dummy add-ons must be invisible outside the fixture that installs them.

This module has no autouse install fixture: it observes the registry and
``sys.path`` from outside, checked separately since either can leak on its
own.
"""

import dummyaddons
import support


support.require_runtime()


def registered():
    from imio.emailkit.discovery import available_templates

    return set(available_templates())


#: This package's own templates, and nothing else.
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
        """Enter, observe, leave, observe again, in one test."""
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
        """A wrong restore removes our own registrations, and later
        modules fail with ``TemplateNotFound``."""
        with dummyaddons.installed():
            assert registered() >= OWN, (
                "the host's own templates went missing *inside* installed(): "
                f"{sorted(OWN - registered())}"
            )

        assert registered() >= OWN, (
            f"the host's own templates did not come back: {sorted(OWN - registered())}"
        )

    def test_the_sys_path_entry_does_not_survive(self, integration):
        """A leftover entry stays hidden until something later imports
        from it."""
        import sys

        with dummyaddons.installed():
            assert str(dummyaddons.DUMMIES_DIR) in sys.path

        assert str(dummyaddons.DUMMIES_DIR) not in sys.path

    def test_nested_installation_still_leaves_nothing(self, integration):
        """``installed()`` restores an absolute state, not a counter."""
        with dummyaddons.installed(), dummyaddons.installed():
            assert registered() >= DUMMY

        assert registered() == OWN
