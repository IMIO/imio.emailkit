"""``dummy.minimal`` -- the smallest add-on that ships an email template (SPEC §4).

The floor. One template, a subject msgid, and nothing else: no ``preheader``, no
hand-authored ``.txt.pt`` twin, no ``directory`` key. Read it next to
``dummy.complete``, which turns every one of those on.

Everything a consumer add-on needs to be discovered is in this file plus one line
in ``setup.py``/``pyproject.toml``::

    [project.entry-points."imio.emailkit.templates"]
    "dummy.minimal" = "dummy.minimal:emailkit"

The left-hand side is the **lookup namespace** -- templates here are reached as
``dummy.minimal:notification`` -- and the right-hand side points at the dict below.
They are the same string in every sane registration, and ``imio.emailkit``
resolves the template directory from the right-hand one, so keep them equal.

**No ``directory`` key** on purpose: it defaults to ``templates``, relative to this
package, which is §4's layout. State it only if you build somewhere else.

**No ``preheader``** on purpose: it is optional, and the kit layout collapses the
hidden preview div to nothing when it is absent. Ship one in real life -- every
inbox shows it -- but this add-on exists to show what the minimum is.

**No ``notification.txt.pt``** on purpose either. §4 makes the hand-authored twin
the primary plaintext path and naive extraction the documented fallback; this
add-on takes the fallback, logs the startup warning that comes with it, and its
committed ``.txt`` snapshot is what that fallback actually produces. Compare it
with ``dummy.complete``'s twin-backed one: the fallback loses the CTA URL.
"""

from zope.i18nmessageid import MessageFactory


#: A real add-on's own i18n domain, with its own ``locales/`` directory. These
#: dummies ship no catalogs, so every msgid renders its ``default`` -- which is
#: also why ``default=`` is not optional in practice: without it an untranslated
#: subject reaches the inbox as the bare msgid.
_ = MessageFactory("dummy.minimal")


emailkit = {
    "templates": {
        "notification": {
            # SPEC §4: the subject lives in the registration as an i18n msgid and
            # is translated per recipient language at send time. Not in the
            # template, not in a metadata sidecar.
            "subject": _(
                "email_subject_notification",
                default="A notification from your commune",
            ),
        },
    },
}
