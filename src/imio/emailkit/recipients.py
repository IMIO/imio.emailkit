"""Recipient resolution: one adapter, no ``isinstance`` in the builder.

``.to()``/``.cc()``/``.bcc()`` accept an email string, a Plone member, a
userid, or an iterable of those. The builder flattens what it is handed
and calls :func:`resolve` at ``.send()``.

Rules:

* Failures are collected, not raised one at a time.
* An adapter returns ``None``, never a guessed address.
* A ``str`` containing ``@`` is always an address, never a member lookup.
  See :func:`recipient_from_string`.
"""

from contextlib import suppress
from dataclasses import dataclass
from email.utils import getaddresses
from imio.emailkit.helpers import FALLBACK_LANGUAGE
from imio.emailkit.interfaces import IEmailRecipient
from imio.emailkit.interfaces import RecipientError
from plone.registry.interfaces import IRegistry
from Products.CMFCore.interfaces import IMember
from Products.CMFCore.interfaces import IMembershipTool
from zope.component import adapter
from zope.component import queryUtility
from zope.interface import implementer


@implementer(IEmailRecipient)
@dataclass(frozen=True)
class Recipient:
    """A resolved recipient: exactly three attributes and nothing else.

    Frozen and hashable, so :func:`resolve` can de-duplicate without a
    separate key.
    """

    email: str
    fullname: str = ""
    language: str | None = None


@adapter(str)
@implementer(IEmailRecipient)
def recipient_from_string(value):
    """The default ``str`` adapter: an address, or a userid.

    ``"@" in value`` decides: this trusts the address as written, since a
    wrong address is worse than a missing display name.

    A bare address gets no ``fullname``/``language``.
    ``"Greffe <greffe@commune.be>"`` is parsed, keeping the display name
    out of the address. A string with several addresses is refused.
    """
    value = value.strip()
    if not value:
        return None
    if "@" in value:
        pairs = getaddresses([value])
        if len(pairs) != 1:
            return None
        fullname, address = pairs[0]
        if "@" not in address:
            return None
        return Recipient(email=address, fullname=fullname)
    member = lookup_member(value)
    if member is None:
        return None
    return IEmailRecipient(member, None)


@adapter(IMember)
@implementer(IEmailRecipient)
def recipient_from_member(member):
    """The default Plone-member adapter.

    Uses ``getProperty``, not attribute access: ``MemberData`` properties
    are not attribute-traversable. An empty ``language`` becomes ``None``.

    A member whose ``email`` holds several addresses is refused, since
    ``parseaddr`` would silently drop it.
    """
    raw = (member.getProperty("email", "") or "").strip()
    fullname = (member.getProperty("fullname", "") or "").strip()
    email = raw
    if raw:
        pairs = getaddresses([raw])
        if len(pairs) != 1:
            return None
        parsed_name, address = pairs[0]
        email = address
        fullname = fullname or parsed_name
    return Recipient(
        email=email,
        fullname=fullname,
        language=(member.getProperty("language", "") or "").strip() or None,
    )


def lookup_member(userid):
    """The member registered under ``userid``, or ``None``.

    Uses ``queryUtility``, not ``getToolByName``: ``.send()`` has a site but
    no context to acquire from.
    """
    tool = queryUtility(IMembershipTool)
    if tool is None:
        return None
    return tool.getMemberById(userid)


def resolve(values):
    """Adapt every value in ``values`` to :class:`.IEmailRecipient`.

    :param values: already-flattened recipient values, in the order given
    :returns: resolved recipients, de-duplicated by address, order preserved
    :raises RecipientError: lists every value that could not be resolved

    Keeps the first duplicate, case-insensitive, only within one field.
    """
    resolved = []
    seen = set()
    problems = []
    for value in values:
        recipient = IEmailRecipient(value, None)
        if recipient is None:
            problems.append(describe_failure(value))
            continue
        address = (recipient.email or "").strip()
        if not address:
            problems.append(f"{describe(value)} resolved to an empty email address")
            continue
        # Checked here so email.py can split every address on '@' with no
        # guard of its own.
        if "@" not in address:
            problems.append(
                f"{describe(value)} resolved to {address!r}, which is not an "
                f"email address"
            )
            continue
        key = address.lower()
        if key in seen:
            continue
        seen.add(key)
        resolved.append(recipient)
    if problems:
        raise RecipientError(problems)
    return resolved


def describe(value):
    """A short, unambiguous rendering of a recipient value, for error messages."""
    if isinstance(value, str):
        return repr(value)
    userid = getattr(value, "getId", None)
    if callable(userid):
        # Suppressed: a traceback here would replace the RecipientError the
        # caller needs to see.
        with suppress(Exception):
            return f"{type(value).__name__} {userid()!r}"
    return f"{type(value).__name__} {value!r}"


def describe_failure(value):
    """Say why a value did not resolve: a typo versus a missing adapter."""
    if isinstance(value, str):
        if "@" not in value:
            return (
                f"{value!r} is neither an email address (no '@') nor a known "
                f"userid in this site"
            )
        return (
            f"{value!r} is not one parsable email address; pass a list rather "
            f"than a string holding several"
        )
    return (
        f"{describe(value)} has no {IEmailRecipient.__name__} adapter; register "
        f"one for its type or pass an address, a userid or a Plone member"
    )


def group_by_language(fields, default_language):
    """Per-language grouping: one entry per distinct language.

    :param fields: mapping of field name (``"to"``/``"cc"``/``"bcc"``) to its
        resolved recipients
    :param default_language: language used for recipients whose own is ``None``
    :returns: list of ``(language, {field: [recipient, ...]})``, in first-seen
        order of the languages

    Each group holds only its own recipients, so a French To and Dutch Cc
    produce two separate messages. Languages are not normalised: ``fr``
    and ``fr-be`` form two groups.
    """
    groups = {}
    for field, recipients in fields.items():
        for recipient in recipients:
            language = recipient.language or default_language
            groups.setdefault(language, {name: [] for name in fields})
            groups[language][field].append(recipient)
    return list(groups.items())


def default_language():
    """The language recipients without a preference are grouped under.

    The site's default, not the request's, since the request may belong
    to a manager or a cron job.
    """
    registry = queryUtility(IRegistry)
    if registry is not None:
        language = registry.get("plone.default_language", None)
        if language:
            return language
    return FALLBACK_LANGUAGE
