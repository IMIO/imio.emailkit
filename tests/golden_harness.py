"""Reusable golden-file harness (SPEC §7).

> A provided test base class renders each registered template against its fixture
> and diffs against the golden file. Catches the two real regressions: a Tailwind
> class silently purged at build, and a ``${}`` placeholder that stopped resolving
> after a refactor.

Subclass :class:`GoldenTemplateTests`, set ``templates``, done:

.. code-block:: python

    class TestMyGoldens(GoldenTemplateTests):
        templates = ("item_published", "meeting_convocation")

The class-level ``pytest_generate_tests`` turns that into one test per
(template, language, part) triple, so a failure names exactly one file.

**Regeneration is deliberate and never automatic.** Set
``EMAILKIT_UPDATE_GOLDEN=1`` (``make update-golden``) and the run *writes* the
snapshots and reports every one as skipped -- so an update run can never be
mistaken for a verification run. Nothing regenerates as a side effect of a failing
comparison; a snapshot that repairs itself when it breaks is not a snapshot.

This lives in ``tests/`` rather than in the egg on purpose: shipping it for
external consumers is a Phase 4 deliverable (SPEC §9). Generalising it later is a
move, not a rewrite -- ``render_parts`` is the only seam a consumer would touch.
"""

import difflib
import pytest
import support


#: How many diff lines to show before truncating. Enough to see the change, few
#: enough that a purged stylesheet does not bury the summary.
DIFF_LINES = 40


def diff(expected, actual, label):
    lines = list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"{label} (committed golden)",
            tofile=f"{label} (rendered now)",
            n=2,
        )
    )
    shown = "".join(lines[:DIFF_LINES])
    if len(lines) > DIFF_LINES:
        shown += f"\n... {len(lines) - DIFF_LINES} more diff lines\n"
    return shown


class GoldenTemplateTests:
    """One test per template x language x part."""

    #: Template names, *unqualified*; the harness namespaces them.
    templates = ()

    #: §7's example ships ``fr``; ``en`` is the source language, and having both
    #: means a translation that stops resolving shows up as a diff rather than as
    #: nothing at all.
    languages = support.GOLDEN_LANGUAGES

    #: ``(attribute index, file suffix)`` of the ``render()`` return tuple.
    parts = (("html", 0), ("txt", 1))

    def pytest_generate_tests(self, metafunc):
        if "template" in metafunc.fixturenames:
            metafunc.parametrize("template", self.templates, ids=self.templates)
        if "language" in metafunc.fixturenames:
            metafunc.parametrize("language", self.languages, ids=self.languages)
        if "part" in metafunc.fixturenames:
            metafunc.parametrize("part", self.parts, ids=[p[0] for p in self.parts])

    # -- the one seam a consumer would override ----------------------------

    def render_parts(self, template, language):
        """Return ``(html, text)`` for one template in one language."""
        from imio.emailkit import render

        return render(
            support.qualified(template),
            context=support.load_fixture(template),
            language=language,
        )

    # -- the tests ---------------------------------------------------------

    def test_matches_golden(self, integration, template, language, part):
        suffix, index = part
        path = support.golden_path(template, language, suffix)

        # The existence check comes *before* rendering on purpose. With no
        # snapshot there is nothing to compare, and a render that blows up here
        # would report as a golden-file failure while the actual defect belongs to
        # -- and is already asserted by -- tests/test_render.py. One defect, one
        # red test.
        if not path.exists() and not support.updating_golden():
            pytest.skip(
                f"no golden file at {path}. Snapshots can only be generated once "
                "the compiled templates exist (`make build-emails`); then run "
                f"`make update-golden`. Missing: {path.name}"
            )

        actual = self.render_parts(template, language)[index]
        if not actual.endswith("\n"):
            actual += "\n"

        if support.updating_golden():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(actual, encoding="utf-8")
            pytest.skip(f"regenerated {path.name} ({len(actual)} bytes)")

        expected = path.read_text(encoding="utf-8")

        assert actual == expected, (
            f"{path.name} differs from the committed snapshot. Either a template "
            "changed on purpose -- then run `make update-golden` and commit the "
            "diff -- or a Tailwind class was purged / a ${...} stopped resolving.\n"
            + diff(expected, actual, path.name)
        )

    def test_golden_has_no_unresolved_placeholder(
        self, integration, template, language, part
    ):
        """A snapshot is only trustworthy if it was clean when it was taken.

        Without this, ``make update-golden`` on a broken engine bakes raw
        ``${member/fullname}`` into the committed file, and every later run
        happily confirms it (Phase 0: the zope.tal fallback raises nothing).
        """
        suffix, _index = part
        path = support.golden_path(template, language, suffix)
        if not path.exists() or support.updating_golden():
            pytest.skip(f"no committed snapshot to audit: {path.name}")

        support.assert_render_is_clean(
            path.read_text(encoding="utf-8"), f"golden {path.name}"
        )

    def test_every_template_has_a_fixture(self, template):
        """§7: "each template ships a fixture and a snapshot". The fixture is the
        harness's input, so a missing one is a hard failure, not a skip."""
        assert support.fixture_path(template).exists(), (
            f"no fixture at {support.fixture_path(template)}"
        )
