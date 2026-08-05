"""Installing the two dummy consumer add-ons, and running §7's CI contract on them.

The add-ons themselves live in ``tests/dummies/`` and are documented there. This
module is the machinery around them: how they get discovered without being
pip-installed, and how the two CI gates §7 requires of every consumer add-on are
reproduced against them.

----------------------------------------------------------------------------
Registering through ZCML, and why the scan is the real code path
----------------------------------------------------------------------------

Each dummy carries a ``configure.zcml`` with one ``<emailkit:templates>`` block,
exactly as a real consumer add-on does; nothing about the registration itself is
special-cased for the tests. What a real add-on gets for free is *execution*: it is
pip-installed, Zope's autoinclude finds its ZCML at startup and the directive runs.
These two live in another package's test tree, so :func:`installed` runs their ZCML
on purpose -- through ``imio.emailkit.scan.scan_package``, which is the code path
the build tooling already uses on a real consumer, over the same directive handler
and into the same registry as an instance start.

Nothing is monkeypatched and no private API is touched. The ZCML is committed,
readable and reviewable, which matters: these add-ons double as documentation and
the registration is half of what a reader came for.

----------------------------------------------------------------------------
Why installation is scoped to a fixture rather than global
----------------------------------------------------------------------------

Registering the dummies for the whole session would change what
``available_templates()`` answers for every other test in the suite --
``tests/test_golden.py`` drives its fixture-coverage check off discovery and would
start demanding ``tests/fixtures/convocation.py``. Scoping it also gives the gate
tests a *negative* control for free: outside the fixture the dummy templates must
not resolve.

:func:`installed` therefore adds the two registrations on the way in and removes
exactly those two on the way out -- see its docstring for why "remove what I added"
beats "put the whole registry back the way I found it" here, which is a measured
difference and not a taste. ``sys.path`` is handled separately, because the packages
also have to be *importable*: the scan resolves them by dotted name and their
fixtures are loaded from beside them.
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

#: The checkout's own Maizzle install. The dummies borrow it through a gitignored
#: ``node_modules`` symlink rather than running a second ``npm ci`` -- see
#: :func:`ensure_toolchain`.
CHECKOUT_NODE_MODULES = HERE.parent / "emails" / "node_modules"


@dataclass(frozen=True)
class DummyAddon:
    """One dummy consumer add-on, described the way §5's recipe describes a real
    one: ``(package, emails_dir, templates_dir)`` plus what it registers."""

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

#: Both of them, which is what SPEC §7 asks for: "discovery tests with two dummy
#: addons (also serving as living documentation)".
ADDONS = (MINIMAL, COMPLETE)


def all_qualified_names():
    return sorted(a.qualified(t) for a in ADDONS for t in a.templates)


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------


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


def _snapshot_of_the_dummies():
    """The registry entries belonging to the dummies, as ``(templates, dirs)``.

    Normally both are empty -- that is the invariant this module exists to keep --
    and they are non-empty only when ``installed()`` blocks are nested. The gate
    modules never do that (each calls ``installed()`` once per test, not one inside
    another); the only place nesting actually happens is the synthetic
    ``test_dummy_isolation.py::test_nested_installation_still_leaves_nothing``,
    which nests it on purpose to prove the un-nesting is exact either way.
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

    ``sys.path`` gains ``tests/dummies`` -- the packages have to be importable,
    since the scan resolves them by dotted name and their fixtures are loaded from
    beside them -- and the registration itself runs through
    ``imio.emailkit.scan``, i.e. the exact code path the build tooling uses on a
    real consumer.

    **Teardown removes the dummies rather than restoring a snapshot of the whole
    registry**, and that is not a stylistic choice. ``discovery.overlay()`` is the
    obvious seam and was the first implementation, but the Plone test layer loads
    ``imio.emailkit``'s ZCML *lazily*: the golden harness pulls its layer fixture
    in with ``request.getfixturevalue()``, so the layer's ``setUpZope`` can run
    **inside** this block -- measured: with the dummies' own suites first in the
    session, the registry is empty at every block entry, because the host's own
    templates are registered inside the block every time. Putting a snapshot back
    then deletes ``imio.emailkit:notification`` and ``imio.emailkit:get_username``
    on the way out, and the damage surfaces much later as a ``TemplateNotFound``
    in a module that never heard of the dummies.

    Subtracting exactly what was added has no such coupling to when anything else
    registers. The dummies' own prior entries are restored, so registry nesting
    behaves (the gate modules install per test *and* call this directly).

    That guarantee is narrower than it looks, and it covers the registry only.
    ``sys.path`` is cleared **unconditionally** in ``finally`` rather than
    restored to what it held on entry, so an inner ``installed()`` exiting
    would evict the path out from under a still-open outer block, if anything
    ever nested that way -- nothing in this module does. The one test that
    nests, ``test_nested_installation_still_leaves_nothing`` in
    ``test_dummy_isolation.py``, only asserts on the registry for exactly this
    reason.
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
    """Take them away again inside a block that has them installed.

    The negative control for every registration assertion: without it, "the dummy
    templates are found" could be true for a reason that has nothing to do with
    the registration.

    The mirror image of :func:`installed`, and subtractive for the same reason:
    only the dummies' entries are touched, so nothing else that registers while
    the block is open can be lost by putting a whole-registry snapshot back.

    Deliberately touches only the registry -- unlike :func:`installed`, there is
    no ``sys.path`` handling here. Its only job is to take a registration away
    again, not to make anything importable, so there is nothing on ``sys.path``
    for it to manage.
    """
    saved = _snapshot_of_the_dummies()
    _forget_the_dummies()
    try:
        yield
    finally:
        _restore(*saved)


# ---------------------------------------------------------------------------
# Gate 1 of §7's CI contract: build output is not stale
# ---------------------------------------------------------------------------
#
# SPEC §5's `bin/check-emails` is the shipped implementation of this gate and lives
# in `imio.recipe.emailkit`. It cannot be pointed at these dummies: it resolves
# packages from the buildout working set, and a package directory dropped on
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
