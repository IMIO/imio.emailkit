"""``dummy.minimal`` -- the smallest add-on that ships an email template.

The floor. One template, a subject msgid, and nothing else: no
``preheader``, no hand-authored ``.txt.pt`` twin, no ``directory``
attribute. Read it next to ``dummy.complete``, which turns every one of
those on.

The registration is in ``configure.zcml`` beside this module. Its package is
the lookup namespace, so the template is reached as
``dummy.minimal:notification``; its ``i18n_domain`` is the msgid domain,
and these dummies ship no catalogs, so every msgid renders its default text.

No twin: naive plaintext extraction is the fallback this add-on takes, and
its committed ``.txt`` snapshot is what that fallback produces. Compare with
``dummy.complete``'s twin-backed one: the fallback loses the CTA URL.
"""
