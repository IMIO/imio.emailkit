"""SPEC §6.2 recipient resolution -- one adapter, no ``isinstance`` in the builder.

``.to()``/``.cc()``/``.bcc()`` accept "an email string, a Plone member object, a
userid, or an iterable of those". This module is where that polymorphism lives, so
:class:`~imio.emailkit.email.Email` can stay the plain data holder §6.2 requires:
the builder flattens what it is handed and calls :func:`resolve` at ``.send()``.

Three things are deliberate and worth reading before changing anything here.

* **Failures are collected, not raised one at a time.** §6.2 puts resolution at
  ``.send()`` precisely so every bad value surfaces in one
  :class:`~imio.emailkit.interfaces.RecipientError`.
* **An adapter returns ``None`` rather than a placeholder.** "Fail loud, not
  silent drop" (§6.2) means the *absence* of an answer has to travel; an adapter
  that guessed an address would send a real mail to the wrong person.
* **A ``str`` containing ``@`` is an address, full stop -- no member lookup.**
  See :func:`recipient_from_string` for why.
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
    """A resolved recipient: exactly SPEC §6.2's three attributes and nothing else.

    Frozen and hashable so :func:`resolve` can de-duplicate without inventing a
    key, and immutable so a resolved list cannot be edited into disagreeing with
    what was sent.
    """

    email: str
    fullname: str = ""
    language: str | None = None


@adapter(str)
@implementer(IEmailRecipient)
def recipient_from_string(value):
    """SPEC §6.2's default ``str`` adapter: an address, or a userid.

    ``"@" in value`` decides, and it decides *for* the address reading. That is a
    real choice, because a userid can look like an email address when a site runs
    ``use_email_as_login``. Taking the string at face value can only ever send to
    the address the caller wrote; the other order -- look the userid up first --
    would take ``"greffe@commune.be"`` and, if some member happened to carry that
    userid with a different ``email`` property, deliver somewhere else entirely.
    A wrong address is much worse than a missing display name.

    Consequence, and it is the documented trade-off: a bare address resolves with
    no ``fullname`` and no ``language``, so it lands in §6.2's default-language
    group. Pass the member object (or its userid) when the language matters.

    ``"Greffe <greffe@commune.be>"`` is accepted too, and the display name is
    kept. This is not decoration: without the parse, the whole string became the
    address and the header came out as ``"Greffe <greffe"@commune.be`` -- valid
    syntax, wrong mailbox, no error anywhere. Measured, then fixed.

    A string carrying *several* addresses is refused rather than silently reduced
    to its first: ``getaddresses`` would hand back only one and the rest would
    vanish, which is the silent drop §6.2 forbids. Pass a list.
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
    """SPEC §6.2's default Plone-member adapter.

    ``getProperty`` rather than attribute access because ``MemberData`` is not
    path- or attribute-traversable for its properties (the same Phase 0 finding
    that shapes the default-mail templates), and because a site is free to drop
    the ``language`` property from ``portal_memberdata`` -- hence the default.

    An empty ``language`` property, which is what Plone stores for "no
    preference", becomes ``None``: §6.2's attribute is documented as "may be
    ``None``", and ``""`` would otherwise become its own language group.

    A member whose ``email`` property holds *several* addresses is refused, for
    the same reason the string adapter refuses one: nothing downstream can send
    to two mailboxes in one field, and the failure was silent. ``parseaddr`` on
    ``"a@b.be, c@d.be"`` returns ``('', '')``, so the header came out as
    ``Full Name <>`` and the recipient simply vanished from the envelope while
    every other recipient in the same call was delivered -- exactly the silent
    drop §6.2 forbids. Returning ``None`` here turns it into a ``RecipientError``
    naming the member.

    A ``"Zoe <z@b.be>"`` shaped property is parsed rather than passed through, so
    the address never ends up nested inside another display name. That is the same
    defect that made ``.sender("Greffe <greffe@commune.be>")`` produce
    ``From: "Greffe <greffe"@commune.be`` -- valid syntax, wrong mailbox, no error
    -- and this adapter was on the path that had not been fixed.
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

    ``queryUtility`` rather than ``getToolByName``: resolution happens inside
    ``.send()``, which has a site but is handed no context to acquire from.
    """
    tool = queryUtility(IMembershipTool)
    if tool is None:
        return None
    return tool.getMemberById(userid)


def resolve(values):
    """Adapt every value in ``values`` to :class:`.IEmailRecipient`.

    :param values: already-flattened recipient values, in the order given
    :returns: resolved recipients, de-duplicated by address, order preserved
    :raises RecipientError: listing *every* value that could not be resolved

    De-duplication keeps the **first** occurrence, which is the one most likely to
    carry a ``fullname`` and a ``language`` -- callers naturally write
    ``.to(member).to(some_shared_list)`` and not the reverse. Comparison is
    case-insensitive on the address, since a mail server is.

    Scope note: duplicates are removed *within* one field, never across To/Cc/Bcc.
    Dropping an address from Cc because it is also in To would change what every
    recipient sees in the header, and that is the caller's editorial decision, not
    ours.
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
        # Checked here rather than trusted from the adapter, because this is what
        # lets `email.py` split every address on '@' without a guard of its own.
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
        # Suppressed rather than trusted: this function only ever runs while
        # building an error message, and a traceback from *here* would replace the
        # RecipientError the caller actually needs to read.
        with suppress(Exception):
            return f"{type(value).__name__} {userid()!r}"
    return f"{type(value).__name__} {value!r}"


def describe_failure(value):
    """Say *why* a value did not resolve, not merely that it did not.

    The two realistic causes need different fixes -- a typo in a userid versus a
    missing adapter registration -- and the message is the only place a caller
    finds out which one they have.
    """
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
    """SPEC §6.2's per-language grouping: one entry per distinct language.

    :param fields: mapping of field name (``"to"``/``"cc"``/``"bcc"``) to its
        resolved recipients
    :param default_language: language used for recipients whose own is ``None``
    :returns: list of ``(language, {field: [recipient, ...]})``, in first-seen
        order of the languages

    A group holds only *its own* recipients in every field, so a French To and a
    Dutch Cc produce two messages, the second with no ``To`` header. That is the
    honest consequence of §6.2 ("renders once per language group, and emits one
    message per group"): the alternative -- repeating the full header lists in
    every message -- would put the French body in front of the Dutch reader,
    which is the exact failure per-language sending exists to prevent.

    Languages are grouped on the string as resolved, with no normalisation. ``fr``
    and ``fr-BE`` are therefore two groups: they are two different renders as far
    as the locale helpers are concerned (§6.1 -- Belgian French groups thousands
    differently from French French), so merging them would be wrong, not thrifty.
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

    Deliberately the *site's* default rather than the current request's: a mail is
    sent for the recipient's benefit, and the request language belongs to whoever
    happened to trigger it -- often a manager, sometimes a cron job with no
    request at all.
    """
    registry = queryUtility(IRegistry)
    if registry is not None:
        language = registry.get("plone.default_language", None)
        if language:
            return language
    return FALLBACK_LANGUAGE
