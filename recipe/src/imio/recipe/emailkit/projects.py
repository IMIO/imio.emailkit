"""Which packages ship email templates, and where their directories are.

Resolves all eggs, collects distributions whose ZCML registers
``<emailkit:templates>``, and records the package, emails directory, and
templates directory for each.

Two collectors, since the recipe runs in two different interpreters:

* :func:`from_working_set` runs inside buildout, whose ``sys.path`` has
  no eggs on it. It greps each dist's ZCML for the emailkit marker on
  disk and imports nothing.
* :func:`from_environment` runs inside the generated scripts, with the
  part's ``eggs`` on ``sys.path``. It runs the real scan
  (``imio.emailkit.scan.scan_package``).

Both funnel into :func:`make_project`.
"""

from dataclasses import dataclass
from pathlib import Path

import logging
import os


logger = logging.getLogger("imio.recipe.emailkit")

#: Substring that marks a ZCML file as carrying emailkit directives.
#: Duplicated from ``imio.emailkit.scan.MARKER`` to avoid importing it.
MARKER = "namespaces.imio.be/emailkit"

#: Directories never worth descending into while looking for ZCML.
PRUNE_DIRS = {"node_modules", "__pycache__", ".git", "emails"}

#: The ``directory`` key of a registration, when the addon omits it.
DEFAULT_DIRECTORY = "templates"

#: Name of the Maizzle project directory inside a consumer addon.
EMAILS_DIRNAME = "emails"

#: A Maizzle project needs one of these configs. Requiring one keeps an
#: unrelated ``emails/`` directory from being mistaken for a build root.
MAIZZLE_CONFIGS = (
    "maizzle.config.js",
    "maizzle.config.ts",
    "maizzle.config.mjs",
)

#: Hand-authored plaintext twins live here. ``maizzle build`` empties its
#: output directory, so twins are copied back in after every build.
TWINS_DIRNAME = "twins"

#: How far above the package directory to look for the Maizzle project.
#: ``emails/`` is usually inside the package; ``imio.emailkit`` puts it
#: at the repository root instead.
MAX_ASCENT = 5


class ProjectError(Exception):
    """A package that ships templates is not laid out in a usable way."""


@dataclass(frozen=True)
class Project:
    """One package that ships email templates, resolved on disk."""

    #: The package's dotted name (the ZCML registration's namespace).
    package: str
    #: The importable package's own directory.
    package_dir: Path
    #: The committed build output. Always set; it may not exist yet.
    templates_dir: Path
    #: The Maizzle project, or ``None`` when this distribution ships no
    #: sources. An installed egg prunes ``emails/``, so ``None`` is normal.
    emails_dir: Path | None

    @property
    def root(self):
        """The directory that holds ``emails/`` -- the checkout root, usually."""
        return None if self.emails_dir is None else self.emails_dir.parent

    @property
    def sources_dir(self):
        """``emails/src/templates`` -- where the ``.vue`` sources live."""
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
        """Where ``fixtures/`` and ``golden/`` live for this package.

        ``<root>/tests`` when the checkout keeps its suite at the top
        level, otherwise ``<package_dir>/tests``.
        """
        if self.root is not None and (self.root / "tests").is_dir():
            return self.root / "tests"
        return self.package_dir / "tests"

    @property
    def kit_dir(self):
        """This package's own kit, if it ships one. Only ``imio.emailkit`` does."""
        candidate = self.package_dir / "kit"
        return candidate if candidate.is_dir() else None

    def vue_sources(self):
        """Every ``.vue`` source this package owns, sorted.

        The authored templates, plus the kit's own layouts and
        components for the package that ships the design system.
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

    :param package: the namespace (the ZCML registration's dotted name)
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

    Searches the package directory and its ancestors, up to
    :data:`MAX_ASCENT` levels. A directory only counts when it holds a
    Maizzle config, so an unrelated ``emails/`` is never mistaken for a
    build root.
    """
    package_dir = Path(package_dir)
    candidates = [package_dir, *list(package_dir.parents)[:MAX_ASCENT]]
    for base in candidates:
        candidate = base / EMAILS_DIRNAME
        if any((candidate / name).is_file() for name in MAIZZLE_CONFIGS):
            return candidate.resolve()
    return None


# ---------------------------------------------------------------------------
# Collector 1: inside buildout (filesystem marker scan, no imports)
# ---------------------------------------------------------------------------


def iter_marker_packages(dist, cache=None):
    """``(dotted_name, package_dir)`` for each package of ``dist`` whose ZCML
    mentions the emailkit namespace.

    Filesystem-only, import-free: safe inside buildout.

    ``cache``, when given, memoizes the walk of a top-level directory
    across every dist of one call. This keeps a shared namespace
    directory (every ``imio.*`` dist's ``top_level.txt`` names the same
    ``imio``, per PEP 420) from being scanned once per distribution.
    Leave it ``None`` for a single dist.
    """
    if cache is None:
        cache = {}
    location = Path(getattr(dist, "location", "") or "")
    for root in (location, location / "src"):
        if not root.is_dir():
            continue
        for top in _top_level_names(dist, root):
            top_dir = root / top
            if not top_dir.is_dir():
                continue
            key = top_dir.resolve()
            if key not in cache:
                cache[key] = _scan_top_dir(top_dir)
            yield from cache[key]


def _scan_top_dir(top_dir):
    """The ``rglob`` walk of one top-level package directory, memoized by
    :func:`iter_marker_packages`'s ``cache``.

    Returns a list, not a generator, so a second consumer of the same
    cache entry never finds it exhausted.
    """
    root = top_dir.parent
    found = []
    for zcml in sorted(top_dir.rglob("*.zcml")):
        # Relative to `top_dir`, not absolute. An absolute path could match
        # a PRUNE_DIRS name in an ancestor of the checkout and hide the
        # whole distribution for an unrelated reason.
        if PRUNE_DIRS.intersection(zcml.relative_to(top_dir).parts):
            continue
        try:
            text = zcml.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if MARKER not in text:
            continue
        package_dir = zcml.parent
        if not (package_dir / "__init__.py").is_file():
            logger.warning(
                "%s mentions the emailkit namespace but %s is not a "
                "package directory; skipping it.",
                zcml,
                package_dir,
            )
            continue
        found.append((".".join(package_dir.relative_to(root).parts), package_dir))
    return found


def _top_level_names(dist, root):
    """The distribution's top-level package names.

    Read from metadata when there is any, from the filesystem otherwise
    (a develop egg with no metadata). The filesystem fallback cannot find a
    PEP 420 namespace package, because it has no ``__init__.py``.
    """
    try:
        names = [line for line in dist.get_metadata_lines("top_level.txt") if line]
    except (OSError, AttributeError):
        names = []
    if names:
        return names
    return sorted(
        p.name for p in root.iterdir() if p.is_dir() and (p / "__init__.py").is_file()
    )


def from_working_set(working_set):
    """Collect the projects of every dist whose ZCML carries the marker.

    Imports nothing. The directive's ``directory`` attribute is not read;
    :data:`DEFAULT_DIRECTORY` is assumed instead, resolved for real later
    by :func:`from_environment`.
    """
    resolved = {}
    cache = {}
    for dist in sorted(working_set, key=str):
        for dotted, package_dir in iter_marker_packages(dist, cache):
            resolved.setdefault(dotted, make_project(dotted, package_dir))
    return [resolved[name] for name in sorted(resolved)]


def locate_package(dist, module_name):
    """Find ``module_name``'s directory under ``dist``'s location, or ``None``.

    A ``src/`` layout develop egg needs a second guess: ``location`` can
    be the project root instead of its ``src`` directory.
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
    """Resolve the built-in design kit's directory from the eggs.

    Raises rather than returning ``None``: buildout is the right place
    to say a script cannot work without a kit to compile against.
    """
    for candidate in working_set:
        # Normalised: `project_name` can read `imio.emailkit` or
        # `imio-emailkit` depending on which metadata generation wrote it.
        if candidate.project_name.replace("-", ".").lower() == package.lower():
            package_dir = locate_package(candidate, package)
            if package_dir is not None:
                return _kit_dir(package_dir, package)
    raise ProjectError(
        f"{package} is not in this part's working set, so the design kit "
        f"cannot be resolved. Add it to the part's `eggs` option -- "
        f"`eggs = ${{instance:eggs}}` normally does it."
    )


def _kit_dir(package_dir, package):
    kit = (Path(package_dir) / "kit").resolve()
    if not kit.is_dir():
        raise ProjectError(
            f"{package} is installed at {package_dir} but ships no `kit/` "
            f"directory. The design system lives inside the egg; an "
            f"install without it cannot compile anything."
        )
    return kit


# ---------------------------------------------------------------------------
# Collector 2: inside the generated scripts (real imports, real `directory`)
# ---------------------------------------------------------------------------


def from_environment():
    """Collect the projects visible from ``sys.path``, resolved for real.

    Used by the generated scripts, so ``imio.emailkit`` is importable and
    each candidate's ZCML is executed rather than pattern-matched. As a
    side effect, this populates the discovery registry, relied on by
    ``preview-emails``.
    """
    from imio.emailkit import discovery
    from imio.emailkit import scan
    from importlib import import_module

    import pkg_resources

    projects = []
    seen = set()
    cache = {}
    for dist in sorted(pkg_resources.working_set, key=str):
        for dotted, package_dir in iter_marker_packages(dist, cache):
            if dotted in seen:
                continue
            seen.add(dotted)
            # A failure here skips only this package, not the rest.
            try:
                scan.scan_package(dotted)
                # Re-derive from the module Python actually imported,
                # since a develop egg can shadow an installed copy.
                package_dir = Path(import_module(dotted).__file__).parent
                templates_dir = discovery.registered_directories().get(dotted)
                if templates_dir is None:
                    # Marker present but no block survived. Nothing to build.
                    continue
                # `relpath`, not `relative_to`: `directory="../templates"`
                # is legal and makes `templates_dir` a sibling, not a
                # descendant, of `package_dir`.
                directory = os.path.relpath(templates_dir, package_dir)
                projects.append(make_project(dotted, package_dir, directory))
            except Exception as exc:
                logger.warning(
                    "Could not scan the emailkit registration of %r (%s: %s); "
                    "skipping it.",
                    dotted,
                    type(exc).__name__,
                    exc,
                )
                continue
    return projects


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

    Fails loud on an unknown name and lists what there was, so a
    ``--package`` typo cannot look like a successful build.
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
