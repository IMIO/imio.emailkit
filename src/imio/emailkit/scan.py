"""Execute a package's ZCML with only the emailkit directives live.

The build tooling (the buildout recipe's generated scripts, the preview server)
needs to know what a consumer package registers without booting a Zope
instance. Parsing the ZCML by hand would mean re-implementing includes,
conditions and overrides; loading it for real would mean importing every
directive handler in Plone. This module does neither: it runs the real
``zope.configuration`` machinery through a :class:`ConfigurationMachine`
subclass whose unknown-directive answer is "swallow it" instead of "crash".

Only ``imio.emailkit``'s ``meta.zcml`` is loaded, so ``emailkit:*`` executes
for real -- through the same handler, into the same registry, as at instance
startup -- while ``browser:page`` and friends are ignored *without their
handlers or classes ever being imported* (an unknown directive never resolves
its schema or handler; only ``<include package>`` imports anything, namely the
included package itself, to locate its files).

Includes are scoped to the scanned package: every egg is scanned from its own
roots, so following ``<include package="some.other.addon">`` would only
double-count. Skipping such an include still imports the foreign package --
``<include>``'s ``package`` field is a ``GlobalObject``, resolved before the
scoped handler ever sees it, so the package's ``__init__`` runs; what is
skipped is the execution of its ZCML. Known divergence from a full instance,
accepted and documented: feature flags (``zcml:condition="have plone-x"``)
read false here, because nothing loads the ZCML that provides features.
"""

from imio.emailkit import discovery  # noqa: F401  (re-exported for callers)
from importlib import import_module
from pathlib import Path
from zope.configuration import xmlconfig
from zope.configuration.config import ConfigurationMachine
from zope.configuration.config import defineSimpleDirective
from zope.configuration.exceptions import ConfigurationError

import imio.emailkit
import logging


logger = logging.getLogger("imio.emailkit.scan")

#: The namespace our directives live in -- the authoritative URI, used to tell
#: "the consumer meant us" from "some other addon's directive" when a directive
#: does not resolve.
NAMESPACE = "http://namespaces.imio.be/emailkit"

#: Substring that marks a ZCML file as (possibly) carrying emailkit directives:
#: the cheap textual pre-filter the build tooling runs before spending a real
#: scan. Deliberately a substring of NAMESPACE and not NAMESPACE itself -- this
#: one only has to be a grep, the parser matches on the URI above.
MARKER = "namespaces.imio.be/emailkit"


class _Swallowed:
    """Stack item standing in for a directive whose meta is not loaded.

    Accepts arbitrary nested directives -- so a grouping directive swallows its
    whole subtree -- and emits no configuration actions. The machine also parks
    the current parser position on every stack item's ``context``; real items
    carry a context decorator, this one is its own, since nothing will ever
    read that position back out.
    """

    info = ""

    def __init__(self):
        self.context = self

    def contained(self, name, data, info):
        return self

    def finish(self):
        pass


def _swallow(context, data, info):
    return _Swallowed()


class PermissiveConfigurationMachine(ConfigurationMachine):
    """A configuration machine that ignores what it does not know.

    Ignorance stops at our own namespace: an ``emailkit:`` directive that does
    not resolve is a consumer mistake, and swallowing it would hand the build
    an empty registry that only blows up at the next instance start.
    """

    def __init__(self):
        super().__init__()
        # A false ``zcml:condition`` on a scanned file's *root* element makes
        # the parser ignore the whole subtree without ever pushing an info
        # object, so the character data that follows lands on the machine's own
        # ``info`` -- class default ``''``, which has no ``characters()``.
        # Instances never notice: their files arrive through an ``<include>``
        # whose context already carries a ParserInfo. Ours arrive on the bare
        # machine, so seed one.
        self.info = xmlconfig.ParserInfo("<scan>", 0, 0)

    def factory(self, context, name):
        try:
            return super().factory(context, name)
        except ConfigurationError:
            if name[0] == NAMESPACE:
                # The consumer meant us: a typo, or a subdirective used outside
                # its block. An instance would refuse this too, so do the same.
                raise
            logger.debug("Swallowing unknown directive %s", name)
            return _swallow


def scan_package(package):
    """Register the emailkit templates ``package``'s ZCML declares.

    Executes ``configure.zcml`` and then ``overrides.zcml`` (each only when
    present) from the package root -- the same two roots Zope's autoinclude
    loads -- and runs the resulting actions against the discovery registry.

    :param package: a dotted name or an imported package.
    :raises zope.configuration errors: a genuinely broken emailkit directive
        (bad attribute, duplicate name) raises exactly as it would at instance
        startup; the *caller* decides whether that stops a build.
    """
    if isinstance(package, str):
        package = import_module(package)
    machine = PermissiveConfigurationMachine()
    xmlconfig.registerCommonDirectives(machine)
    xmlconfig.include(machine, file="meta.zcml", package=imio.emailkit)
    _scope_includes(machine, package.__name__)
    package_dir = Path(package.__file__).parent
    if (package_dir / "configure.zcml").is_file():
        xmlconfig.include(machine, file="configure.zcml", package=package)
    if (package_dir / "overrides.zcml").is_file():
        xmlconfig.includeOverrides(machine, file="overrides.zcml", package=package)
    machine.execute_actions()


def _scope_includes(machine, root):
    """Confine ``<include>``/``<includeOverrides>`` to ``root``'s namespace.

    ``<include file=...>`` (package=None) always passes: it stays inside the
    package by construction. ``<include package=...>`` of anything outside
    ``root`` is dropped -- that package gets its own scan from its own roots.
    Dropped means "its ZCML is not executed", not "it is not imported": the
    ``package`` field is a ``GlobalObject``, so ``zope.configuration`` has
    already imported the foreign package by the time this handler runs.
    """

    def scoped(handler):
        def scoped_handler(_context, file=None, package=None, files=None):
            if package is not None:
                name = package.__name__
                if name != root and not name.startswith(root + "."):
                    logger.info(
                        "Skipping <include package=%r> while scanning %s",
                        name,
                        root,
                    )
                    return
            handler(_context, file=file, package=package, files=files)

        return scoped_handler

    defineSimpleDirective(
        machine,
        "include",
        xmlconfig.IInclude,
        scoped(xmlconfig.include),
        namespace="*",
    )
    defineSimpleDirective(
        machine,
        "includeOverrides",
        xmlconfig.IInclude,
        scoped(xmlconfig.includeOverrides),
        namespace="*",
    )


def has_marker(package_dir):
    """Cheap pre-filter: does any ZCML under ``package_dir`` mention us?"""
    for zcml in Path(package_dir).rglob("*.zcml"):
        try:
            if MARKER in zcml.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False
