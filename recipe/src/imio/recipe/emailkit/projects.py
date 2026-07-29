"""Which packages ship email templates, and where their directories are.

SPEC §5 step 1: "Resolves all eggs, collects distributions exposing the
``imio.emailkit.templates`` entry point, and records ``(package, emails_dir,
templates_dir)`` tuples. It also resolves the kit directory from the
``imio.emailkit`` egg."

Two collectors, because the recipe runs in **two different interpreters**:

* :func:`from_working_set` runs inside *buildout*, whose ``sys.path`` does not
  contain the eggs. It therefore resolves everything off ``pkg_resources``
  metadata and the filesystem and **imports nothing** -- not the consumer's
  code, not ``imio.emailkit``, not Plone. That is deliberate: a buildout run must
  stay a buildout run.
* :func:`from_environment` runs inside the *generated scripts*, whose
  ``sys.path`` is exactly the part's ``eggs``. It can therefore import the
  registration module and honour a non-default ``directory`` key.

Both funnel into :func:`make_project`, so "where does the build write" has one
answer.
"""

from dataclasses import dataclass
from pathlib import Path

import logging


logger = logging.getLogger("imio.recipe.emailkit")

#: SPEC §4's entry-point group. Declared here rather than imported from
#: ``imio.emailkit.discovery`` on purpose: importing it would pull the Plone
#: runtime into a build-time tool, and into *buildout itself*. The string is a
#: spec constant, not an implementation detail -- and
#: ``tests/test_projects.py::test_entry_point_group_matches_the_runtime`` fails
#: if the two ever drift.
ENTRY_POINT_GROUP = "imio.emailkit.templates"

#: The ``directory`` key of a §4 registration, when the addon omits it.
DEFAULT_DIRECTORY = "templates"

#: Name of the Maizzle project directory inside a consumer addon (§4).
EMAILS_DIRNAME = "emails"

#: A Maizzle project is only a Maizzle project if it has a config. Requiring one
#: keeps an unrelated ``emails/`` directory from being mistaken for a build root.
MAIZZLE_CONFIGS = (
    "maizzle.config.js",
    "maizzle.config.ts",
    "maizzle.config.mjs",
)

#: Hand-authored plaintext twins live here and are copied into the templates
#: directory after every build. This is not decoration: ``maizzle build`` empties
#: its own output directory silently and Maizzle 6 exposes no option to stop it,
#: so a twin committed beside the compiled output gets deleted (recorded in
#: ``docs/DECISIONS.md``). Every consumer addon inherits the same hazard, so the
#: convention is generalised here rather than left in one Makefile.
TWINS_DIRNAME = "twins"

#: How far above the package directory to look for the Maizzle project. §4 puts
#: ``emails/`` *inside* the package; ``imio.emailkit`` itself puts it at the
#: repository root, four levels up from ``src/imio/emailkit``. Both are found.
MAX_ASCENT = 5


class ProjectError(Exception):
    """A package that ships templates is not laid out in a usable way."""


@dataclass(frozen=True)
class Project:
    """One package that ships email templates, resolved on disk.

    SPEC §5's ``(package, emails_dir, templates_dir)`` tuple, plus the two paths
    every consumer of it immediately needs.
    """

    #: The §4 namespace, i.e. the entry-point name.
    package: str
    #: The importable package's own directory.
    package_dir: Path
    #: The committed build output (``<package_dir>/<directory>``). Always set --
    #: it is where the build writes, so it may legitimately not exist yet.
    templates_dir: Path
    #: The Maizzle project, or ``None`` when this distribution ships no sources.
    #: An installed egg prunes ``emails/`` (§4's ``MANIFEST.in``), so ``None`` is
    #: the *normal* answer in production and means "nothing to compile here",
    #: never "something is broken".
    emails_dir: Path | None

    @property
    def root(self):
        """The directory that holds ``emails/`` -- the checkout root, usually."""
        return None if self.emails_dir is None else self.emails_dir.parent

    @property
    def sources_dir(self):
        """``emails/src/templates`` -- where the ``.vue`` sources live (§4)."""
        if self.emails_dir is None:
            return None
        return self.emails_dir / "src" / "templates"

    @property
    def twins_dir(self):
        """``emails/twins`` -- hand-authored ``.txt.pt`` sources."""
        return None if self.emails_dir is None else self.emails_dir / TWINS_DIRNAME

    @property
    def compilable(self):
        return self.emails_dir is not None

    @property
    def tests_dir(self):
        """Where §7's ``fixtures/`` and ``golden/`` live for this package.

        ``<root>/tests`` when the checkout keeps its suite at the top level (the
        Cookieplone layout ``imio.emailkit`` uses), otherwise
        ``<package_dir>/tests``. Resolved rather than configured because §7 shows
        the directory without saying which of the two roots it hangs off.
        """
        if self.root is not None and (self.root / "tests").is_dir():
            return self.root / "tests"
        return self.package_dir / "tests"

    @property
    def kit_dir(self):
        """This package's *own* kit, if it ships one. Only ``imio.emailkit`` does.

        Returned so the authoring lint covers the kit's layout and components when
        ``imio.emailkit`` checks itself, and covers nothing extra for a consumer --
        whose installed copy of the kit is not its code to fix.
        """
        candidate = self.package_dir / "kit"
        return candidate if candidate.is_dir() else None

    def vue_sources(self):
        """Every ``.vue`` source this package **owns**, sorted.

        The authored templates under ``emails/src/templates`` plus, for the package
        that ships the design system, the kit's own layouts and components. Empty
        for an installed egg with no sources, which is the normal production case.
        """
        sources = []
        if self.sources_dir is not None and self.sources_dir.is_dir():
            sources.extend(self.sources_dir.rglob("*.vue"))
        if self.kit_dir is not None:
            sources.extend(self.kit_dir.rglob("*.vue"))
        return sorted(sources)

    def describe(self):
        return (
            f"{self.package}: templates={self.templates_dir} "
            f"emails={self.emails_dir or '(not shipped)'}"
        )


def make_project(package, package_dir, directory=None):
    """Build a :class:`Project` from a package directory.

    :param package: the §4 namespace (the entry-point name)
    :param package_dir: the importable package's directory
    :param directory: the registration's ``directory`` key; ``None`` means the
        caller could not read it and :data:`DEFAULT_DIRECTORY` is used
    """
    package_dir = Path(package_dir).resolve()
    templates_dir = (package_dir / (directory or DEFAULT_DIRECTORY)).resolve()
    return Project(
        package=package,
        package_dir=package_dir,
        templates_dir=templates_dir,
        emails_dir=find_emails_dir(package_dir),
    )


def find_emails_dir(package_dir):
    """Locate the Maizzle project belonging to ``package_dir``, or ``None``.

    §4 draws ``emails/`` as a sibling of ``templates/`` *inside* the package.
    ``imio.emailkit`` itself keeps it at the repository root instead, because its
    Maizzle project also emits the §8 jbot overrides, which live elsewhere in the
    tree. Both layouts are legitimate, so both are searched: the package
    directory first, then each ancestor up to :data:`MAX_ASCENT` levels.

    A directory only counts when it holds a Maizzle config. Without that check an
    unrelated ``emails/`` -- a content-type folder, say -- would be picked up and
    the build would fail somewhere much less obvious.
    """
    package_dir = Path(package_dir)
    candidates = [package_dir, *list(package_dir.parents)[:MAX_ASCENT]]
    for base in candidates:
        candidate = base / EMAILS_DIRNAME
        if any((candidate / name).is_file() for name in MAIZZLE_CONFIGS):
            return candidate.resolve()
    return None


# ---------------------------------------------------------------------------
# Collector 1: inside buildout (pkg_resources metadata, no imports)
# ---------------------------------------------------------------------------


def from_working_set(working_set):
    """Collect the projects of every dist in ``working_set`` that registers.

    Imports nothing. The registration's ``directory`` key is therefore *not*
    read; :data:`DEFAULT_DIRECTORY` is assumed, which is what §4's own example
    and every registration in this repository use. The generated scripts resolve
    it for real (:func:`from_environment`), so a package that overrides it still
    builds correctly -- only buildout's log line would name the default.
    """
    resolved = {}
    unresolved = {}
    for entry_point in sorted(
        working_set.iter_entry_points(ENTRY_POINT_GROUP),
        key=lambda ep: ep.name,
    ):
        if entry_point.name in resolved:
            continue
        package_dir = locate_package(entry_point.dist, entry_point.module_name)
        if package_dir is None:
            # Two distributions can legitimately answer for one name -- a develop
            # egg shadowing an installed copy is the everyday case -- and only one
            # of them has the files. Remember the failure and complain only if no
            # candidate works out, so a shadowed install is silent and a genuinely
            # broken registration is not.
            unresolved.setdefault(entry_point.name, entry_point)
            continue
        resolved[entry_point.name] = make_project(entry_point.name, package_dir)

    for name, entry_point in sorted(unresolved.items()):
        if name in resolved:
            continue
        logger.warning(
            "%r registers %s but its module %r could not be located under %s; "
            "skipping it.",
            name,
            ENTRY_POINT_GROUP,
            entry_point.module_name,
            getattr(entry_point.dist, "location", "?"),
        )
    return [resolved[name] for name in sorted(resolved)]


def locate_package(dist, module_name):
    """Find ``module_name``'s directory under ``dist``'s location, or ``None``.

    ``dist.location`` is the directory that goes on ``sys.path``, so the module
    normally hangs straight off it. A ``src/`` layout develop egg is the one case
    that needs a second guess: depending on how the egg-link was written,
    ``location`` can be the project root rather than its ``src``.
    """
    if dist is None:
        return None
    parts = module_name.split(".")
    location = Path(getattr(dist, "location", "") or "")
    for base in (location, location / "src"):
        candidate = base.joinpath(*parts)
        if candidate.is_dir():
            return candidate
    return None


def kit_dir_from_working_set(working_set, package="imio.emailkit"):
    """Resolve the built-in design kit's directory (SPEC §3) from the eggs.

    Raises rather than returning ``None``: a part that generates
    ``bin/compile-emails`` without a kit to compile against generates a script
    that cannot work, and buildout is the right place to say so.
    """
    for candidate in working_set:
        # Compared through a normalisation because a distribution's
        # `project_name` reaches us as `imio.emailkit` or `imio-emailkit`
        # depending on which metadata generation wrote it.
        if candidate.project_name.replace("-", ".").lower() == package.lower():
            package_dir = locate_package(candidate, package)
            if package_dir is not None:
                return _kit_dir(package_dir, package)
    raise ProjectError(
        f"{package} is not in this part's working set, so the design kit "
        f"(SPEC §3) cannot be resolved. Add it to the part's `eggs` option -- "
        f"`eggs = ${{instance:eggs}}` normally does it."
    )


def _kit_dir(package_dir, package):
    kit = (Path(package_dir) / "kit").resolve()
    if not kit.is_dir():
        raise ProjectError(
            f"{package} is installed at {package_dir} but ships no `kit/` "
            f"directory. SPEC §3 keeps the design system inside the egg; an "
            f"install without it cannot compile anything."
        )
    return kit


# ---------------------------------------------------------------------------
# Collector 2: inside the generated scripts (real imports, real `directory`)
# ---------------------------------------------------------------------------


def from_environment():
    """Collect the projects of every registration importable from ``sys.path``.

    Used by the generated scripts, which run with the part's ``eggs`` on their
    path. Here the registration module *is* importable, so the ``directory`` key
    is honoured.
    """
    from importlib.metadata import entry_points

    projects = []
    for entry_point in sorted(
        entry_points(group=ENTRY_POINT_GROUP), key=lambda ep: ep.name
    ):
        try:
            package_dir, directory = _resolve_by_import(entry_point)
        except Exception as exc:
            logger.warning(
                "Could not resolve the %s registration of %r (%s: %s); skipping it.",
                ENTRY_POINT_GROUP,
                entry_point.name,
                type(exc).__name__,
                exc,
            )
            continue
        projects.append(make_project(entry_point.name, package_dir, directory))
    return projects


def _resolve_by_import(entry_point):
    """``(package_dir, directory)`` for one entry point, by importing it.

    Mirrors ``imio.emailkit.discovery._resolve_directory``: the directory is
    relative to the module the entry point *points at*, while the namespace is
    the entry-point *name*.
    """
    from importlib import import_module

    module = import_module(entry_point.module)
    package_dir = Path(module.__file__).parent
    registration = module
    for attribute in entry_point.attr.split("."):
        registration = getattr(registration, attribute)
    directory = None
    if isinstance(registration, dict):
        directory = registration.get("directory")
    return package_dir, directory


def kit_dir_from_environment(package="imio.emailkit"):
    """Resolve the kit directory by importing ``imio.emailkit``."""
    from importlib import import_module

    module = import_module(package)
    return _kit_dir(Path(module.__file__).parent, package)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def select(projects, package=None):
    """Return the projects ``--package`` asks for, or all of them.

    Fails loud on an unknown name, listing what there was: a ``--package`` typo
    that silently compiled nothing would look exactly like a successful build.
    """
    if package is None:
        return list(projects)
    chosen = [project for project in projects if project.package == package]
    if not chosen:
        known = ", ".join(sorted(project.package for project in projects)) or "(none)"
        raise ProjectError(
            f"No package named {package!r} ships email templates. Registered: {known}."
        )
    return chosen
