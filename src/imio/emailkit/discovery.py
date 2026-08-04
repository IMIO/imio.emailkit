"""The registry of email templates the ``emailkit:templates`` directive fills.

A consumer addon declares its templates in ZCML (see ``meta.zcml`` and
``zcml.py``); each ``<emailkit:template>`` becomes a configuration action whose
callable resolves the ``.pt`` / ``.txt.pt`` files on disk and writes one
:class:`Template` here. Lookup stays namespaced: ``"<package>:<basename>"``.

There is no scan and no cache: ZCML execution *is* the startup scan, so the
"missing plaintext twin" warning lands in the startup log by construction, and
duplicate registrations are a ``ConfigurationConflictError`` instead of a
silent overwrite. Re-executing the same ZCML (test layers stack it) simply
rewrites the same values, which is why :func:`register_template` overwrites
without complaint -- within one configuration run the action discriminator
already guarantees uniqueness.

:func:`overlay` is the test seam: it snapshots the registry so a block can
register throwaway addons (the dummies) and leave no trace.
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
    #: The package whose ZCML registered it, i.e. the namespace part of :attr:`name`.
    package: str
    #: The file stem, i.e. the part after the colon in :attr:`name`.
    basename: str
    #: The compiled HTML template. Always present -- a template whose ``.pt``
    #: is missing is not registered at all.
    html_path: Path
    #: The plaintext twin, or ``None`` when the addon ships none; ``render()``
    #: then falls back to naive text extraction and logs a deprecation.
    text_path: Path | None
    #: i18n msgid of the subject, from the registration.
    subject: object = None
    #: Optional i18n msgid of the hidden inbox-preview line.
    preheader: object = None


_templates = {}
#: ``package -> templates directory``; what the build tooling reads to know
#: where compiled output lands, even for a package whose first build has not
#: run yet (its directory holds no ``.pt`` to derive the answer from).
_directories = {}


def register_template(template):
    """The single write path into the registry."""
    _templates[template.name] = template


def register_directory(package, templates_dir):
    """Record where ``package``'s compiled templates live (build-tool query)."""
    _directories[package] = Path(templates_dir)


def registered_directories():
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
        raise TemplateNotFound(name, available=dict(_templates)) from None


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
    """Resolve one registration to files on disk, or ``None`` plus a warning.

    Called when configuration actions execute -- at instance startup, or at the
    end of a build-tool scan -- so every warning below lands where someone
    deploying can see it, not in the log of whoever sends the first mail.
    """
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
