"""The golden-file test base class SPEC §7 promises consumer add-ons.

> A provided test base class renders each registered template against its fixture
> and diffs against the golden file. Catches the two real regressions: a Tailwind
> class silently purged at build, and a ``${}`` placeholder that stopped resolving
> after a refactor.

A consumer add-on's whole email test suite is this::

    from imio.emailkit.golden import GoldenTemplateTests


    class TestEmailGoldens(GoldenTemplateTests):
        package = "imio.pm.notifications"
        templates = ("item_published", "meeting_convocation")

with ``tests/fixtures/<template>.py`` and ``tests/golden/<template>.<lang>.<ext>``
next to it -- the layout §7 draws. That is one test per
(template x language x part), so a failure names exactly one file.

**Why this lives in the egg and not in a test directory.** §7 says *provided*, and
a base class a consumer cannot import is not provided. Phases 1-3 kept it in
``tests/golden_harness.py`` with a note that shipping it was Phase 4 work; this is
that move. ``tests/golden_harness.py`` is now a thin subclass that binds this
class to ``imio.emailkit``'s own suite, so the export is a move rather than a fork.

**Why a separate module rather than ``imio.emailkit.testing``.** This module
imports ``pytest`` at import time. ``imio.emailkit.testing`` holds the Plone test
layers, and plenty of iMio add-ons still run their tests under
``zope.testrunner``; folding a pytest import into that module would make the
layers unimportable for them. Two modules, two dependencies, no coupling.

**Regeneration is deliberate and never automatic.** Set
``EMAILKIT_UPDATE_GOLDEN=1`` and the run *writes* the snapshots and reports every
one as skipped -- so an update run can never be mistaken for a verification run.
Nothing regenerates as a side effect of a failing comparison; a snapshot that
repairs itself when it breaks is not a snapshot.
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


# On the bare ``assert`` statements below: this module ships in the egg, so ruff's
# S101 (assert in non-test code) fires on it, and the exemption is recorded in
# ``pyproject.toml``'s ``per-file-ignores`` rather than sprinkled here. The reason
# is that this *is* test code -- a pytest base class a consumer's test module
# subclasses -- and ``assert cond, message`` is the only form pytest reports as a
# test failure with a diff. Raising ``AssertionError`` by hand would work and read
# worse, and ``python -O`` (which strips asserts) does not run test suites.


#: Environment variable that turns a verification run into a regeneration run.
UPDATE_GOLDEN_ENV = "EMAILKIT_UPDATE_GOLDEN"

#: §7's example ships ``fr``; ``en`` is the source language, and having both means
#: a translation that stops resolving shows up as a diff rather than as nothing at
#: all. Override ``languages`` on the subclass to trim or extend.
DEFAULT_LANGUAGES = ("fr", "en")

#: How many diff lines to show before truncating. Enough to see the change, few
#: enough that a purged stylesheet does not bury the summary.
DIFF_LINES = 40

#: A Chameleon placeholder that survived into the output. Phase 0: without the
#: ``IPageTemplateEngine`` utility, ``zope.pagetemplate`` falls back to
#: ``zope.tal``, where ``${...}`` passes through **verbatim and with no error** --
#: so a test that only checks "my marker is present" ships raw placeholders to
#: production and stays green.
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

    The single most important assertion in an email test suite: the failure this
    catches is silent, and a mail that reaches a commune reading
    ``Bonjour ${member/fullname}`` looks exactly like a successful send from the
    sending side.
    """
    leftovers = unresolved_placeholders(rendered)
    assert not leftovers, (
        f"unsubstituted Chameleon placeholder in {what}: {leftovers[:5]}"
    )
    assert "${" not in rendered, f"stray '${{' in {what}"
    residue = sorted(set(TAL_RESIDUE.findall(rendered)))
    assert not residue, f"leftover TAL/i18n attributes in {what}: {residue}"


def load_fixture(path):
    """Return the ``CONTEXT`` dict of a ``tests/fixtures/<template>.py`` file.

    Loaded *by path* rather than imported, so ``tests/fixtures/`` stays a
    directory of data files -- which is what §7 describes -- instead of having to
    become an importable package.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No fixture at {path}. SPEC §7 requires one per template: a module "
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
            f"{path} defines no CONTEXT. A §7 fixture is a module-level dict "
            "named CONTEXT holding the render context."
        ) from None
    return dict(context)


def diff(expected, actual, label):
    """A truncated unified diff, labelled so the two sides cannot be confused."""
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
    """One test per template x language x part.

    Everything below is a class attribute a subclass may set; the only method
    worth overriding is :meth:`render_parts`.
    """

    #: Namespace of the add-on whose templates these are -- the package part of
    #: the ``<package>:<template>`` lookup name its ``<emailkit:templates>`` ZCML
    #: registration gives them (SPEC §4). The harness namespaces :attr:`templates`
    #: with it.
    package = None

    #: Template basenames, *unqualified*.
    templates = ()

    #: Languages to snapshot. See :data:`DEFAULT_LANGUAGES`.
    languages = DEFAULT_LANGUAGES

    #: ``(file suffix, index into render()'s return tuple)``.
    parts = (("html", 0), ("txt", 1))

    #: ``tests/fixtures`` and ``tests/golden``, absolute. ``None`` means "beside
    #: the module this subclass is defined in", which is §7's layout.
    fixtures_dir = None
    golden_dir = None

    #: Name of the pytest fixture that sets up the Plone site. The harness pulls
    #: it in for every test rather than naming it in each signature, so a consumer
    #: whose layer fixture is called something else changes this one string.
    #: ``None`` disables it (for a suite that sets its layer up another way).
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
        """``item_published`` -> ``imio.pm.notifications:item_published`` (§4)."""
        assert cls.package, (
            f"{cls.__name__} sets no `package`. SPEC §4 namespaces template names "
            "as <package>:<template>, so the harness cannot look anything up "
            "without the package name the add-on's ZCML registered them under."
        )
        return f"{cls.package}:{template}"

    # -- the one seam a consumer would override ----------------------------

    #: Host every snapshot is rendered against, whatever host the test server is
    #: actually listening on. See :meth:`stable_host`.
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

        A snapshot has to be reproducible, and without this one it is not. The kit
        builds ``asset_base`` from ``portal_url``, which is ``getSite()
        .absolute_url()``, which is whatever host the test request happens to
        carry -- so every image ``src``, every ``background`` attribute and the
        web-font stylesheet land in the committed file with that host baked in.

        For years that host was ``nohost`` and the problem was invisible. It stops
        being invisible the moment a test layer serves on a real socket: Plone
        6.2's newer ``plone.app.testing`` does, so the same templates rendered
        ``http://localhost:37267/...`` and every snapshot in the suite failed at
        once, on a port that is different again next run. Regenerating was not a
        fix -- the regenerated files fail on the following run.

        Only the scheme and the authority are replaced. The portal's own path
        survives, so a consumer whose test site is not called ``plone`` still gets
        its own path in the snapshot; only the part that was never theirs to begin
        with is normalised.
        """
        from urllib.parse import urlsplit
        from urllib.parse import urlunsplit

        # `import imio.emailkit.render` yields the render FUNCTION, because
        # `imio/emailkit/__init__.py` rebinds the name to it -- that is the public
        # API §6.1 documents. The module itself is only reachable this way, and
        # patching the function object instead is the mistake that made
        # `bin/preview-emails` silently drop every image once already.
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
        """Overridable so a suite can tighten the audit; see the module docs."""
        assert_render_is_clean(rendered, label)

    # -- the tests ---------------------------------------------------------

    def test_matches_golden(self, template, language, part):
        suffix, index = part
        path = self.golden_path(template, language, suffix)

        # The existence check comes *before* rendering on purpose. With no
        # snapshot there is nothing to compare, and a render that blows up here
        # would report as a golden-file failure while the actual defect belongs
        # to the render tests. One defect, one red test.
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
        """A snapshot is only trustworthy if it was clean when it was taken.

        Without this, a regeneration run on a broken engine bakes raw
        ``${member/fullname}`` into the committed file, and every later run
        happily confirms it.
        """
        suffix, _index = part
        path = self.golden_path(template, language, suffix)
        if not path.exists() or updating_golden():
            pytest.skip(f"no committed snapshot to audit: {path.name}")

        self.assert_clean(path.read_text(encoding="utf-8"), f"golden {path.name}")

    def test_every_template_has_a_fixture(self, template):
        """§7: "each template ships a fixture and a snapshot". The fixture is the
        harness's input, so a missing one is a hard failure, not a skip."""
        assert self.fixture_path(template).exists(), (
            f"no fixture at {self.fixture_path(template)}"
        )
