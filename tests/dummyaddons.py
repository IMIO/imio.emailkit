"""Installing the two dummy consumer add-ons, and running §7's CI contract on them.

The add-ons themselves live in ``tests/dummies/`` and are documented there. This
module is the machinery around them: how they get discovered without being
pip-installed, and how the two CI gates §7 requires of every consumer add-on are
reproduced against them.

----------------------------------------------------------------------------
Faking an entry point, and why it is not really faking
----------------------------------------------------------------------------

``imio.emailkit.discovery`` reads ``importlib.metadata.entry_points(group=...)``,
which enumerates the ``*.dist-info`` / ``*.egg-info`` directories found on
``sys.path``. So a distribution is "installed", as far as the entry-point machinery
is concerned, when a directory named ``<name>-<version>.dist-info`` containing
``METADATA`` and ``entry_points.txt`` sits next to the importable package on a
``sys.path`` entry. That is what ``tests/dummies/`` is, and the ``entry_points.txt``
files there are byte-for-byte what ``pip`` writes from a ``pyproject.toml``
``[project.entry-points."imio.emailkit.templates"]`` block.

Nothing is monkeypatched and no private API is touched: the code under test runs
the same ``entry_points()`` call it runs in production, over real metadata. The
only difference from a real add-on is *who wrote the ``.dist-info``*.

``.dist-info`` directories are gitignored by nothing (only ``*.egg-info`` is), so
they are committed, readable and reviewable -- which matters, because §7 says these
add-ons double as documentation and the registration is half of what a reader came
for.

----------------------------------------------------------------------------
Why installation is scoped to a fixture rather than global
----------------------------------------------------------------------------

Registering the dummies for the whole session would change what
``available_templates()`` answers for every other test in the suite --
``tests/test_golden.py`` drives its fixture-coverage check off discovery and would
start demanding ``tests/fixtures/convocation.py``. Scoping it also gives the gate
tests a *negative* control for free: outside the fixture the dummy templates must
not resolve.

``discovery.invalidate_cache()`` exists for exactly this ("For tests that add or
remove a registration"), so this is the sanctioned seam rather than a workaround.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import importlib
import importlib.metadata
import os
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).parent
DUMMIES_DIR = HERE / "dummies"

#: The checkout's own Maizzle install. The dummies borrow it through a gitignored
#: ``node_modules`` symlink rather than running a second ``npm ci`` -- see
#: :func:`ensure_toolchain`.
CHECKOUT_NODE_MODULES = HERE.parent / "emails" / "node_modules"


@dataclass(frozen=True)
class DummyAddon:
    """One dummy consumer add-on, described the way §5's recipe describes a real
    one: ``(package, emails_dir, templates_dir)`` plus what it registers."""

    #: Entry-point name == lookup namespace == importable package (§4).
    package: str
    #: Basenames of the templates it registers, sorted.
    templates: tuple
    #: Basenames that ship a hand-authored ``.txt.pt`` twin.
    twins: tuple
    #: Languages its suite snapshots.
    languages: tuple

    @property
    def root(self):
        return DUMMIES_DIR / Path(*self.package.split("."))

    @property
    def emails_dir(self):
        return self.root / "emails"

    @property
    def templates_dir(self):
        return self.root / "templates"

    @property
    def twins_dir(self):
        return self.emails_dir / "twins"

    @property
    def suite_dir(self):
        return self.root / "tests"

    @property
    def fixtures_dir(self):
        return self.suite_dir / "fixtures"

    @property
    def golden_dir(self):
        return self.suite_dir / "golden"

    @property
    def dist_info(self):
        return DUMMIES_DIR / f"{self.package.replace('.', '_')}-1.0.dist-info"

    def qualified(self, template):
        return f"{self.package}:{template}"

    def registration(self):
        """The ``emailkit`` dict the entry point points at."""
        return importlib.import_module(self.package).emailkit


MINIMAL = DummyAddon(
    package="dummy.minimal",
    templates=("notification",),
    twins=(),
    languages=("fr",),
)

COMPLETE = DummyAddon(
    package="dummy.complete",
    templates=("convocation", "notification"),
    twins=("convocation", "notification"),
    languages=("fr", "en"),
)

#: Both of them, which is what SPEC §7 asks for: "discovery tests with two dummy
#: addons (also serving as living documentation)".
ADDONS = (MINIMAL, COMPLETE)


def all_qualified_names():
    return sorted(a.qualified(t) for a in ADDONS for t in a.templates)


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------


def _refresh_metadata_caches():
    """Make ``importlib.metadata`` and discovery see the current ``sys.path``.

    ``importlib.metadata`` caches its per-directory listings, and
    ``imio.emailkit.discovery`` caches the whole scan (deliberately: §4 has it scan
    "once at startup"). Both have to be dropped whenever the set of visible
    distributions changes.
    """
    importlib.invalidate_caches()
    from imio.emailkit import discovery

    discovery.invalidate_cache()


def _drop_from_sys_path():
    """Remove **every** occurrence of ``tests/dummies`` from ``sys.path``.

    Not "the one we added": pytest puts it there itself. With
    ``--import-mode=prepend`` (the default) importing ``tests/dummies/conftest.py``
    inserts its own directory on ``sys.path`` and never takes it out again, so a
    teardown that only undoes its own insertion undoes nothing and the dummy
    add-ons stay discoverable for the rest of the session.

    That is not a hypothetical. It made ``tests/test_golden.py``'s orphan check and
    ``tests/test_preview.py``'s template listing fail on ``convocation`` -- a
    template belonging to a dummy add-on -- while both passed in isolation. Those
    two assert on the *exact* registered set, which is the property that caught it
    and is worth keeping.

    Removing pytest's insertion is safe: collection is complete before the first
    test runs, so every module that needed importing from there is already in
    ``sys.modules``, and nothing outside ``tests/dummies/`` imports from it by name.
    """
    root = str(DUMMIES_DIR)
    while root in sys.path:
        sys.path.remove(root)


@contextmanager
def installed():
    """Make both dummy add-ons discoverable for the duration of the block, only.

    Idempotent and re-entrant-safe by being absolute rather than incremental: the
    block starts by normalising ``sys.path`` and ends by clearing the entry
    unconditionally. "Discoverable inside, invisible outside" is then true however
    the block was entered.
    """
    _drop_from_sys_path()
    sys.path.insert(0, str(DUMMIES_DIR))
    _refresh_metadata_caches()
    try:
        yield ADDONS
    finally:
        _drop_from_sys_path()
        _refresh_metadata_caches()


@contextmanager
def uninstalled():
    """Take them away again inside a block that has them installed.

    The negative control for every discovery assertion: without it, "the dummy
    templates are found" could be true for a reason that has nothing to do with
    the entry point.
    """
    _drop_from_sys_path()
    _refresh_metadata_caches()
    try:
        yield
    finally:
        sys.path.insert(0, str(DUMMIES_DIR))
        _refresh_metadata_caches()


# ---------------------------------------------------------------------------
# Gate 1 of §7's CI contract: build output is not stale
# ---------------------------------------------------------------------------
#
# SPEC §5's `bin/check-emails` is the shipped implementation of this gate and lives
# in `imio.recipe.emailkit`. It cannot be pointed at these dummies: it resolves
# packages from the buildout working set, and a `.dist-info` directory dropped on
# `sys.path` by a test fixture is not in anybody's working set. So the gate's
# *logic* is reproduced here -- snapshot, rebuild, diff, restore -- which is also
# what makes it testable in both directions (green and red) without Node in the
# loop for the red half.

#: Statuses :func:`compare_output` reports. Only ``ok`` is a pass.
OK = "ok"
STALE = "STALE"
MISSING = "MISSING"  # built, never committed
ORPHAN = "ORPHAN"  # committed, no longer built


def compare_output(committed, fresh):
    """Compare two directories of compiled templates.

    Returns ``[(status, filename), ...]`` sorted by filename. Both directions are
    reported on purpose: a template that is built but not committed will not ship,
    and a template that is committed but no longer built is dead weight that the
    golden gate would keep confirming for ever.
    """
    committed, fresh = Path(committed), Path(fresh)
    names = sorted(
        {p.name for p in committed.glob("*.pt")} | {p.name for p in fresh.glob("*.pt")}
    )
    report = []
    for name in names:
        left, right = committed / name, fresh / name
        if not left.is_file():
            report.append((MISSING, name))
        elif not right.is_file():
            report.append((ORPHAN, name))
        elif left.read_bytes() != right.read_bytes():
            report.append((STALE, name))
        else:
            report.append((OK, name))
    return report


def is_stale(report):
    return any(status != OK for status, _name in report)


def format_report(report):
    return "\n".join(f"  {status:<9} {name}" for status, name in report) or "  (empty)"


def node_available():
    return bool(shutil.which("npx")) and CHECKOUT_NODE_MODULES.is_dir()


def node_modules_link(addon):
    return addon.emails_dir / "node_modules"


@contextmanager
def toolchain(addon):
    """Point the add-on's ``emails/`` at the checkout's Maizzle install, briefly.

    A real consumer add-on has its own ``package.json`` and its own ``npm ci``;
    these two borrow the checkout's, because a second install of the whole Maizzle
    toolchain per dummy buys nothing and costs a minute of CI.

    **The symlink is required and cannot be worked around.** Tailwind resolves the
    ``@import "@maizzle/tailwindcss"`` that ``Main.vue`` emits by walking up from the
    *template's* directory, and with no ``node_modules`` ancestor Maizzle catches the
    CSS error and **ships the uncompiled stylesheet with exit code 0** -- measured:
    5.3 KB of compiled output with inlined styles becomes 3.5 KB with none, and the
    build says "Built 1 template".

    **And it is removed again afterwards**, which is not tidiness. ``MANIFEST.in``
    does ``graft tests``, and setuptools' file walk follows symlinks -- so a
    ``node_modules`` link left behind in the working tree puts ~20 000 files from the
    Maizzle toolchain into the sdist. It is gitignored, so nothing else would ever
    tell you.
    """
    link = node_modules_link(addon)
    created = not link.exists()
    if created:
        link.symlink_to(
            os.path.relpath(CHECKOUT_NODE_MODULES, addon.emails_dir),
            target_is_directory=True,
        )
    try:
        yield link
    finally:
        if created and link.is_symlink():
            link.unlink()


def rebuild(addon):
    """Compile ``addon`` fresh and return ``(committed_dir, fresh_dir)`` in a tmpdir.

    The working tree is left exactly as it was found. Maizzle writes into (and
    first **empties**) its output directory, which is the committed
    ``templates/``, so the committed files are snapshotted first and restored
    afterwards -- the same dance ``make check-emails`` does, and for the same
    reason: a check that leaves your tree holding a build you did not ask for is a
    check people stop running.
    """
    workdir = Path(tempfile.mkdtemp(prefix=f"emailkit-{addon.package}-"))
    committed, fresh = workdir / "committed", workdir / "fresh"
    committed.mkdir()
    addon.templates_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(addon.templates_dir, committed, dirs_exist_ok=True)
    try:
        with toolchain(addon):
            result = subprocess.run(
                ["npx", "maizzle", "build"],  # noqa: S607
                cwd=addon.emails_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=600,
            )
        assert result.returncode == 0, (
            f"`maizzle build` failed for {addon.package} "
            f"(exit {result.returncode}):\n{result.stdout}\n{result.stderr}"
        )
        # SPEC §4's plaintext twins are hand-authored source, so the build cannot
        # produce them; `make build-emails` copies them in afterwards and so must
        # anything that compares against a committed tree, or every twin reports
        # as an ORPHAN.
        for twin in sorted(addon.twins_dir.glob("*.txt.pt")):
            shutil.copy2(twin, addon.templates_dir / twin.name)
        shutil.copytree(addon.templates_dir, fresh, dirs_exist_ok=True)
    finally:
        shutil.rmtree(addon.templates_dir)
        shutil.copytree(committed, addon.templates_dir)
    return committed, fresh
