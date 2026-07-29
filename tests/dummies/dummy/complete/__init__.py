"""``dummy.complete`` -- a consumer add-on using every §4 feature.

The ceiling, where ``dummy.minimal`` is the floor: two templates, a ``preheader``
on each, an explicit ``directory``, a hand-authored ``.txt.pt`` twin per template,
and a template (``convocation``) that exercises the whole kit component catalog
plus ``tal:repeat`` and a locale helper.

Its entry point, in ``pyproject.toml``::

    [project.entry-points."imio.emailkit.templates"]
    "dummy.complete" = "dummy.complete:emailkit"

**Note the template basename.** ``notification`` is *also* registered by
``dummy.minimal`` **and** by ``imio.emailkit`` itself. There is no clash, because
§4 namespaces every lookup: ``dummy.complete:notification``,
``dummy.minimal:notification`` and ``imio.emailkit:notification`` are three
different templates in three different files. The bare name ``notification``
resolves to none of them, on purpose -- accepting it would make which one you get
depend on entry-point scan order.

Packaging, for a real add-on (SPEC §4): the compiled output is committed and must
ship in the sdist, while the Maizzle project must not::

    recursive-include src/dummy/complete/templates *.pt
    prune src/dummy/complete/emails
"""

from zope.i18nmessageid import MessageFactory


_ = MessageFactory("dummy.complete")


emailkit = {
    # Stated explicitly here, though ``templates`` is also the default. State it
    # when you want the reader of the registration to see where the build output
    # lands without going to look at the Maizzle config.
    "directory": "templates",
    "templates": {
        "convocation": {
            "subject": _(
                "email_subject_convocation",
                default="Convocation to the municipal council",
            ),
            # SPEC §4: the hidden inbox-preview line next to the subject. The
            # highest-visibility email feature that everyone forgets -- every
            # inbox shows it, and left out the client fills it with whatever body
            # copy comes first. Keep it short: clients cut around 100 characters.
            "preheader": _(
                "email_preheader_convocation",
                default="Agenda and documents for the session of 12 August.",
            ),
        },
        "notification": {
            "subject": _(
                "email_subject_notification",
                default="An update on your file",
            ),
            "preheader": _(
                "email_preheader_notification",
                default="One of your files has moved forward.",
            ),
        },
    },
}
