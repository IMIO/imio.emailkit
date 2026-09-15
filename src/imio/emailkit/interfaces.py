"""Module where all interfaces, events and exceptions live."""

from imio.emailkit import _
from zope import schema
from zope.interface import Attribute
from zope.interface import Interface
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IEmailkitLayer(IDefaultBrowserLayer):
    """Browser layer carrying the z3c.jbot overrides of Plone's default mails.

    This layer is what *activates* the restyled stock mails, and it is
    installed by the ``imio.emailkit:default`` profile only. ``:base`` ships the
    runtime without it, which is the opt-out: the jbot directory is bound to
    this layer in ``browser/configure.zcml``, so the overrides are inert until
    the layer is installed.

    A site package overriding our templates in turn must declare a layer that
    **extends** this one -- z3c.jbot precedence is only a guarantee for child
    layers, not for siblings.
    """


#: Prefix of the ``plone.app.registry`` records built from
#: :class:`IEmailkitTheme`, so the record names come out as
#: ``imio.emailkit.theme.logo_url`` and friends.
THEME_REGISTRY_PREFIX = "imio.emailkit.theme"


class IEmailkitTheme(Interface):
    """The three runtime-variable branding tokens.

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


class IEmailRecipient(Interface):
    """The one thing ``.to()``/``.cc()``/``.bcc()`` resolve a value to.

    Those methods take "an email string, a Plone member object, a userid, or
    an iterable of those", and resolution goes through a single adapter. So
    the builder holds whatever it was handed and, at ``.send()``, adapts each
    value to this interface. Adding a new kind of recipient is one adapter
    registration and no change to the builder -- which is what keeps "it
    holds data, it does not grow behaviour" true.

    An adapter that cannot resolve its value returns ``None`` (the ordinary
    zope.component "not adaptable" answer); ``recipients.resolve()`` turns that
    into :class:`RecipientError`. It must never invent an address.
    """

    email = Attribute("address")
    fullname = Attribute("display name, may be empty")
    language = Attribute("preferred language code, may be None")


class EmailkitError(Exception):
    """Base class of every error this package raises deliberately."""


class TemplateNotFound(EmailkitError):
    """No template is registered under the requested name.

    The available names travel with the error: the mistake
    is nearly always a typo or a template whose ZCML never registered, and both
    are obvious once the list is in front of you.
    """

    def __init__(self, name, available=()):
        self.name = name
        self.available = sorted(available)
        super().__init__(
            f"No email template registered as {name!r}. "
            f"Available: {', '.join(self.available) or '(none)'}"
        )


class _CollectedError(EmailkitError):
    """Base of the two ``.send()``-time errors that report *every* problem.

    Both are raised at ``.send()`` rather than at collection time, and the
    reason is this class: a caller who mistyped three userids should learn about
    three, not fix one and run again. So resolution collects problems and raises
    once.
    """

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__(
            f"{self._headline} ({len(self.problems)}):\n  - "
            + "\n  - ".join(self.problems)
        )


class RecipientError(_CollectedError):
    """One or more recipients could not be resolved.

    Raised at ``.send()``. Never a silent drop: a mail that quietly reaches four
    of five people is the failure mode this exception exists to make impossible.
    """

    _headline = "Unresolvable recipient(s)"


class AttachmentError(_CollectedError):
    """One or more attachments could not be resolved.

    Raised at ``.send()``, for an unreadable source or for missing filename /
    mimetype that could not be inferred.
    """

    _headline = "Unusable attachment(s)"
