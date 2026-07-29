"""Golden files for ``imio.emailkit``'s own templates -- the dogfooding gate (§7).

> Golden files + ``check-emails`` for its own templates -- dogfooding the full
> contract.

Together with ``make check-emails`` (build output is not stale) this is the whole
CI contract §7 asks of every consumer add-on, applied to us first.

**The two Plone default mails are not here, for two independent reasons.**

1. They are jbot-only: rendered by a stock Plone view whose namespace requires the
   ``options/...`` dialect, so ``render()`` -- and therefore this harness -- can
   never render them (``docs/DECISIONS.md``; Phase 0 caveat D2).
2. Even if it could, that output is not snapshot-able: it embeds a freshly
   generated password-reset token and an expiry computed from the clock, so every
   run would differ.

They are covered instead in ``tests/test_default_mails.py``, on invariants, through
the real call site. Golden files cover the ``render()`` path, where §6.1's purity
guarantee makes a byte comparison meaningful.
"""

import golden_harness
import support


support.require_runtime()


class TestOwnTemplateGoldens(golden_harness.GoldenTemplateTests):
    """Every template ``imio.emailkit`` ships through ``render()``.

    The two restyled Plone default mails are deliberately absent -- see
    ``TestFixtureCoverage`` below for why, and ``tests/test_default_mails.py`` for
    how they are covered instead.
    """

    templates = support.RENDERABLE_TEMPLATES


class TestFixtureCoverage:
    """Every fixture must belong to a template the harness renders.

    The reverse of ``test_every_template_has_a_fixture``: an orphan fixture means
    a template was renamed or dropped and its snapshot is now dead weight that
    nothing checks.
    """

    def test_every_registered_template_has_a_fixture(self, integration):
        """§7: "Each template ships a fixture and a snapshot".

        Driven off *discovery* rather than off a hardcoded list, so a template
        added to the registration without a fixture is caught here instead of
        being quietly absent from the golden gate, from ``make preview-emails``
        and from ``@@emailkit-preview`` -- three places that all read the same
        fixture directory.
        """
        from imio.emailkit.discovery import get_templates

        registered = {name.split(":", 1)[-1] for name in get_templates()}
        without = sorted(
            name for name in registered if not support.fixture_path(name).exists()
        )

        assert without == [], (
            f"registered templates with no tests/fixtures/<name>.py: {without}"
        )

    def test_the_default_mails_are_shipped_as_committed_jbot_overrides(self):
        """The two default mails are **jbot-only** and not golden-tested.

        ``docs/DECISIONS.md`` ("Default-mail templates are built once and copied
        to the jbot overrides dir") amends §8: they are rendered by a *stock Plone
        view*, so their bodies must use ``options/...`` and
        ``python:member.getProperty(...)`` (Phase 0, caveat D2 -- ``MemberData`` is
        not path-traversable at all), which ``render()``'s flat context can never
        satisfy wherever the files sit. So no ``render()``, no fixture, no
        snapshot.

        What is checked instead is that the artifacts *exist and are committed*:
        the build writes them, nothing else in this suite would notice if a build
        stopped producing one, and the staleness gate only compares files it finds
        on both sides. Their rendered output is asserted in
        ``tests/test_default_mails.py`` through the stock view.
        """
        missing = [
            support.JBOT_OVERRIDE_FILENAMES[name]
            for name in support.DEFAULT_MAIL_TEMPLATES
            if not support.override_path(name).exists()
        ]

        assert missing == [], f"jbot override files not committed: {missing}"

    def test_the_default_mails_are_not_registered_for_discovery(self, integration):
        """The other half of the same decision, asserted so it cannot drift back.

        Registering them would make them look ``render()``-able to the golden
        harness, to ``make preview-emails`` and to ``@@emailkit-preview`` -- all
        three of which would then fail at render time with a namespace error that
        says nothing about why. If a future change genuinely makes them
        renderable, this test is the place that says the decision changed.
        """
        from imio.emailkit.discovery import get_templates

        registered = {name.split(":", 1)[-1] for name in get_templates()}
        leaked = sorted(set(support.DEFAULT_MAIL_TEMPLATES) & registered)

        assert leaked == [], (
            f"{leaked} are registered for discovery, but their bodies use the "
            "stock view's options/... dialect and cannot be rendered by render(). "
            "See docs/DECISIONS.md."
        )

    def test_no_orphan_fixtures(self):
        covered = set(TestOwnTemplateGoldens.templates)
        orphans = sorted(set(support.available_fixtures()) - covered)

        assert orphans == [], f"fixtures with no template in the harness: {orphans}"

    def test_no_orphan_golden_files(self):
        covered = set(TestOwnTemplateGoldens.templates)
        orphans = sorted({
            path.name.split(".")[0]
            for path in support.GOLDEN_DIR.glob("*.*.*")
            if path.name.split(".")[0] not in covered
        })

        assert orphans == [], f"golden files with no template: {orphans}"
