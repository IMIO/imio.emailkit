"""``dummy.minimal`` -- the smallest add-on that ships an email template.

The floor. One template, a subject msgid, and nothing else: no ``preheader``, no
hand-authored ``.txt.pt`` twin, no ``directory`` attribute. Read it next to
``dummy.complete``, which turns every one of those on.

This module holds no registration at all -- it is a docstring. Everything a
consumer add-on needs to be discovered is the ``configure.zcml`` beside it, which
Zope's autoinclude already executes when the add-on is installed::

    <configure
        xmlns="http://namespaces.zope.org/zope"
        xmlns:emailkit="http://namespaces.imio.be/emailkit"
        i18n_domain="dummy.minimal"
        >

      <include package="imio.emailkit" file="meta.zcml" />

      <emailkit:templates>
        <emailkit:template
            name="notification"
            subject="[email_subject_notification] A notification from your commune"
            />
      </emailkit:templates>

    </configure>

The package that ZCML file belongs to is the **lookup namespace** -- this template
is reached as ``dummy.minimal:notification`` -- and the directive derives it from
the file's package rather than from an attribute, so it cannot lie.

**The i18n domain is the file's ``i18n_domain``**, and the subject msgid takes it
from there instead of from a hand-wired ``MessageFactory``. A real add-on ships a
``locales/`` directory for that domain; these dummies ship no catalogs, so every
msgid renders the default text after it -- which is also why that default is not
optional in practice: without it an untranslated subject reaches the inbox as the
bare msgid.

**No ``directory`` attribute** on purpose: it defaults to ``templates``, relative to
this package. State it only if you build somewhere else.

**No ``preheader``** on purpose: it is optional, and the kit layout collapses the
hidden preview div to nothing when it is absent. Ship one in real life -- every
inbox shows it -- but this add-on exists to show what the minimum is.

**No ``notification.txt.pt``** on purpose either. The hand-authored twin is the
primary plaintext path and naive extraction the documented fallback; this add-on
takes the fallback, logs the startup warning that comes with it, and its committed
``.txt`` snapshot is what that fallback actually produces. Compare it with
``dummy.complete``'s twin-backed one: the fallback loses the CTA URL.
"""
