"""The ``Email`` builder.

.. code-block:: python

    Email("imio.pm.notifications:item_published") \\
        .to(member).to("greffe@commune.be").cc(meeting_managers) \\
        .reply_to("noreply@imio.be").with_context(item=item, meeting=meeting) \\
        .attach(convocation_pdf, filename="convocation.pdf").send()

**This API is frozen**: exactly nine methods, each setting a field and
returning ``self``. Everything that can fail happens inside
:meth:`Email.send`.
"""

from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP as SMTP_POLICY
from email.utils import parseaddr
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

#: Recipient fields grouped by language, each becoming a message header.
#: ``MailHost`` strips the ``Bcc`` header after reading envelope recipients
#: from it, so ``send()`` never passes ``mto`` explicitly.
RECIPIENT_FIELDS = ("to", "cc", "bcc")

#: Header name per recipient field.
HEADERS = {"to": "To", "cc": "Cc", "bcc": "Bcc"}


class Email:
    """Collect the parts of one styled mail, then send it.

    :param name: namespaced template name, e.g.
        ``"imio.pm.notifications:item_published"``

    The template is not looked up here: ``TemplateNotFound`` raises only
    from :meth:`send`.
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

        ``MailHost`` removes the ``Bcc`` header after it reads the envelope
        recipients from it. Blind means blind.
        """
        self._recipients["bcc"].extend(flatten(value))
        return self

    def reply_to(self, value):
        """Set the ``Reply-To`` addresses. Same accepted values as :meth:`to`."""
        self._reply_to.extend(flatten(value))
        return self

    def sender(self, value):
        """Override the ``From`` address. Same accepted values as :meth:`to`;
        omitted, ``From`` is the site's configured sender.
        """
        self._sender = flatten(value)
        return self

    def subject(self, value):
        """Override the subject: an i18n msgid or literal string. Omitted, the
        subject is the msgid in the template's registration.
        """
        self._subject = value
        return self

    def with_context(self, **context):
        """Add names to the render context, as ``render()`` takes them."""
        self._context.update(context)
        return self

    def attach(self, source, filename=None, mimetype=None):
        """Add an attachment. Callable repeatedly, order preserved.

        ``source`` is raw ``bytes``, a filesystem path, an open binary file, a
        ``NamedFile``/``NamedBlobFile`` value, or a Plone File/Image content
        object. ``filename`` and ``mimetype`` are required for ``bytes``, else
        inferred. Nothing is read until :meth:`send`.
        """
        self._attachments.append((source, filename, mimetype))
        return self

    # -- the one method that does anything ----------------------------------

    def send(self, immediate=False):
        """Resolve, render per language group, and hand each message to ``MailHost``.

        :param immediate: bypass the transaction and send now.
        :returns: the built :class:`~email.message.EmailMessage` objects.
        :raises TemplateNotFound: no template registered under :attr:`name`
        :raises RecipientError: any recipient could not be resolved
        :raises AttachmentError: any attachment could not be resolved

        Recipients and attachments resolve before any render. Delivery is
        transaction-bound by default.
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

        # Build every group before sending any of them. With `immediate=True`
        # there is no transaction to undo a partial run: a later template
        # error must not leave an earlier mail already sent.
        groups = []
        for language, fields in recipient_sources.group_by_language(
            resolved, recipient_sources.default_language()
        ):
            html, text = render(self.name, context=self._context, language=language)
            groups.append((
                language,
                fields,
                build_message(
                    sender=sender,
                    fields=fields,
                    reply_to=reply_to,
                    subject=self._resolve_subject(template, language),
                    html=html,
                    text=text,
                    attachments=parts,
                ),
            ))

        mailhost = getUtility(IMailHost)
        for language, fields, message in groups:
            # No `mto`: MailHost's `_mungeHeaders` reads envelope recipients
            # from the To/Cc/Bcc headers, then deletes Bcc. Passing `mto`
            # would overwrite the To header, exposing Bcc addresses.
            mailhost.send(message, immediate=immediate)
            logger.info(
                "%s %s to %s recipient(s) in %r",
                "Sent" if immediate else "Queued",
                self.name,
                sum(len(v) for v in fields.values()),
                language,
            )
        return [message for _, _, message in groups]

    # -- internals ----------------------------------------------------------

    def _resolve_subject(self, template, language):
        """The subject for one language group: the override, else the registration."""
        subject = self._subject if self._subject is not None else template.subject
        if subject is None:
            raise EmailkitError(
                f"{template.name} has no subject: its registration declares no "
                f"'subject' msgid and .subject() was not called. "
                f"Refusing to send a mail whose subject would read '[No Subject]'."
            )
        return zope_translate(subject, target_language=language)

    def _resolve_sender(self):
        """``From``: the ``.sender()`` override, else the site's configured sender."""
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

    Accepts an email string, a Plone member, a userid, or a nested
    iterable of those; ``None`` flattens to nothing. Tests ``__iter__``,
    not ``__getitem__``, since Zope content objects use the latter for
    traversal.
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

    Uses ``Address``, not ``email.utils.formataddr``, to escape names safely.
    """
    return ", ".join(str(as_address(recipient)) for recipient in recipients)


def as_address(recipient):
    """One resolved recipient as an :class:`email.headerregistry.Address`.

    Parses with ``parseaddr``: a member's ``email`` property is free text,
    so a name embedded in it must be split out first.
    """
    display_name, address = parseaddr(recipient.email)
    username, _, domain = address.rpartition("@")
    return Address(
        display_name=recipient.fullname or display_name,
        username=username,
        domain=domain,
    )


def build_message(sender, fields, reply_to, subject, html, text, attachments):
    """Assemble the message: ``set_content(text)`` then the HTML alternative.

    Plaintext first, HTML second, in ``multipart/alternative``: a
    text-only client then shows the text part.
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
