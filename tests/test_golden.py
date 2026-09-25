"""The golden-file smoke test for ``imio.emailkit``'s own templates.

Only one template, in one language, is snapshotted: many snapshots amplify
cosmetic reflows into diffs nobody reads, which then hides a real
regression. The two Plone default mails are not snapshotted, since their
output embeds a fresh token and a clock-based expiry and is covered in
``tests/test_default_mails.py`` instead.
"""

import golden_harness
import support


support.require_runtime()


class TestOwnTemplateGoldens(golden_harness.GoldenTemplateTests):
    """``notification``: the worked example in the docs, with no special
    calling convention."""

    templates = support.GOLDEN_TEMPLATES


#: Not just the snapshot set: a fixture is also read by ``bin/preview-emails``
#: and ``@@emailkit-preview``.
COVERED = set(support.RENDERABLE_TEMPLATES) | set(support.SHELL_FIXTURES)


class TestFixtureCoverage:
    """Every fixture must belong to a template the harness renders."""

    def test_every_registered_template_has_a_fixture(self, integration):
        """Driven off discovery, not a hardcoded list."""
        from imio.emailkit.discovery import get_templates

        # Scoped to this package's own templates: a consumer's fixtures
        # live in its own tests/fixtures/.
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
        """Every shipped template must be discovered, like a consumer's."""
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
        """Scoped to :data:`support.GOLDEN_TEMPLATES`, not ``COVERED``."""
        orphans = sorted({
            path.name.split(".")[0]
            for path in support.GOLDEN_DIR.glob("*.*.*")
            if path.name.split(".")[0] not in set(support.GOLDEN_TEMPLATES)
        })

        assert orphans == [], (
            f"golden files for templates the gate no longer snapshots: {orphans}. "
            "Delete them, or add the template back to support.GOLDEN_TEMPLATES."
        )
