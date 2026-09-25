"""The registry of email templates the ``emailkit:templates`` directive fills.

A consumer addon declares templates in ZCML. Each ``<emailkit:template>``
resolves its files on disk and writes one :class:`Template` here, under
the namespaced name ``"<package>:<basename>"``.

A duplicate registration raises ``ConfigurationConflictError``.

:func:`overlay` is the test seam: it snapshots the registry for
throwaway test registrations.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from imio.emailkit.interfaces import TemplateNotFound
from pathlib import Path

import logging


logger = logging.getLogger("imio.emailkit.discovery")

#: Suffixes of the two compiled artifacts a template ships.
HTML_SUFFIX = ".pt"
TEXT_SUFFIX = ".txt.pt"

#: ``directory`` attribute of ``<emailkit:templates>``, when the addon omits it.
DEFAULT_DIRECTORY = "templates"


@dataclass(frozen=True)
class Template:
    """One registered template, resolved to files on disk."""

    #: Namespaced lookup name, ``"<package>:<basename>"``.
    name: str
    #: Package that registered it.
    package: str
    #: File stem, after the colon in :attr:`name`.
    basename: str
    #: Compiled HTML template.
    html_path: Path
    #: Plaintext twin, or ``None`` (``render()`` then extracts naively).
    text_path: Path | None
    #: i18n msgid of the subject.
    subject: object = None
    #: i18n msgid of the preview line.
    preheader: object = None


_templates = {}
#: Maps package to its templates directory, for the build tooling.
_directories = {}


def register_template(template):
    """The single write path into the registry."""
    _templates[template.name] = template


def register_directory(package, templates_dir):
    """Record where ``package``'s compiled templates live (build-tool query)."""
    _directories[package] = Path(templates_dir)


def registered_directories():
    """The full ``package -> directory`` mapping, as a copy."""
    return dict(_directories)


def get_templates():
    """The full ``name -> Template`` mapping, as a copy."""
    return dict(_templates)


def get_template(name):
    """Return the :class:`Template` registered as ``name``.

    :raises TemplateNotFound: when nothing is registered under that name.
    """
    try:
        return _templates[name]
    except KeyError:
        raise TemplateNotFound(name, available=_templates) from None


def available_templates():
    """Every registered template name, sorted."""
    return sorted(_templates)


def reset():
    """Empty the registry. For rescans (preview) and test isolation."""
    _templates.clear()
    _directories.clear()


def forget_package(package):
    """Drop one package's templates and directory record."""
    for name in [n for n, t in _templates.items() if t.package == package]:
        del _templates[name]
    _directories.pop(package, None)


@contextmanager
def overlay():
    """Snapshot the registry, restore it on exit. The test seam."""
    saved_templates = dict(_templates)
    saved_directories = dict(_directories)
    try:
        yield
    finally:
        _templates.clear()
        _templates.update(saved_templates)
        _directories.clear()
        _directories.update(saved_directories)


def load_template(package, package_dir, directory, basename, subject, preheader):
    """Resolve one registration to files on disk, or ``None`` plus a warning."""
    directory_path = (Path(package_dir) / directory).resolve()
    html_path = directory_path / f"{basename}{HTML_SUFFIX}"
    if not html_path.is_file():
        logger.warning(
            "%s registers the template %r but %s is missing; skipping it. "
            "The compiled output is committed, so this is a build or "
            "packaging problem, not a runtime one.",
            package,
            basename,
            html_path,
        )
        return None
    text_path = directory_path / f"{basename}{TEXT_SUFFIX}"
    if not text_path.is_file():
        logger.warning(
            "%s:%s ships no %s plaintext twin. render() will fall back to "
            "naive text extraction, which is deprecated -- ship a twin.",
            package,
            basename,
            TEXT_SUFFIX,
        )
        text_path = None
    return Template(
        name=f"{package}:{basename}",
        package=package,
        basename=basename,
        html_path=html_path,
        text_path=text_path,
        subject=subject,
        preheader=preheader,
    )
