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

**Two harnesses, one contract.** ``TestOwnTemplateGoldens`` snapshots the authored
templates through ``render()``; ``TestShellGoldens`` snapshots a realistic legacy
body through §9 phase 3's ``render_shell()``. Both are the same §7 gate -- fixture
in, snapshot out, regenerated deliberately -- and the shell needs its own class only
because it has no template *name* to look up.
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


class TestShellGoldens(golden_harness.GoldenTemplateTests):
    """SPEC §9 phase 3 -- a realistic legacy body wrapped by ``render_shell``.

    ``docs/plans/phase-3.md`` §4 gate 4 asks for exactly this and §1 explains why
    it is the phase's *evidence* rather than a nicety: the exit criterion claims
    "zero template redesign", and the only honest way to support that claim
    without the PloneMeeting codebase is to snapshot the HTML idioms those
    notifications really emit and let a diff speak. ``tests/fixtures/
    shell_plonemeeting.py`` documents each idiom and why it is there.

    The one seam ``golden_harness`` exposes is :meth:`render_parts`, and this is
    what it exists for: the shell has no registered name (``render_shell`` takes
    ``subject`` and ``body_html``, not a template name), so the fixture holds the
    call rather than a context. Everything else -- one test per language per part,
    the deliberate-regeneration rule, the placeholder audit of the committed
    snapshot -- is inherited unchanged.
    """

    templates = support.SHELL_FIXTURES

    def render_parts(self, template, language):
        from imio.emailkit import render_shell

        subject, body_html = support.load_shell_fixture(template)
        return render_shell(subject, body_html, language=language)


#: Every fixture/snapshot name this module renders, in either harness. The orphan
#: tests below read this rather than one class's ``templates``, so adding a
#: harness cannot silently stop the orphan checks from covering it.
COVERED = set(TestOwnTemplateGoldens.templates) | set(TestShellGoldens.templates)


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
        orphans = sorted({
            path.name.split(".")[0]
            for path in support.GOLDEN_DIR.glob("*.*.*")
            if path.name.split(".")[0] not in COVERED
        })

        assert orphans == [], f"golden files with no template: {orphans}"
