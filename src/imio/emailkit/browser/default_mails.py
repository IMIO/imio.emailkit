"""Plone's two default mails, rendered through ``render()`` like the rest.

``RegistrationTool.mailPassword`` and ``.registeredNotify`` parse ``Subject``,
``To``, ``From`` and ``Content-Type`` back out of the return value and hand
the whole string to ``MailHost.send``. So the return value must be an RFC822
document, headers included, built here from data: single-part
``text/html``, since the plaintext half of ``render()`` would otherwise be
ours to assemble into a ``multipart/alternative`` and stock's to mishandle.

Subclasses ``PasswordResetToolView`` so ``encoded_mail_sender``,
``construct_url``, ``expiration_timeout`` and ``portal_state`` stay stock's.
The kwargs each tool passes are pinned by
``tests/test_default_mails.py::test_stock_kwargs_are_what_we_build_from``;
when a Plone upgrade trips it, update :meth:`build_context`.

Both views are bound to ``IEmailkitLayer``: a ``:base`` site gets stock
Plone's views and mails.
"""

from imio.emailkit.discovery import get_template
from imio.emailkit.interfaces import IEmailRecipient
from imio.emailkit.render import negotiated_language
from imio.emailkit.render import render
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.browser.login.password_reset import PasswordResetToolView
from zope.i18n import translate as zope_translate


#: The RFC822 preamble ``RegistrationTool`` parses back out of the return value.
#: ``Precedence: bulk`` keeps vacation auto-responders from answering a
#: password reset.
HEADER_BLOCK = (
    "From: {sender}\n"
    "To: {recipient}\n"
    "Subject: {subject}\n"
    "Content-Type: text/html; charset=utf-8\n"
    "Precedence: bulk\n"
    "\n"
)


def recipient_language(member):
    """The language to render a default mail to ``member`` in.

    Uses ``IEmailRecipient``, so it resolves the language by the same rule
    :mod:`imio.emailkit.recipients` applies for every other mail.
    """
    recipient = IEmailRecipient(member, None)
    language = getattr(recipient, "language", None)
    return language or negotiated_language()


class DefaultMailView(PasswordResetToolView):
    """Render one registered template and return it as an RFC822 document.

    Subclasses supply :attr:`template_name` and :meth:`build_context`.
    """

    #: Namespaced name of the template this view renders.
    template_name = None

    def build_context(self, **kwargs):
        """The flat ``render()`` context, from the kwargs the tool passed."""
        raise NotImplementedError

    def __call__(self, **kwargs):
        member = kwargs["member"]
        language = recipient_language(member)
        html, _text = render(
            self.template_name, context=self.build_context(**kwargs), language=language
        )
        return self.header_block(member, language) + html

    def header_block(self, member, language):
        """The headers ``RegistrationTool`` parses back out.

        The subject is the template's registration msgid, translated into the
        recipient's language.
        """
        subject = zope_translate(
            get_template(self.template_name).subject, target_language=language
        )
        return HEADER_BLOCK.format(
            sender=self.encoded_mail_sender(),
            recipient=member.getProperty("email"),
            subject=subject,
        )


class MailPasswordView(DefaultMailView):
    """``@@mail_password_template`` -- the password-reset mail.

    Called by ``RegistrationTool.mailPassword`` with ``member``, ``reset``,
    ``password`` and ``charset``. ``password`` is unused: the mail carries a
    reset link, never a password. ``charset`` is fixed at utf-8 in
    :data:`HEADER_BLOCK`.
    """

    template_name = "imio.emailkit:mail_password_template"

    def build_context(self, member=None, reset=None, **stock_kwargs):
        portal_state = self.portal_state()
        return {
            "userid": member.getId(),
            "site_name": portal_state.navigation_root_title(),
            # An administrator resetting somebody else's password gets a
            # different opening paragraph.
            "is_anonymous": portal_state.anonymous(),
            "reset_url": self.construct_url(reset["randomstring"]),
            "expiration_hours": self.expiration_timeout(),
            # `getClientAddr`, not the raw `X-Forwarded-For` header: reading
            # the header directly would let the sender choose the IP address
            # the mail names. Needs `trusted-proxy` in zope.conf.
            "client_addr": self.request.getClientAddr(),
        }


class RegisteredNotifyView(DefaultMailView):
    """``@@registered_notify_template`` -- the "an account was created for you" mail.

    Called by ``RegistrationTool.registeredNotify`` with ``member``, ``reset``,
    ``email`` and ``charset``. ``email`` is unused: the ``To`` header is built
    from the member, which also resolves the recipient's language.
    """

    template_name = "imio.emailkit:registered_notify_template"

    def build_context(self, member=None, email=None, reset=None, **stock_kwargs):
        # `registeredNotify` always passes `reset`; other `for="*"` callers may not.
        if reset is None:
            tool = getToolByName(self.context, "portal_password_reset")
            reset = tool.requestReset(member.getId())
        username = member.getUserName()
        return {
            "fullname": member.getProperty("fullname") or username,
            "username": username,
            "email": email or member.getProperty("email") or "",
            "password_url": (
                f"{self.construct_url(reset['randomstring'])}?userid={username}"
            ),
            "expires": as_datetime(reset["expires"]),
            "email_from_name": self.context.portal_registry["plone.email_from_name"],
        }


def as_datetime(value):
    """A Zope ``DateTime`` as a standard ``datetime``; anything else untouched.

    ``portal_password_reset`` hands out Zope ``DateTime`` instances, which the
    kit's locale helpers do not understand.
    """
    converter = getattr(value, "asdatetime", None)
    return converter() if converter is not None else value
