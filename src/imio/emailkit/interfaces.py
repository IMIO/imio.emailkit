"""Module where all interfaces, events and exceptions live."""

from imio.emailkit import _
from zope import schema
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IEmailkitLayer(IDefaultBrowserLayer):
    """Browser layer carrying the z3c.jbot overrides of Plone's default mails.

    This layer is what *activates* SPEC §8's restyled stock mails, and it is
    installed by the ``imio.emailkit:default`` profile only. ``:base`` ships the
    runtime without it, which is §8.2's opt-out: the jbot directory is bound to
    this layer in ``browser/configure.zcml``, so the overrides are inert until
    the layer is installed.

    A site package overriding our templates in turn must declare a layer that
    **extends** this one -- z3c.jbot precedence is only a guarantee for child
    layers, not for siblings (see docs/DECISIONS.md).
    """


#: Prefix of the ``plone.app.registry`` records built from
#: :class:`IEmailkitTheme`, so the record names read exactly as SPEC §3 has
#: them: ``imio.emailkit.theme.logo_url`` and friends.
THEME_REGISTRY_PREFIX = "imio.emailkit.theme"


class IEmailkitTheme(Interface):
    """SPEC §3's three runtime-variable branding tokens.

    Everything else in the design system is Tailwind, fixed at build time; these
    are the only values a site may change without recompiling. The field
    defaults below are the single source of truth -- ``profiles/base`` declares
    the records from this interface and ships no values of its own, so a default
    is written once, here.

    Only ``primary_color`` carries a real default. ``logo_url`` and
    ``footer_html`` default to empty on purpose: a URL is site-specific and
    footer wording is user-facing text, which the house convention leaves to
    i18n and to the site rather than freezing it in a profile.
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
        # iMio magenta, the same value the kit layout falls back to when no
        # registry is reachable. Kept in step with `kit/tailwind.css` on purpose:
        # two different "brand colours" in one package is a bug waiting to be
        # noticed by a client.
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


class EmailkitError(Exception):
    """Base class of every error this package raises deliberately."""


class TemplateNotFound(EmailkitError):
    """No template is registered under the requested name.

    SPEC §4 requires the available names to travel with the error: the mistake
    is nearly always a typo or a forgotten entry point, and both are obvious
    once the list is in front of you.
    """

    def __init__(self, name, available=()):
        self.name = name
        self.available = sorted(available)
        super().__init__(
            f"No email template registered as {name!r}. "
            f"Available: {', '.join(self.available) or '(none)'}"
        )
