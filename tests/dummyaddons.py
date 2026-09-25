"""Installing the two dummy consumer add-ons, and running the CI contract on them.

The add-ons live in ``tests/dummies/`` and are documented there. This module
is the machinery around them: how they get discovered without being
pip-installed, and how the two CI gates required of every consumer add-on are
reproduced against them.

A real add-on is pip-installed, so Zope's autoinclude runs its
``configure.zcml`` at startup. These two live in another package's test tree,
so :func:`installed` runs their ZCML itself, through
``imio.emailkit.scan.scan_package``, the same code path the build tooling
uses on a real consumer.

Installation is scoped to a fixture, not global: registering the dummies for
the whole session would change what discovery answers for every other test.
It also gives the gate tests a negative control for free: outside the
fixture the dummy templates must not resolve.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import importlib
import os
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).parent
DUMMIES_DIR = HERE / "dummies"

#: The checkout's own Maizzle install, borrowed through a gitignored
#: ``node_modules`` symlink. See :func:`toolchain`.
CHECKOUT_NODE_MODULES = HERE.parent / "emails" / "node_modules"


@dataclass(frozen=True)
class DummyAddon:
    """One dummy consumer add-on: package, directories, and what it registers."""

    #: Importable package == the ZCML file's package == lookup namespace.
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
    def zcml(self):
        """The registration itself: one ``<emailkit:templates>`` block."""
        return self.root / "configure.zcml"

    def qualified(self, template):
        return f"{self.package}:{template}"


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

#: Both of them, used together by the discovery tests.
ADDONS = (MINIMAL, COMPLETE)


def all_qualified_names():
    return sorted(a.qualified(t) for a in ADDONS for t in a.templates)


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------


def _drop_from_sys_path():
    """Remove **every** occurrence of ``tests/dummies`` from ``sys.path``.

    Not just the entry this module added: pytest's ``prepend`` import mode
    puts ``tests/dummies`` on ``sys.path`` itself and never removes it.
    """
    root = str(DUMMIES_DIR)
    while root in sys.path:
        sys.path.remove(root)


def _snapshot_of_the_dummies():
    """The registry entries belonging to the dummies, as ``(templates, dirs)``.

    Normally both are empty; non-empty only inside an open ``installed()``.
    """
    from imio.emailkit import discovery

    packages = {addon.package for addon in ADDONS}
    templates = {
        name: template
        for name, template in discovery.get_templates().items()
        if template.package in packages
    }
    directories = {
        package: directory
        for package, directory in discovery.registered_directories().items()
        if package in packages
    }
    return templates, directories


def _restore(templates, directories):
    """Put a :func:`_snapshot_of_the_dummies` result back."""
    from imio.emailkit import discovery

    for template in templates.values():
        discovery.register_template(template)
    for package, directory in directories.items():
        discovery.register_directory(package, directory)


def _forget_the_dummies():
    from imio.emailkit import discovery

    for addon in ADDONS:
        discovery.forget_package(addon.package)


@contextmanager
def installed():
    """Register both dummy add-ons for the duration of the block, only.

    ``sys.path`` gains ``tests/dummies``, since the scan resolves the
    packages by dotted name. Registration runs through
    ``imio.emailkit.scan``, the code path a real consumer uses.

    Teardown removes only the dummies' own entries, not a snapshot of the
    whole registry: the Plone test layer loads ``imio.emailkit``'s ZCML
    lazily, so that layer's setup can run *inside* this block, and a
    whole-registry restore would then delete the host's own templates too.
    """
    from imio.emailkit import scan

    _drop_from_sys_path()
    sys.path.insert(0, str(DUMMIES_DIR))
    importlib.invalidate_caches()
    saved = _snapshot_of_the_dummies()
    try:
        for addon in ADDONS:
            scan.scan_package(addon.package)
        yield ADDONS
    finally:
        _forget_the_dummies()
        _restore(*saved)
        _drop_from_sys_path()


@contextmanager
def uninstalled():
    """Take the dummies away again inside a block that has them installed.

    The negative control for every registration assertion. Subtractive like
    :func:`installed`, so nothing else registered while the block is open is
    lost.
    """
    saved = _snapshot_of_the_dummies()
    _forget_the_dummies()
    try:
        yield
    finally:
        _restore(*saved)


# ---------------------------------------------------------------------------
# CI contract: build output must not be stale
# ---------------------------------------------------------------------------
#
# `bin/check-emails` cannot be pointed at these dummies: it resolves packages
# from the buildout working set. So its logic is reproduced here instead:
# snapshot, rebuild, diff, restore.

#: Statuses :func:`compare_output` reports. Only ``ok`` is a pass.
OK = "ok"
STALE = "STALE"
MISSING = "MISSING"  # built, never committed
ORPHAN = "ORPHAN"  # committed, no longer built


def compare_output(committed, fresh):
    """Compare two directories of compiled templates, both directions."""
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

    The symlink is required: Tailwind resolves the kit's import by walking
    up from the template's directory, and with no ``node_modules`` ancestor
    Maizzle silently ships the uncompiled stylesheet with exit code 0.

    It is removed again afterwards, or setuptools would follow it into the
    sdist.
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
    """Compile ``addon`` fresh and return ``(committed_dir, fresh_dir)``.

    Maizzle empties its output directory before writing, so the committed
    files are snapshotted first and restored afterwards.
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
        # Twins are hand-authored; copy them in or they report as ORPHAN.
        for twin in sorted(addon.twins_dir.glob("*.txt.pt")):
            shutil.copy2(twin, addon.templates_dir / twin.name)
        shutil.copytree(addon.templates_dir, fresh, dirs_exist_ok=True)
    finally:
        shutil.rmtree(addon.templates_dir)
        shutil.copytree(committed, addon.templates_dir)
    return committed, fresh
