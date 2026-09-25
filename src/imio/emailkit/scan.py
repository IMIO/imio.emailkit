"""Execute a package's ZCML with only the emailkit directives live.

The build tooling needs to know what a consumer package registers,
without booting a Zope instance. It runs the real ``zope.configuration``
machinery through a :class:`ConfigurationMachine` subclass that
swallows unknown directives instead of crashing.

Includes are scoped to the scanned package: an included package is
still imported, but its ZCML does not execute. Known divergence: a
``zcml:condition="have plone-x"`` feature flag always reads false here.
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

#: The namespace our directives live in.
NAMESPACE = "http://namespaces.imio.be/emailkit"

#: Substring marking a ZCML file as possibly carrying emailkit directives.
MARKER = "namespaces.imio.be/emailkit"


class _Swallowed:
    """Stack item for a directive whose meta is not loaded; swallows its subtree."""

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

    Except our own namespace: an unresolved ``emailkit:`` directive is a
    consumer mistake.
    """

    def __init__(self):
        super().__init__()
        # A false root-element `zcml:condition` leaves character data on
        # the machine's own `info`, which has no `characters()` method.
        # A real instance never hits this.
        self.info = xmlconfig.ParserInfo("<scan>", 0, 0)

    def factory(self, context, name):
        try:
            return super().factory(context, name)
        except ConfigurationError:
            if name[0] == NAMESPACE:
                # A typo or misplaced subdirective: refuse it, like a
                # real instance would.
                raise
            logger.debug("Swallowing unknown directive %s", name)
            return _swallow


def scan_package(package):
    """Register the emailkit templates ``package``'s ZCML declares.

    Executes ``configure.zcml`` then ``overrides.zcml`` (when present).

    :param package: a dotted name or an imported package.
    :raises zope.configuration errors: as at instance startup.
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

    ``<include file=...>`` always passes. ``<include package=...>`` of
    anything outside ``root`` is dropped: not executed, though still
    imported.
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
