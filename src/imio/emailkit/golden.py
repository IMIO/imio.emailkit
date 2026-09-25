"""Golden-file test base class for a consumer add-on's email templates.

Renders each registered template against its fixture and diffs it against
the committed golden file. Set ``EMAILKIT_UPDATE_GOLDEN=1`` to write new
snapshots instead of comparing.
"""

from contextlib import contextmanager
from pathlib import Path

import difflib
import importlib
import importlib.util
import inspect
import os
import pytest
import re


# S101 (assert in non-test code) is ignored for this file in pyproject.toml.
# This is test code, and pytest only reports `assert cond, message` with a diff.


#: Turns a verification run into a regeneration run.
UPDATE_GOLDEN_ENV = "EMAILKIT_UPDATE_GOLDEN"

#: Snapshotted by default.
DEFAULT_LANGUAGES = ("fr", "en")

#: How many diff lines to show before truncating.
DIFF_LINES = 40

#: A Chameleon placeholder left unresolved in rendered output.
UNRESOLVED_PLACEHOLDER = re.compile(r"\$\{[^}]*\}")

#: TAL/i18n attributes that should never survive a render.
TAL_RESIDUE = re.compile(r"\s(?:tal|i18n|metal):[a-z]+=")


def updating_golden():
    """True when this run regenerates snapshots instead of verifying them."""
    return os.environ.get(UPDATE_GOLDEN_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def unresolved_placeholders(rendered):
    return UNRESOLVED_PLACEHOLDER.findall(rendered)


def assert_render_is_clean(rendered, what="output"):
    """No unsubstituted placeholder and no leftover TAL attribute.

    Catches a mail that would silently send as ``Bonjour ${member/fullname}``.
    """
    leftovers = unresolved_placeholders(rendered)
    assert not leftovers, (
        f"unsubstituted Chameleon placeholder in {what}: {leftovers[:5]}"
    )
    assert "${" not in rendered, f"stray '${{' in {what}"
    residue = sorted(set(TAL_RESIDUE.findall(rendered)))
    assert not residue, f"leftover TAL/i18n attributes in {what}: {residue}"


def load_fixture(path):
    """Return the ``CONTEXT`` dict of a ``tests/fixtures/<template>.py`` file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No fixture at {path}. Each template requires one: a module "
            "with a CONTEXT dict of the data the template renders against."
        )
    spec = importlib.util.spec_from_file_location(
        f"_emailkit_fixture_{path.stem}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        context = module.CONTEXT
    except AttributeError:
        raise AssertionError(
            f"{path} defines no CONTEXT. A fixture is a module-level dict "
            "named CONTEXT holding the render context."
        ) from None
    return dict(context)


def diff(expected, actual, label):
    """A truncated unified diff between the two labelled sides."""
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
    """One test per template x language x part. Configure via class attributes."""

    #: Package part of the ``<package>:<template>`` name.
    package = None

    #: Template basenames, unqualified.
    templates = ()

    languages = DEFAULT_LANGUAGES

    #: ``(file suffix, index into render()'s return tuple)``.
    parts = (("html", 0), ("txt", 1))

    #: ``None`` means beside the module the subclass is defined in.
    fixtures_dir = None
    golden_dir = None

    #: Pytest fixture that sets up the Plone site. ``None`` disables it.
    layer_fixture = "integration"

    # -- wiring ------------------------------------------------------------

    @pytest.fixture(autouse=True)
    def _emailkit_plone_site(self, request):
        if self.layer_fixture:
            request.getfixturevalue(self.layer_fixture)

    def pytest_generate_tests(self, metafunc):
        if "template" in metafunc.fixturenames:
            metafunc.parametrize("template", self.templates, ids=self.templates)
        if "language" in metafunc.fixturenames:
            metafunc.parametrize("language", self.languages, ids=self.languages)
        if "part" in metafunc.fixturenames:
            metafunc.parametrize("part", self.parts, ids=[p[0] for p in self.parts])

    @classmethod
    def suite_directory(cls):
        """The directory the subclass's test module lives in."""
        return Path(inspect.getfile(cls)).parent

    @classmethod
    def fixtures_directory(cls):
        return Path(cls.fixtures_dir or cls.suite_directory() / "fixtures")

    @classmethod
    def golden_directory(cls):
        return Path(cls.golden_dir or cls.suite_directory() / "golden")

    @classmethod
    def fixture_path(cls, template):
        return cls.fixtures_directory() / f"{template}.py"

    @classmethod
    def golden_path(cls, template, language, suffix):
        return cls.golden_directory() / f"{template}.{language}.{suffix}"

    @classmethod
    def qualified(cls, template):
        """``item_published`` -> ``imio.pm.notifications:item_published``."""
        assert cls.package, (
            f"{cls.__name__} sets no `package`. Template names are namespaced "
            "as <package>:<template>, so the harness cannot look anything up "
            "without the package name the add-on's ZCML registered them under."
        )
        return f"{cls.package}:{template}"

    # -- the one seam a consumer would override ----------------------------

    #: Host every snapshot is rendered against. See :meth:`stable_host`.
    snapshot_host = "http://nohost"

    def render_parts(self, template, language):
        """Return ``(html, text)`` for one template in one language."""
        from imio.emailkit import render

        with self.stable_host():
            return render(
                self.qualified(template),
                context=load_fixture(self.fixture_path(template)),
                language=language,
            )

    @contextmanager
    def stable_host(self):
        """Pin the host in ``portal_url`` for the duration of a snapshot render.

        Without this, the host of the test request bakes into every image
        ``src`` in the committed snapshot. Only scheme and authority are
        replaced; the portal's own path is kept.
        """
        from urllib.parse import urlsplit
        from urllib.parse import urlunsplit

        # Get the real module, not the render function `__init__.py` rebinds
        # the name to, so the patched attribute is the one render() reads.
        module = importlib.import_module("imio.emailkit.render")
        original = module.portal_url

        def pinned():
            real = original()
            if not real:
                return real
            host = urlsplit(self.snapshot_host)
            parts = urlsplit(real)
            return urlunsplit((
                host.scheme or parts.scheme,
                host.netloc or parts.netloc,
                parts.path,
                parts.query,
                parts.fragment,
            ))

        module.portal_url = pinned
        try:
            yield
        finally:
            module.portal_url = original

    def assert_clean(self, rendered, label):
        """Overridable so a suite can tighten the audit."""
        assert_render_is_clean(rendered, label)

    # -- the tests ---------------------------------------------------------

    def test_matches_golden(self, template, language, part):
        suffix, index = part
        path = self.golden_path(template, language, suffix)

        # Check existence before rendering, so a render error reports as
        # such, not as a golden-file failure.
        if not path.exists() and not updating_golden():
            pytest.skip(
                f"no golden file at {path}. Snapshots can only be generated once "
                "the compiled templates exist (`bin/compile-emails`); then run "
                f"with {UPDATE_GOLDEN_ENV}=1. Missing: {path.name}"
            )

        actual = self.render_parts(template, language)[index]
        if not actual.endswith("\n"):
            actual += "\n"

        if updating_golden():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(actual, encoding="utf-8")
            pytest.skip(f"regenerated {path.name} ({len(actual)} bytes)")

        expected = path.read_text(encoding="utf-8")

        assert actual == expected, (
            f"{path.name} differs from the committed snapshot. Either a template "
            f"changed on purpose -- then re-run with {UPDATE_GOLDEN_ENV}=1 and "
            "commit the diff -- or a Tailwind class was purged / a ${...} stopped "
            "resolving.\n" + diff(expected, actual, path.name)
        )

    def test_golden_has_no_unresolved_placeholder(self, template, language, part):
        """A snapshot is only trustworthy if it was clean when it was taken."""
        suffix, _index = part
        path = self.golden_path(template, language, suffix)
        if not path.exists() or updating_golden():
            pytest.skip(f"no committed snapshot to audit: {path.name}")

        self.assert_clean(path.read_text(encoding="utf-8"), f"golden {path.name}")

    def test_every_template_has_a_fixture(self, template):
        """A missing fixture is a hard failure, not a skip."""
        assert self.fixture_path(template).exists(), (
            f"no fixture at {self.fixture_path(template)}"
        )
