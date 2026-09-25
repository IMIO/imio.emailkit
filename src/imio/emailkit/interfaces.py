"""Module where all interfaces, events and exceptions live."""

from imio.emailkit import _
from zope import schema
from zope.interface import Attribute
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IEmailkitLayer(IDefaultBrowserLayer):
    """Browser layer that activates the z3c.jbot overrides of Plone's stock mails.

    Installed only by ``imio.emailkit:default``. An overriding layer must
    extend this one for jbot precedence to apply.
    """


#: Prefix of the ``plone.app.registry`` records built from
#: :class:`IEmailkitTheme`, so the record names come out as
#: ``imio.emailkit.theme.logo_url`` and friends.
THEME_REGISTRY_PREFIX = "imio.emailkit.theme"


class IEmailkitTheme(Interface):
    """The three runtime-variable branding tokens.

    Everything else in the design system is fixed Tailwind. ``profiles/base``
    builds its records from this interface; the defaults below are the
    only source of truth.
    """

    logo_url = schema.TextLine(
        title=_("Logo URL"),
        description=_(
            "Absolute URL of the logo shown in the mail header. Remote URL, "
            "not an inline image."
        ),
        required=False,
        default="",
        missing_value="",
    )

    primary_color = schema.TextLine(
        title=_("Primary color"),
        description=_(
            "Hexadecimal color used by buttons and the header rule, for "
            "example ``#e6007e``."
        ),
        required=False,
        # iMio magenta. Must match the fallback in `kit/tailwind.css`: two
        # different brand colors in one package would be a visible bug.
        default="#e6007e",
        missing_value="",
    )

    footer_html = schema.Text(
        title=_("Footer HTML"),
        description=_(
            "HTML inserted in the mail footer. Rendered unescaped -- it is one "
            "of the two slots allowed to carry markup."
        ),
        required=False,
        default="",
        missing_value="",
    )


class IEmailRecipient(Interface):
    """What ``.to()``/``.cc()``/``.bcc()`` resolve every value to.

    The builder adapts each value to this interface at ``.send()``. An
    adapter that cannot resolve returns ``None``, never an invented address.
    """

    email = Attribute("address")
    fullname = Attribute("display name, may be empty")
    language = Attribute("preferred language code, may be None")


class EmailkitError(Exception):
    """Base class of every error this package raises deliberately."""


class TemplateNotFound(EmailkitError):
    """No template is registered under the requested name.

    Carries the available names, to help catch a typo.
    """

    def __init__(self, name, available=()):
        self.name = name
        self.available = sorted(available)
        super().__init__(
            f"No email template registered as {name!r}. "
            f"Available: {', '.join(self.available) or '(none)'}"
        )


class _CollectedError(EmailkitError):
    """Base of the two ``.send()``-time errors that report every problem at once."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__(
            f"{self._headline} ({len(self.problems)}):\n  - "
            + "\n  - ".join(self.problems)
        )


class RecipientError(_CollectedError):
    """One or more recipients could not be resolved.

    Raised at ``.send()`` instead of a silent drop.
    """

    _headline = "Unresolvable recipient(s)"


class AttachmentError(_CollectedError):
    """One or more attachments could not be resolved. Raised at ``.send()``."""

    _headline = "Unusable attachment(s)"
