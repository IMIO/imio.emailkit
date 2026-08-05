"""Which packages ship email templates, and where their directories are.

SPEC §5 step 1: "Resolves all eggs, collects distributions whose ZCML registers
``<emailkit:templates>``, and records ``(package, emails_dir, templates_dir)``
tuples. It also resolves the kit directory from the ``imio.emailkit`` egg."

Two collectors, because the recipe runs in **two different interpreters**:

* :func:`from_working_set` runs inside *buildout*, whose ``sys.path`` does not
  contain the eggs. It therefore greps each dist's ZCML for the emailkit marker
  on disk and **imports nothing** -- not the consumer's code, not
  ``imio.emailkit``, not Plone, not even ``zope.configuration``. That is
  deliberate: a buildout run must stay a buildout run.
* :func:`from_environment` runs inside the *generated scripts*, whose
  ``sys.path`` is exactly the part's ``eggs``. It can therefore run the real
  permissive scan (``imio.emailkit.scan.scan_package``) and honour whatever the
  directive actually resolved -- non-default ``directory``, conditions,
  overrides -- instead of pattern-matching.

Both funnel into :func:`make_project`, so "where does the build write" has one
answer.
"""

from dataclasses import dataclass
from pathlib import Path

import logging
import os


logger = logging.getLogger("imio.recipe.emailkit")

#: Substring that marks a ZCML file as carrying emailkit directives. Duplicated
#: from ``imio.emailkit.scan.MARKER`` on purpose: this module runs inside
#: buildout, where importing imio.emailkit would pull the Plone runtime into
#: the build system. ``tests/test_projects.py::test_marker_matches_the_runtime``
#: fails if the two ever drift.
MARKER = "namespaces.imio.be/emailkit"

#: Directories never worth descending into while looking for ZCML.
PRUNE_DIRS = {"node_modules", "__pycache__", ".git", "emails"}

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

    #: The §4 namespace, i.e. the package's own dotted name (the ZCML
    #: registration's namespace, per ``iter_marker_packages``).
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

    :param package: the §4 namespace (the ZCML registration's dotted name)
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
# Collector 1: inside buildout (filesystem marker scan, no imports)
# ---------------------------------------------------------------------------


def iter_marker_packages(dist, cache=None):
    """``(dotted_name, package_dir)`` for each package of ``dist`` whose ZCML
    mentions the emailkit namespace.

    Filesystem-only, import-free: safe inside buildout. The dotted name is the
    path of the directory holding the marked ZCML file, relative to the
    ``sys.path`` root -- which is exactly the namespace the directive gives its
    templates at runtime (the package the ZCML file belongs to).

    ``cache``, when given, memoizes the walk of a top-level directory across
    every dist of one collection call, keyed by its resolved path. This is
    what actually keeps a shared namespace directory from being rglobbed once
    per distribution that declares it: restricting the walk to the dist's own
    top-level names (:func:`_top_level_names`) does not help when several
    dists share the same top-level name, which every ``imio.*`` dist's
    ``top_level.txt`` does (PEP 420). :func:`from_working_set` and
    :func:`from_environment` each build one dict and pass it through their
    whole loop; leave it ``None`` when scanning a single dist in isolation.
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
    """The ``rglob`` walk of one top-level package directory, memoized by its
    caller (:func:`iter_marker_packages`'s ``cache``).

    Split out on purpose: the cache has to hold the actual list of matches,
    not the generator that used to produce them, or a second consumer of the
    same cache entry would find the generator already exhausted.
    """
    root = top_dir.parent
    found = []
    for zcml in sorted(top_dir.rglob("*.zcml")):
        # Relative to `top_dir`, not absolute. An absolute `zcml.parts` also
        # matches a PRUNE_DIRS name carried by an *ancestor* of the checkout
        # -- a clone under `~/work/emails/dist/...`, say -- which would hide
        # the whole distribution for a reason that has nothing to do with its
        # own layout.
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
    """The distribution's top-level package names, from metadata when it has
    any, from the filesystem when it does not (develop eggs, mainly).

    Restricting the walk to the dist's own top-level packages keeps an
    unrelated sibling directory out of the rglob; it does *not*, by itself,
    stop a *shared* top-level directory from being walked once per
    distribution that declares it -- every ``imio.*`` dist's ``top_level.txt``
    names the same ``imio`` (PEP 420 namespace packages share it by design).
    :func:`iter_marker_packages`'s ``cache`` is what collapses that back down
    to one walk per directory.

    The filesystem fallback below cannot see a namespace package's top-level
    name: a PEP 420 namespace has no ``__init__.py``, so it would never match
    the ``(p / "__init__.py").is_file()`` check. Accepted rather than worked
    around -- the fallback only exists for a develop egg with no metadata at
    all, and every real installer, ``pip install -e`` included, writes
    ``top_level.txt`` even for a namespace package.
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

    Imports nothing, executes nothing -- a buildout run stays a buildout run.
    The directive's ``directory`` attribute is therefore *not* read;
    :data:`DEFAULT_DIRECTORY` is assumed, which is what the spec's example and
    every registration in this repository use. The generated scripts resolve it
    for real (:func:`from_environment`), so a package that overrides it still
    builds correctly -- only buildout's log line would name the default.
    """
    resolved = {}
    cache = {}
    for dist in sorted(working_set, key=str):
        for dotted, package_dir in iter_marker_packages(dist, cache):
            resolved.setdefault(dotted, make_project(dotted, package_dir))
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
    """Collect the projects visible from ``sys.path``, resolved for real.

    Used by the generated scripts, which run with the part's ``eggs`` on their
    path -- so ``imio.emailkit`` is importable and each candidate's ZCML is
    *executed* (permissively) rather than pattern-matched: the ``directory``
    attribute, includes, conditions and overrides all behave exactly as at
    instance startup. Side effect, relied on by ``preview-emails``: the
    discovery registry is populated.
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
            # The whole body -- scan, re-derive, append -- is guarded together:
            # an unexpected failure anywhere in it should skip this one
            # package, not abort the collection for every package after it.
            try:
                scan.scan_package(dotted)
                # The marker walk's `package_dir` is a filesystem guess: the
                # directory holding the marked ZCML file. `scan_package` just
                # imported `dotted` for real, and that import can resolve to a
                # *different* directory -- a develop egg shadowing an
                # installed copy on `sys.path`, say. Re-derive from the module
                # Python actually imported: that is the truth the scan just
                # executed against, not the guess.
                package_dir = Path(import_module(dotted).__file__).parent
                templates_dir = discovery.registered_directories().get(dotted)
                if templates_dir is None:
                    # Marker present but no block survived (all conditioned
                    # away, say). Nothing to build.
                    continue
                # `os.path.relpath`, not `Path.relative_to`: a subpackage's
                # `directory="../templates"` is legal (`zcml.py`'s own
                # docstring says a block may point at its parent's files) and
                # produces a `templates_dir` that is a *sibling* of
                # `package_dir`, not a descendant -- `relative_to` cannot
                # express that `..` and raises, `relpath` can, and
                # `make_project` resolves it right back
                # (`(package_dir / directory).resolve()`).
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
