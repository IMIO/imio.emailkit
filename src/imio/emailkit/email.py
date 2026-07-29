"""SPEC §6.2 -- the ``Email`` builder.

.. code-block:: python

    Email("imio.pm.notifications:item_published") \\
        .to(member).to("greffe@commune.be").cc(meeting_managers) \\
        .reply_to("noreply@imio.be").with_context(item=item, meeting=meeting) \\
        .attach(convocation_pdf, filename="convocation.pdf").send()

**This API is frozen.** The methods are exactly the nine §6.2 names and there are
no others. Every one of them appends to a list or sets a field and returns
``self``; none of them touches the site, the registry, the filesystem or the
network. Everything that can fail happens inside :meth:`Email.send`, which is what
makes §6.2's "it holds data, it does not grow behaviour" checkable rather than
aspirational: if a method here ever needs an ``if``, the design is wrong and the
fix is a decision-log entry, not an ``if``.

The two neighbouring modules hold the polymorphism, on purpose:
:mod:`imio.emailkit.recipients` turns strings/userids/members into
``IEmailRecipient``, :mod:`imio.emailkit.attachments` turns five kinds of source
into bytes. Rendering is :func:`imio.emailkit.render.render`, unchanged and not
duplicated.

Two notes on the module name and the imports below. This module is
``imio.emailkit.email`` and it imports the standard library's ``email`` package;
under Python 3's absolute imports those do not collide -- ``from email.message
import EmailMessage`` here resolves to the stdlib, because this module is only
ever reachable as ``imio.emailkit.email``. And ``policy.SMTP`` rather than the
default policy: it is the default with CRLF line endings, which is what
``MailHost`` hands to ``smtplib`` verbatim.
"""

from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from imio.emailkit import attachments as attachment_sources
from imio.emailkit import recipients as recipient_sources
from imio.emailkit.discovery import get_template
from imio.emailkit.interfaces import EmailkitError
from imio.emailkit.interfaces import RecipientError
from imio.emailkit.render import render
from plone.registry.interfaces import IRegistry
from Products.MailHost.interfaces import IMailHost
from zope.component import getUtility
from zope.component import queryUtility
from zope.i18n import translate as zope_translate

import logging


logger = logging.getLogger("imio.emailkit.email")

#: Fields whose recipients are grouped by language and become message headers.
#: ``bcc`` is here too: ``MailHost`` strips the ``Bcc`` header after collecting
#: envelope recipients from it, which is exactly the behaviour we want and the
#: reason ``send()`` never passes ``mto`` explicitly.
RECIPIENT_FIELDS = ("to", "cc", "bcc")

#: Header name per recipient field.
HEADERS = {"to": "To", "cc": "Cc", "bcc": "Bcc"}


class Email:
    """Collect the parts of one styled mail, then send it (SPEC §6.2).

    :param name: namespaced template name, e.g.
        ``"imio.pm.notifications:item_published"``

    The template is *not* looked up here. ``Email("typo")`` is legal and silent;
    ``TemplateNotFound`` arrives from :meth:`send`. That is deliberate and matches
    how recipients and attachments behave -- one place where things fail, one place
    to look.
    """

    def __init__(self, name):
        self.name = name
        self._recipients = {field: [] for field in RECIPIENT_FIELDS}
        self._reply_to = []
        self._sender = None
        self._subject = None
        self._context = {}
        self._attachments = []

    # -- collection: data in, ``self`` out, nothing else ---------------------

    def to(self, value):
        """Add To recipients: an address, a member, a userid, or an iterable."""
        self._recipients["to"].extend(flatten(value))
        return self

    def cc(self, value):
        """Add Cc recipients. Same accepted values as :meth:`to`."""
        self._recipients["cc"].extend(flatten(value))
        return self

    def bcc(self, value):
        """Add Bcc recipients. Same accepted values as :meth:`to`.

        The ``Bcc`` header is removed before the message goes out, by ``MailHost``,
        after it has collected the envelope recipients from it. Blind means blind.
        """
        self._recipients["bcc"].extend(flatten(value))
        return self

    def reply_to(self, value):
        """Set the ``Reply-To`` addresses. Same accepted values as :meth:`to`.

        §6.2 only shows a literal address here, and that is the common case. The
        same values are accepted because it is the same header machinery and the
        same resolution rules -- ``.reply_to(item_author)`` should not need the
        caller to dig out an address by hand, and a second, str-only code path for
        one header would be the thing that eventually disagrees with the first.
        """
        self._reply_to.extend(flatten(value))
        return self

    def sender(self, value):
        """Override the ``From`` address. Same accepted values as :meth:`to`.

        Omitted, ``From`` is the site's configured sender (§6.2).
        """
        self._sender = flatten(value)
        return self

    def subject(self, value):
        """Override the subject; an i18n msgid or a literal string (§6.2).

        Omitted, the subject is the msgid in the template's registration (§4),
        translated per language group.
        """
        self._subject = value
        return self

    def with_context(self, **context):
        """Add names to the render context, as ``render()`` takes them (§6.1)."""
        self._context.update(context)
        return self

    def attach(self, source, filename=None, mimetype=None):
        """Add an attachment (SPEC §6.2). Callable repeatedly, order preserved.

        ``source`` is raw ``bytes``, a filesystem path, an open binary file, a
        ``NamedFile``/``NamedBlobFile`` value, or a Plone File/Image content
        object. ``filename`` and ``mimetype`` are inferred where the source carries
        them and required for ``bytes``; nothing is read until :meth:`send`.
        """
        self._attachments.append((source, filename, mimetype))
        return self

    # -- the one method that does anything ----------------------------------

    def send(self, immediate=False):
        """Resolve, render per language group, and hand each message to ``MailHost``.

        :param immediate: bypass the transaction and talk to the MTA now. The only
            escape hatch in §6.2; leave it alone unless you know why you want it.
        :returns: the :class:`~email.message.EmailMessage` objects handed to
            ``MailHost``, one per language group, in group order. Not part of
            §6.2's surface -- the spec's example discards it -- but returning what
            was built costs nothing and is what makes the preview view's send-test
            and §7's assertions possible without re-deriving it.
        :raises TemplateNotFound: no template registered under :attr:`name`
        :raises RecipientError: any recipient could not be resolved
        :raises AttachmentError: any attachment could not be resolved

        Resolution happens before the first render so that a mistyped userid does
        not surface only after half the language groups have been queued.
        Deliberately in this order: recipients first, because that is the argument
        callers get wrong most often, and both are reported exhaustively within
        their own kind.

        By default delivery is the transaction-bound ``MailHost`` send, so an
        aborted transaction sends nothing -- ``zope.sendmail`` joins a data manager
        to the current transaction and only talks to the MTA in ``tpc_finish``.
        """
        template = get_template(self.name)
        resolved = {
            field: recipient_sources.resolve(values)
            for field, values in self._recipients.items()
        }
        if not any(resolved.values()):
            raise RecipientError([
                f"{self.name} has no recipients; nothing would be sent and that "
                f"would be a silent drop"
            ])
        reply_to = recipient_sources.resolve(self._reply_to)
        parts = attachment_sources.resolve(self._attachments)
        sender = self._resolve_sender()

        mailhost = getUtility(IMailHost)
        default_language = recipient_sources.default_language()
        messages = []
        for language, fields in recipient_sources.group_by_language(
            resolved, default_language
        ):
            html, text = render(self.name, context=self._context, language=language)
            message = build_message(
                sender=sender,
                fields=fields,
                reply_to=reply_to,
                subject=self._resolve_subject(template, language),
                html=html,
                text=text,
                attachments=parts,
            )
            # No `mto`/`mfrom`: MailHost's own `_mungeHeaders` collects envelope
            # recipients from the To/Cc/Bcc headers and then deletes Bcc. Passing
            # `mto` would *overwrite* the To header with the full list -- Bcc
            # addresses included, in front of everyone.
            mailhost.send(message, immediate=immediate)
            logger.info(
                "Queued %s to %s recipient(s) in %r%s",
                self.name,
                sum(len(v) for v in fields.values()),
                language,
                " (immediate)" if immediate else "",
            )
            messages.append(message)
        return messages

    # -- internals ----------------------------------------------------------

    def _resolve_subject(self, template, language):
        """The subject for one language group: the override, else the registration.

        Both go through ``zope.i18n.translate``, which returns a plain string
        unchanged and translates a msgid into ``language`` -- so §6.2's "accepts a
        msgid or literal string" needs no branch here.
        """
        subject = self._subject if self._subject is not None else template.subject
        if subject is None:
            raise EmailkitError(
                f"{template.name} has no subject: its registration declares no "
                f"'subject' msgid (SPEC §4) and .subject() was not called. "
                f"Refusing to send a mail whose subject would read '[No Subject]'."
            )
        return zope_translate(subject, target_language=language)

    def _resolve_sender(self):
        """``From``: the ``.sender()`` override, else the site's configured sender.

        Failing here rather than letting ``MailHost`` raise
        ``"Message missing SMTP Header 'From'"``: that message is true but says
        nothing about *which* of the two registry records to go and fill in.
        """
        if self._sender is not None:
            return format_addresses(recipient_sources.resolve(self._sender))
        registry = queryUtility(IRegistry)
        address = name = None
        if registry is not None:
            address = registry.get("plone.email_from_address", None)
            name = registry.get("plone.email_from_name", None)
        if not address:
            raise EmailkitError(
                "No sender: 'plone.email_from_address' is not set in this site's "
                "registry (Site Setup -> Mail) and .sender() was not called."
            )
        return format_addresses([
            recipient_sources.Recipient(email=address, fullname=name or "")
        ])


def flatten(value):
    """Flatten one ``.to()``-style argument into a list of scalar values.

    §6.2 accepts "an email string, a Plone member object, a userid, or an iterable
    of those", nested freely -- ``.cc(meeting_managers)`` where that is a list of
    lists is nobody's mistake worth an exception.

    ``__iter__`` is the test, not ``__getitem__``: Zope objects are littered with
    ``__getitem__`` (it is how traversal works), so duck-typing on it would explode
    a content object into its children. Strings are scalars here even though they
    iterate, for obvious reasons; ``None`` flattens to nothing, so
    ``.cc(maybe_someone)`` needs no guard at the call site.
    """
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    if hasattr(value, "__iter__"):
        result = []
        for item in value:
            result.extend(flatten(item))
        return result
    return [value]


def format_addresses(recipients):
    """Render resolved recipients as one header value: ``Name <a@b.c>, …``.

    ``Address`` rather than ``email.utils.formataddr`` so that a display name
    containing a comma, a quote or a non-ASCII character is the header registry's
    problem and not ours -- the failure mode of getting this wrong by hand is a
    header that splits into two recipients.
    """
    return ", ".join(str(as_address(recipient)) for recipient in recipients)


def as_address(recipient):
    """One resolved recipient as an :class:`email.headerregistry.Address`."""
    username, _, domain = recipient.email.partition("@")
    return Address(
        display_name=recipient.fullname or "", username=username, domain=domain
    )


def build_message(sender, fields, reply_to, subject, html, text, attachments):
    """Assemble SPEC §6.2's message: ``set_content(text)`` then the HTML alternative.

    The result is ``multipart/alternative`` -- plaintext first, HTML second, which
    is the order that makes a text-only client show the text part -- wrapped in
    ``multipart/mixed`` by ``add_attachment`` as soon as there is one attachment.
    Attachments are identical across language groups (§6.2), so the same resolved
    bytes are reused for every message.

    ``policy.SMTP`` gives CRLF line endings, RFC 2047 headers, and a suitable
    transfer encoding per part; nothing here is hand-rolled and callers never see
    any of it.
    """
    message = EmailMessage(policy=SMTP_POLICY)
    message["From"] = sender
    for field, header in HEADERS.items():
        value = format_addresses(fields.get(field) or [])
        if value:
            message[header] = value
    if reply_to:
        message["Reply-To"] = format_addresses(reply_to)
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    for attachment in attachments:
        message.add_attachment(
            attachment.data,
            maintype=attachment.maintype,
            subtype=attachment.subtype,
            filename=attachment.filename,
        )
    return message
