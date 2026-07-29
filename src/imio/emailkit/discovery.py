"""Entry-point discovery of email templates (SPEC §4).

A consumer addon declares one ``imio.emailkit.templates`` entry point pointing
at a module-level ``emailkit`` dict; this module turns every such registration
into a flat mapping of ``<package>:<name>`` -> :class:`Template`, with the
``.pt`` and ``.txt.pt`` files already resolved on disk.

The scan runs once and is cached: its answer only changes when the set of
installed distributions does, which does not happen inside a running instance.
:func:`invalidate_cache` exists for tests that install a dummy addon.
"""

from dataclasses import dataclass
from imio.emailkit.interfaces import TemplateNotFound
from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path

import logging


logger = logging.getLogger("imio.emailkit.discovery")

#: The entry-point group consumers declare. SPEC §4.
ENTRY_POINT_GROUP = "imio.emailkit.templates"

#: Suffixes of the two compiled artifacts a template ships.
HTML_SUFFIX = ".pt"
TEXT_SUFFIX = ".txt.pt"

#: ``directory`` key of the registration dict, when the addon omits it.
DEFAULT_DIRECTORY = "templates"


@dataclass(frozen=True)
class Template:
    """One registered template, resolved to files on disk."""

    #: Namespaced lookup name, ``"<package>:<basename>"``.
    name: str
    #: The entry-point name, i.e. the namespace part of :attr:`name`.
    package: str
    #: The file stem, i.e. the part after the colon in :attr:`name`.
    basename: str
    #: The compiled HTML template. Always present -- a template whose ``.pt``
    #: is missing is not registered at all.
    html_path: Path
    #: The plaintext twin, or ``None`` when the addon ships none. SPEC §4 then
    #: has ``render()`` fall back to naive text extraction.
    text_path: Path | None
    #: i18n msgid of the subject, from the registration.
    subject: object = None
    #: Optional i18n msgid of the hidden inbox-preview line (SPEC §3).
    preheader: object = None


_templates = None


def get_templates():
    """Return the cached ``name -> Template`` mapping, scanning on first use."""
    global _templates
    if _templates is None:
        _templates = _scan()
    return _templates


def get_template(name):
    """Return the :class:`Template` registered as ``name``.

    :raises TemplateNotFound: when nothing is registered under that name.
    """
    templates = get_templates()
    try:
        return templates[name]
    except KeyError:
        raise TemplateNotFound(name, available=templates) from None


def available_templates():
    """Return every registered template name, sorted."""
    return sorted(get_templates())


def invalidate_cache():
    """Drop the cached scan. For tests that add or remove a registration."""
    global _templates
    _templates = None


def warm_cache(event=None):
    """Run the scan at instance start-up.

    Subscribed to ``IDatabaseOpenedWithRoot`` in ``configure.zcml``, so SPEC
    §4's "missing ``.txt.pt`` twin -> warning at startup" happens at startup and
    not on the first mail somebody sends three weeks later.
    """
    get_templates()


def _scan():
    templates = {}
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        for template in _load(entry_point):
            templates[template.name] = template
    logger.info(
        "Discovered %s email template(s) from %s: %s",
        len(templates),
        ENTRY_POINT_GROUP,
        ", ".join(sorted(templates)) or "(none)",
    )
    return templates


def _load(entry_point):
    """Yield the templates one entry point registers.

    A broken registration is logged with its traceback and skipped rather than
    raised: discovery runs at instance start-up, and one consumer addon with a
    typo must not stop the instance -- nor stop the *other* addons' mails from
    being found. ``logger.exception`` keeps it loud.
    """
    try:
        registration = entry_point.load()
        directory = _resolve_directory(entry_point, registration)
    except Exception:
        logger.exception(
            "Could not load the %s registration of %r; skipping it.",
            ENTRY_POINT_GROUP,
            entry_point.name,
        )
        return

    if not directory.is_dir():
        logger.warning(
            "%r declares its email templates in %s, which does not exist. "
            "Nothing registered for that package -- has the Maizzle build run?",
            entry_point.name,
            directory,
        )
        return

    for basename, options in (registration.get("templates") or {}).items():
        html_path = directory / f"{basename}{HTML_SUFFIX}"
        if not html_path.is_file():
            logger.warning(
                "%r registers the template %r but %s is missing; skipping it. "
                "The compiled output is committed, so this is a build or "
                "packaging problem, not a runtime one.",
                entry_point.name,
                basename,
                html_path,
            )
            continue

        text_path = directory / f"{basename}{TEXT_SUFFIX}"
        if not text_path.is_file():
            # SPEC §4: warning at startup; render() then falls back to naive
            # text extraction and logs a deprecation of its own.
            logger.warning(
                "%s:%s ships no %s plaintext twin. render() will fall back to "
                "naive text extraction, which is deprecated -- ship a twin.",
                entry_point.name,
                basename,
                TEXT_SUFFIX,
            )
            text_path = None

        yield Template(
            name=f"{entry_point.name}:{basename}",
            package=entry_point.name,
            basename=basename,
            html_path=html_path,
            text_path=text_path,
            subject=(options or {}).get("subject"),
            preheader=(options or {}).get("preheader"),
        )


def _resolve_directory(entry_point, registration):
    """Resolve the registration's ``directory``, relative to its own package.

    The directory is relative to the module the entry point *points at* -- the
    right-hand side of ``imio.pm.notifications = imio.pm.notifications:emailkit``
    -- while the lookup namespace is the entry-point *name*, the left-hand side.
    They are the same string in every sane registration; resolving them from
    their own side keeps the odd one honest instead of guessing.
    """
    module = import_module(entry_point.module)
    package_directory = Path(module.__file__).parent
    subdirectory = registration.get("directory") or DEFAULT_DIRECTORY
    return (package_directory / subdirectory).resolve()
