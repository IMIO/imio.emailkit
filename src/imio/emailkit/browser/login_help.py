"""The username-reminder mail sent by Plone's login-help form.

Stock Plone has no template for the username reminder: it is a plain string
handed straight to ``MailHost`` by ``RequestUsername.send_username()``. There
is no file for ``z3c.jbot`` to key on, so the view is the only seam.

Both classes below are bound to ``IEmailkitLayer`` in ``configure.zcml``: a
``:base`` site gets stock Plone's view and plaintext mail.
"""

from imio.emailkit import Email

# Stock Plone's own factory: the message below is stock's string, already
# translated FR/NL/DE.
from plone.base import PloneMessageFactory as _plone
from Products.CMFPlone.browser.login import login_help as stock
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from smtplib import SMTPRecipientsRefused
from zope.component import getMultiAdapter

import os


#: The registered template this view renders.
TEMPLATE_NAME = "imio.emailkit:get_username"

#: Stock Plone's login-help form template, reused verbatim by absolute path:
#: this module changes which mail goes out, not what the page looks like. A
#: real ``ViewPageTemplateFile`` keeps the page jbot-overridable.
STOCK_LOGIN_HELP_TEMPLATE = os.path.join(
    os.path.dirname(stock.__file__), "templates", "login_help.pt"
)


class RequestUsername(stock.RequestUsername):
    """Stock's username subform, sending the styled mail instead of the flat one.

    ``handleGetUsername``'s anti-enumeration behaviour is inherited
    untouched: no match, several matches, and success all emit the same
    status message, so the form cannot be used to probe for addresses. Do
    not change it into helpful error reporting.
    """

    def send_username(self, portal, userinfo):
        """Send the styled reminder. Same signature and contract as stock.

        ``immediate=True`` is required: with the default transaction-bound
        delivery, the SMTP conversation happens in ``tpc_finish``, long after
        the ``SMTPRecipientsRefused`` clause below could run.
        """
        portal_state = getMultiAdapter(
            (portal, self.request), name="plone_portal_state"
        )
        # The member, not `userinfo["userid"]`: a userid that looks like an
        # address would otherwise be delivered to as one.
        member = portal.portal_membership.getMemberById(userinfo["userid"])
        recipient = member if member is not None else userinfo["email"]

        try:
            (
                Email(TEMPLATE_NAME)
                .to(recipient)
                .with_context(
                    # The login fallback avoids "Dear ," for a member with
                    # no fullname.
                    fullname=userinfo["title"] or userinfo["login"],
                    login=userinfo["login"],
                    site_name=portal_state.navigation_root_title(),
                    login_url=f"{portal_state.navigation_root_url()}/login",
                    # `getClientAddr` needs `trusted-proxy` in zope.conf
                    # behind a reverse proxy; see the README.
                    client_addr=self.request.getClientAddr(),
                )
                .send(immediate=True)
            )
        except SMTPRecipientsRefused:
            # Do not disclose the email address on failure. `from None` keeps
            # the rejected address out of the traceback.
            raise SMTPRecipientsRefused(
                _plone("Recipient address rejected by server.")
            ) from None


class LoginHelpForm(stock.LoginHelpForm):
    """Stock's login-help form, wired to the :class:`RequestUsername` above.

    ``update()`` is reimplemented, not extended: stock instantiates
    ``RequestUsername`` by direct class reference and sends the mail inside
    the subform's own ``update()``, before ``super().update()`` could return.

    ``test_stock_update_is_what_we_forked_from`` pins the source of stock
    ``update()``. When a Plone upgrade trips it, re-fork it here.
    """

    index = ViewPageTemplateFile(STOCK_LOGIN_HELP_TEMPLATE)

    def update(self):
        # Forked from stock.LoginHelpForm. The only intended difference is
        # the RequestUsername subform below; the drift test compares this
        # against upstream, so keep it a recognisable copy.
        subforms = []
        if self.can_reset_password():
            form = stock.RequestResetPassword(None, self.request)
            form.update()
            subforms.append(form)
        if not self.use_email_as_login() and self.can_retrieve_username():
            form = RequestUsername(None, self.request)  # <-- the one change
            form.update()
            subforms.append(form)

        self.subforms = subforms
        # `stock.LoginHelpForm` is the method being replaced, so `super()`
        # must skip it and call two classes up.
        super(stock.LoginHelpForm, self).update()

        # When `use_email_as_login()` is True, stock hides the username
        # subform, so this mail is never sent.
