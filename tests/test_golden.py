"""The golden-file smoke test for ``imio.emailkit``'s own templates (SPEC §7).

> Golden files + ``check-emails`` for its own templates -- dogfooding the full
> contract.

**One snapshot, deliberately.** This gate used to byte-compare every template in
every language: eighteen files, and they failed for two very different reasons
that the gate could not tell apart. A purged Tailwind class or a ``${...}`` that
stopped resolving is one. Any edit to a shared layout, or a Plone point release
that reflows the markup, is the other -- and that one arrived as eighteen diffs
that all had to be regenerated and none of which anybody read. A gate people stop
reading is a gate that no longer catches the first kind.

So one template, in one language, both parts: enough to notice that the rendering
pipeline produced something different, small enough that the diff gets looked at.
What covers the rest, and covered it all along:

* ``support.assert_render_is_clean`` runs on every body this suite renders, and
  ``test_render.py``, ``test_i18n.py``, ``test_theme_tokens.py`` and
  ``test_preview.py`` between them render all four templates in several
  languages. That is the check that catches an unresolved placeholder.
* ``make check-emails`` compares the committed build against a fresh one byte for
  byte, which is the gate that catches a stale or purged build.
* ``tests/dummies/`` runs the *shipped* harness end to end for two consumer
  add-ons, which is what proves §7's promise to consumers still works.

``TestFixtureCoverage`` below is unchanged in spirit and never churns: it is about
which templates exist, not what they render.

**The two Plone default mails are not here, for two independent reasons.**

1. They are jbot-only: rendered by a stock Plone view whose namespace requires the
   ``options/...`` dialect, so ``render()`` -- and therefore this harness -- can
   never render them (``docs/DECISIONS.md``; Phase 0 caveat D2).
2. Even if it could, that output is not snapshot-able: it embeds a freshly
   generated password-reset token and an expiry computed from the clock, so every
   run would differ.

They are covered instead in ``tests/test_default_mails.py``, on invariants, through
the real call site.
"""

import golden_harness
import support


support.require_runtime()


class TestOwnTemplateGoldens(golden_harness.GoldenTemplateTests):
    """One template through ``render()``, as a smoke test of the pipeline.

    ``notification`` is the one, because it is the worked example the docs point
    at and the only template with no special calling convention behind it.
    """

    templates = support.GOLDEN_TEMPLATES


#: Every name a fixture may legitimately belong to. Deliberately NOT the snapshot
#: set: a fixture is read by ``bin/preview-emails`` and ``@@emailkit-preview`` as
#: well as by this gate, so narrowing the gate to one template must not turn the
#: other three fixtures into "orphans" and delete them. What makes a fixture dead
#: is a template that no longer exists, which is what this checks.
COVERED = set(support.RENDERABLE_TEMPLATES) | set(support.SHELL_FIXTURES)


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

        # Scoped to THIS package's own templates. A consumer add-on's fixtures
        # live in the consumer's own tests/fixtures/ -- `tests/dummies/` proves
        # exactly that -- so asserting over every registered name would make this
        # package fail because somebody else's fixture is somewhere else. It also
        # made the assertion order-dependent: it passed alone and failed whenever
        # the dummies happened to be installed in the same session.
        own = (
            f"{support.PACKAGE_NAME}:"
            if hasattr(support, "PACKAGE_NAME")
            else "imio.emailkit:"
        )
        registered = {
            name.split(":", 1)[-1] for name in get_templates() if name.startswith(own)
        }
        without = sorted(
            name for name in registered if not support.fixture_path(name).exists()
        )

        assert without == [], (
            f"{own}* templates with no tests/fixtures/<name>.py: {without}"
        )

    def test_every_shipped_template_is_registered_for_discovery(self, integration):
        """The inverse of the guard this replaced, and the point of §8.

        There used to be a test here asserting that the two Plone default mails
        were **not** registered: a stock view rendered them, their bodies spoke
        that view's dialect, and a registration would have resolved to something
        ``render()`` could never render. ``browser/default_mails.py`` owns those
        views now, so the exception is gone and the assertion flips: every
        template this package ships is discovered, exactly like a consumer's.

        If a future change reintroduces a template that cannot go through
        ``render()``, this is the test that will say so.
        """
        from imio.emailkit.discovery import get_templates

        registered = {name.split(":", 1)[-1] for name in get_templates()}
        unregistered = sorted(set(support.RENDERABLE_TEMPLATES) - registered)

        assert unregistered == [], (
            f"{unregistered} are shipped but not registered for discovery, so "
            "they are invisible to the golden harness, to bin/preview-emails and "
            "to @@emailkit-preview"
        )

    def test_no_orphan_fixtures(self):
        orphans = sorted(set(support.available_fixtures()) - COVERED)

        assert orphans == [], f"fixtures with no template in the harness: {orphans}"

    def test_no_orphan_golden_files(self):
        """A snapshot nothing renders any more.

        Scoped to :data:`support.GOLDEN_TEMPLATES` rather than to ``COVERED``,
        because that is what this directory is now for: narrowing the gate and
        leaving the old snapshots behind would keep eighteen files in git that no
        test reads and no target regenerates.
        """
        orphans = sorted({
            path.name.split(".")[0]
            for path in support.GOLDEN_DIR.glob("*.*.*")
            if path.name.split(".")[0] not in set(support.GOLDEN_TEMPLATES)
        })

        assert orphans == [], (
            f"golden files for templates the gate no longer snapshots: {orphans}. "
            "Delete them, or add the template back to support.GOLDEN_TEMPLATES."
        )
