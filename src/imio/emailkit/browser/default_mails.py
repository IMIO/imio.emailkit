"""Plone's two default mails, rendered through ``render()`` like the rest.

These two used to be ``z3c.jbot`` overrides of stock Plone's page templates, and
that made them the package's only second-class citizens: a stock view rendered
them, so they spoke that view's dialect (``options/member``,
``python:member.getProperty('email')``, no locale helpers, no ``theme``), they
could not be registered for discovery, and therefore they never appeared in
``bin/preview-emails`` or ``@@emailkit-preview``. The claim that the default
mails are "authored, compiled, discovered, tested and shipped exactly like
consumer templates" was true for everything except *discovered*.

Owning the view removes the exception rather than documenting it. This is not a
new mechanism: :mod:`imio.emailkit.browser.login_help` has done exactly this for
``get_username`` since the beginning, and its docstring already says why -- "because
we own the view, the template speaks the flat dialect, renders through ``render()``
and goes out through the ``Email`` builder. It is therefore genuinely discovered,
golden-tested and previewable." The same reasoning applies here; the only reason
these two were different is that jbot *could* reach them, not that it should.

What the consumer sees now: three registered templates in the ordinary dialect,
one preview list, one set of authoring rules. The Plone machinery -- which kwargs
the tool passes, which header block it parses back out -- is hidden in this module,
which is where "hide the ugly stuff" belongs.

---------------------------------------------------------------------------
The one piece of machinery that cannot move: the header block
---------------------------------------------------------------------------
``RegistrationTool.mailPassword`` and ``.registeredNotify`` do not send what we
return. They call ``message_from_string(mail_text.strip())`` on it, pull ``Subject``,
``To``, ``From`` and ``Content-Type`` back out, and hand the *whole string* to
``MailHost.send`` with those as arguments. So the return value has to be an RFC822
document, headers included, or the mail goes out with no subject and no recipient.

That block used to live in the templates, emitted through Maizzle's ``useDoctype()``
with ``tal:omit-tag=""`` on every span -- one forgotten attribute away from shipping
``Subject: <span>Password reset request</span>``. It is now built here, in one
place, from data. The subject comes from the template's registration like every
other subject in the package, which is the single biggest thing this change buys:
it is a msgid in ZCML, not markup in a template.

``Content-Type: text/html`` single-part, exactly as stock Plone does. The tool is
what talks to ``MailHost``, so a ``multipart/alternative`` here would be ours to
assemble and stock's to mis-handle; the plaintext half of ``render()`` is therefore
discarded for these two, and the twins exist for the preview and for completeness
rather than for delivery.

---------------------------------------------------------------------------
Coupling to stock Plone
---------------------------------------------------------------------------
We subclass ``PasswordResetToolView`` rather than reimplementing it, so
``encoded_mail_sender``, ``construct_url``, ``expiration_timeout`` and
``portal_state`` stay stock's. What we own is ``__call__`` and the context we build
for it. The kwargs each tool passes are pinned by
``tests/test_default_mails.py::test_stock_kwargs_are_what_we_build_from``; when a
Plone upgrade trips it, re-read the call site and update :meth:`build_context`. Do
not weaken the test -- it is the same drift guard ``login_help.py`` carries.

Both views are bound to ``IEmailkitLayer`` in ``configure.zcml``, so the
``:base`` opt-out still works exactly as before: a site that installs ``:base``
gets stock Plone's views and stock Plone's mails.
"""

from imio.emailkit.discovery import get_template
from imio.emailkit.interfaces import IEmailRecipient
from imio.emailkit.render import negotiated_language
from imio.emailkit.render import render
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.browser.login.password_reset import PasswordResetToolView
from zope.i18n import translate as zope_translate


#: The RFC822 preamble ``RegistrationTool`` parses back out of our return value.
#: ``Precedence: bulk`` is stock Plone's, kept: it is what keeps vacation
#: auto-responders from answering a password reset.
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

    Through ``IEmailRecipient`` rather than ``member.getProperty('language')``
    directly, so these two mails resolve a recipient's language by exactly the
    rule :mod:`imio.emailkit.recipients` applies for every other mail -- including
    its treatment of the empty ``language`` property as "no preference".
    """
    recipient = IEmailRecipient(member, None)
    language = getattr(recipient, "language", None)
    return language or negotiated_language()


class DefaultMailView(PasswordResetToolView):
    """Render one registered template and return it as an RFC822 document.

    Subclasses supply :attr:`template_name` and :meth:`build_context`; everything
    that touches Plone's calling convention lives here.
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
        recipient's language -- the same value ``Email`` would use for a
        registered template, resolved the same way.
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
    ``password`` and ``charset``. ``password`` is stock's and is deliberately
    unused: the mail carries a reset link, never a password. ``charset`` is fixed
    at utf-8 in :data:`HEADER_BLOCK`, as the stock template also hardcoded it.
    """

    template_name = "imio.emailkit:mail_password_template"

    def build_context(self, member=None, reset=None, **stock_kwargs):
        portal_state = self.portal_state()
        return {
            "userid": member.getId(),
            "site_name": portal_state.navigation_root_title(),
            # Stock's template branches on this: an administrator resetting
            # somebody else's password gets a different opening paragraph from a
            # visitor who used the forgotten-password form.
            "is_anonymous": portal_state.anonymous(),
            "reset_url": self.construct_url(reset["randomstring"]),
            "expiration_hours": self.expiration_timeout(),
            # `getClientAddr`, not stock's `HTTP_X_FORWARDED_FOR | REMOTE_ADDR`:
            # that chain renders empty with no X-Forwarded-For header, because
            # HTTPRequest.get returns '' for a missing HTTP_ key rather than
            # raising, and TAL's `|` only falls through on an error. Zope's
            # accessor also refuses to trust a client-settable header unless the
            # proxy is declared `trusted-proxy` in zope.conf, which the README
            # documents. Reading the raw header would let the sender choose which
            # IP address this mail names.
            "client_addr": self.request.getClientAddr(),
        }


class RegisteredNotifyView(DefaultMailView):
    """``@@registered_notify_template`` -- the "an account was created for you" mail.

    Called by ``RegistrationTool.registeredNotify`` with ``member``, ``reset``,
    ``email`` and ``charset``. ``email`` is stock's and is unused here: the
    ``To`` header is built from the member, which is the same address and is also
    what resolves the recipient's language.
    """

    template_name = "imio.emailkit:registered_notify_template"

    def build_context(self, member=None, email=None, reset=None, **stock_kwargs):
        # `registeredNotify` always passes `reset`, but the same view is
        # registered `for="*"` and other callers do not. Stock's template carried
        # the same fallback; it costs nothing when the value is already there.
        if reset is None:
            tool = getToolByName(self.context, "portal_password_reset")
            reset = tool.requestReset(member.getId())
        username = member.getUserName()
        return {
            # The login rather than "Hello ," for a member with no fullname.
            "fullname": member.getProperty("fullname") or username,
            "username": username,
            # `registeredNotify` reads this off the member and passes it on, so
            # taking the kwarg is taking the same value stock validated before it
            # decided to send at all. The fallback is for the other callers the
            # `for="*"` registration allows, which pass no `email`.
            "email": email or member.getProperty("email") or "",
            "password_url": (
                f"{self.construct_url(reset['randomstring'])}?userid={username}"
            ),
            # A real datetime, formatted by the template through the kit's
            # `format_datetime` helper -- which `render()` binds to the recipient's
            # language. Stock used `context.toLocalizedTime`, which follows the
            # *request*, so a mail rendered for a Dutch member carried a French
            # date whenever a French visitor triggered it.
            "expires": as_datetime(reset["expires"]),
            "email_from_name": self.context.portal_registry["plone.email_from_name"],
        }


def as_datetime(value):
    """A Zope ``DateTime`` as a standard ``datetime``; anything else untouched.

    ``portal_password_reset`` hands out Zope ``DateTime`` instances, which the
    kit's locale helpers (and CLDR under them) do not understand.
    """
    converter = getattr(value, "asdatetime", None)
    return converter() if converter is not None else value
