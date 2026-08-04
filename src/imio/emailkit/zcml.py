"""The ``<emailkit:templates>`` / ``<emailkit:template>`` directives.

Registration is ZCML rather than Python so it inherits the machinery every
other Zope registration has: duplicate names are a ``ConfigurationConflictError``
at startup instead of a silent overwrite, ``overrides.zcml`` can replace a
registration, ``zcml:condition`` gates one, and the msgid domain of ``subject``
/ ``preheader`` comes from the enclosing ``i18n_domain`` instead of a hand-wired
``MessageFactory``.

The handler only *emits actions*; the file checks live in
``discovery.load_template`` and run when actions execute. That keeps the
warnings at startup (action execution time) and lets conflict resolution see
every registration before any of them takes effect.
"""

from imio.emailkit import discovery
from pathlib import Path
from zope.configuration.exceptions import ConfigurationError
from zope.configuration.fields import MessageID
from zope.interface import Interface
from zope.schema import TextLine


class ITemplatesDirective(Interface):
    """``<emailkit:templates>`` -- one block per package."""

    directory = TextLine(
        title="Directory holding the compiled templates",
        description=(
            "Relative to the package the ZCML file belongs to. Defaults to "
            "`templates`. Relative traversal is allowed on purpose -- a "
            "subpackage's block may point at its parent's files with "
            "`../templates` -- but absolute paths are rejected."
        ),
        required=False,
    )


class ITemplateDirective(Interface):
    """``<emailkit:template>`` -- one registered template."""

    name = TextLine(
        title="Template basename",
        description="Resolves to `<directory>/<name>.pt` and `<name>.txt.pt`.",
        required=True,
    )

    subject = MessageID(
        title="Subject msgid",
        description=(
            "Translated per recipient language at send time. Use "
            "`[msgid] Default text` to pick the msgid explicitly."
        ),
        required=True,
    )

    preheader = MessageID(
        title="Preheader msgid",
        description=(
            "The hidden inbox-preview line next to the subject. Omitted, the "
            "layout's preview div collapses to nothing."
        ),
        required=False,
    )


class TemplatesDirective:
    """Handler for one ``<emailkit:templates>`` block.

    The namespace of every contained template is the package the ZCML file
    belongs to -- never spelled out by the consumer, so it cannot lie.
    """

    def __init__(self, context, directory=None):
        package = getattr(context, "package", None)
        if package is None:
            raise ConfigurationError(
                "emailkit:templates must be used in a package's ZCML: the "
                "package is the template namespace and the base the directory "
                "resolves against."
            )
        if directory is not None and Path(directory).is_absolute():
            raise ConfigurationError(
                f"emailkit:templates directory={directory!r} must be relative "
                "to the package, not absolute."
            )
        self.context = context
        self.package = package.__name__
        self.package_dir = Path(package.__file__).parent
        self.directory = directory or discovery.DEFAULT_DIRECTORY
        # One directory record per package: any second <emailkit:templates>
        # block in the same package conflicts here, regardless of what
        # directory it names -- the discriminator carries no directory
        # component. That is deliberate: the build tooling needs a single
        # answer to "where does output land" for a given package.
        context.action(
            discriminator=("emailkit:templates", self.package),
            callable=discovery.register_directory,
            args=(self.package, (self.package_dir / self.directory).resolve()),
        )

    def template(self, context, name, subject, preheader=None):
        full_name = f"{self.package}:{name}"
        context.action(
            discriminator=("emailkit:template", full_name),
            callable=_load_and_register,
            args=(
                self.package,
                self.package_dir,
                self.directory,
                name,
                subject,
                preheader,
            ),
        )

    def __call__(self):
        return ()


def _load_and_register(package, package_dir, directory, basename, subject, preheader):
    template = discovery.load_template(
        package, package_dir, directory, basename, subject, preheader
    )
    if template is not None:
        discovery.register_template(template)
