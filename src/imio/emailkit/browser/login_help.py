"""The username-reminder mail sent by Plone's login-help form.

Why this module exists at all, in one paragraph: the other two restyled default
mails are ``z3c.jbot`` overrides of real page templates on disk, but stock Plone
has **no template** for the username reminder. It is
``SEND_USERNAME_TEMPLATE`` -- a module-level i18n string at
``Products/CMFPlone/browser/login/login_help.py:33``, declared ``text/plain``,
interpolated with ``str.format()`` and handed straight to ``MailHost`` by
``RequestUsername.send_username()``. jbot keys on a resolved filename, and there
is no file, so the *view* is the only seam.

That is a strictly better position than the jbot mails are in, not a worse one:
because we own the view, the template speaks the flat dialect, renders through
``render()`` and goes out through the ``Email`` builder. It is therefore genuinely
discovered, golden-tested and previewable -- see the amended comment in
``imio/emailkit/__init__.py``.

Both classes below are bound to ``IEmailkitLayer`` in ``configure.zcml``, so
the opt-out profile still works: a site on the ``:base`` profile gets stock Plone's
view and stock Plone's plaintext mail.
"""

from imio.emailkit import Email
# Plone's factory, not ours, for the one message below: it is stock Plone's own
# string and Plone already ships it translated. Re-declaring it in the
# `imio.emailkit` domain would make us re-translate FR/NL/DE for no gain and would
# drift from whatever Plone says in the languages we do not ship.
from plone.base import PloneMessageFactory as _plone
from Products.CMFPlone.browser.login import login_help as stock
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from smtplib import SMTPRecipientsRefused
from zope.component import getMultiAdapter

import os


#: The registered template this view renders. Namespaced, like every discovered
#: template name.
TEMPLATE_NAME = "imio.emailkit:get_username"

#: Stock Plone's login-help *form* template, reused verbatim by absolute path.
#:
#: The form markup is not ours and there is no reason to fork it -- this module
#: changes which mail goes out, not what the page looks like. Registering our
#: class without a ``template=`` in ZCML means the class has to supply ``index``
#: itself (``LoginHelpForm.render`` returns ``self.index()``), which is what the
#: assignment below does.
#:
#: Keeping it a real ``ViewPageTemplateFile`` over Plone's own path also keeps the
#: page jbot-overridable: jbot patches ``ViewPageTemplateFile.__get__`` and keys on
#: the resolved filename, so a site that already overrides
#: ``Products.CMFPlone.browser.login.templates.login_help.pt`` keeps winning.
STOCK_LOGIN_HELP_TEMPLATE = os.path.join(
    os.path.dirname(stock.__file__), "templates", "login_help.pt"
)


class RequestUsername(stock.RequestUsername):
    """Stock's username subform, sending the styled mail instead of the flat one.

    Everything about *when* the mail is sent, and the anti-enumeration behaviour
    around it, is inherited untouched from ``handleGetUsername``: an address with
    no match and an address with several matches both log and send nothing, and
    all three outcomes emit the same status message. That is deliberate -- it
    stops the form being used to probe for registered addresses -- and it is
    asserted in ``tests/test_get_username.py``. Do not "improve" it into helpful
    error reporting.
    """

    def send_username(self, portal, userinfo):
        """Send the styled reminder. Same signature and same contract as stock.

        ``immediate=True`` matches stock, and not only for parity: the
        ``SMTPRecipientsRefused`` clause below exists to avoid disclosing an
        address, and with the default transaction-bound delivery the SMTP
        conversation happens in ``tpc_finish`` -- long after any ``except`` here
        could run. So the paranoia handling and immediate delivery are one
        decision, not two.
        """
        portal_state = getMultiAdapter(
            (portal, self.request), name="plone_portal_state"
        )
        # The *member*, not ``userinfo["userid"]``. The ``str`` recipient adapter reads
        # any string containing "@" as an address and never looks a member up
        # (recipients.py, "A ``str`` containing ``@`` is an address, full stop"),
        # so a site whose userids happen to look like addresses -- a migration
        # artefact, not just ``use_email_as_login`` -- would have the userid
        # delivered *as* the address. The member object has no such ambiguity and
        # carries the language preference that the builder groups by.
        member = portal.portal_membership.getMemberById(userinfo["userid"])
        recipient = member if member is not None else userinfo["email"]

        try:
            (
                Email(TEMPLATE_NAME)
                .to(recipient)
                .with_context(
                    # ``title`` is PAS's full-name key. Falling back to the login
                    # keeps the greeting from reading "Dear ," for a member who
                    # never filled in a fullname.
                    fullname=userinfo["title"] or userinfo["login"],
                    login=userinfo["login"],
                    site_name=portal_state.navigation_root_title(),
                    login_url=f"{portal_state.navigation_root_url()}/login",
                    # Bugfix carried over from stock Plone, pinned by
                    # ``TestClientAddressSemantics`` in the test suite: stock
                    # Plone's ``request/HTTP_X_FORWARDED_FOR|request/REMOTE_ADDR``
                    # renders EMPTY without an ``X-Forwarded-For`` header, because
                    # ``HTTPRequest.get`` returns '' for a missing ``HTTP_`` key
                    # rather than raising and TAL's ``|`` only falls through on an
                    # error. ``getClientAddr`` is Zope's supported API; it needs
                    # ``trusted-proxy`` in zope.conf behind a reverse proxy, which
                    # the README documents.
                    client_addr=self.request.getClientAddr(),
                )
                .send(immediate=True)
            )
        except SMTPRecipientsRefused:
            # Don't disclose the email address on failure -- stock's behaviour,
            # deliberately preserved. `from None` suppresses the original, which
            # would otherwise put the rejected address in the traceback and undo
            # the very thing this clause is for.
            raise SMTPRecipientsRefused(
                _plone("Recipient address rejected by server.")
            ) from None
        # Stock also has `except SMTPException as e: raise (e)`. That is a no-op
        # re-raise, so it is dropped rather than copied: every other SMTP error
        # propagates unchanged either way.


class LoginHelpForm(stock.LoginHelpForm):
    """Stock's login-help form, wired to the :class:`RequestUsername` above.

    ``update()`` is **reimplemented rather than extended**, and that is forced
    rather than chosen. Stock instantiates ``RequestUsername`` by direct class
    reference (``login_help.py:243``) -- no ZCA lookup to override -- and the mail
    is sent inside the subform's own ``update()``, so by the time
    ``super().update()`` returned the stock plaintext mail would already be on the
    wire. There is no seam.

    The alternative, temporarily rebinding ``stock.RequestUsername`` around a
    ``super().update()`` call, is a monkeypatch with a race: Zope's publisher is
    threaded and two concurrent login-help requests would see each other's
    rebind. Twelve forked lines with a drift test is the cheaper failure mode.

    The drift test is ``test_stock_update_is_what_we_forked_from`` in
    ``tests/test_get_username.py``, which pins the source of stock ``update()``.
    When a Plone upgrade trips it, re-read the upstream method and re-fork it
    here; do not weaken the test.
    """

    index = ViewPageTemplateFile(STOCK_LOGIN_HELP_TEMPLATE)

    def update(self):
        # Forked from Products.CMFPlone.browser.login.login_help.LoginHelpForm
        # (Plone 6). The ONLY intended difference is that the username subform is
        # this module's RequestUsername. Keep it a recognisable copy -- the drift
        # test compares against upstream, and a cleverer rewrite makes the next
        # comparison harder for no gain.
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
        # `form.EditForm.update`, i.e. two classes up: `stock.LoginHelpForm` is
        # exactly the method being replaced, so `super()` would recurse into it.
        super(stock.LoginHelpForm, self).update()

        # `use_email_as_login()` is inherited untouched. Its consequence is worth
        # knowing and is NOT a defect in this module: when it is True stock hides
        # the username subform entirely, so this mail is never sent -- inert, not
        # broken. Both registry states are covered in tests/test_get_username.py.
