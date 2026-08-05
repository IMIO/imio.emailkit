"""``dummy.complete`` -- a consumer add-on using every registration feature.

The ceiling, where ``dummy.minimal`` is the floor: two templates, a ``preheader``
on each, an explicit ``directory``, a hand-authored ``.txt.pt`` twin per template,
and a template (``convocation``) that exercises the whole kit component catalog
plus ``tal:repeat`` and a locale helper.

There is no Python registration to read here: the templates are declared in
``configure.zcml`` beside this module, and Zope's autoinclude executes it when the
add-on is installed. That file is the thing to read::

    <configure
        xmlns="http://namespaces.zope.org/zope"
        xmlns:emailkit="http://namespaces.imio.be/emailkit"
        i18n_domain="dummy.complete"
        >

      <include package="imio.emailkit" file="meta.zcml" />

      <emailkit:templates directory="templates">
        <emailkit:template
            name="convocation"
            subject="[email_subject_convocation] Convocation to the municipal council"
            preheader="[email_preheader_convocation] Agenda and documents ..."
            />
      </emailkit:templates>

    </configure>

The package the ZCML file belongs to is the **lookup namespace** -- templates here
are reached as ``dummy.complete:convocation`` -- and the consumer never spells it
out, so it cannot disagree with reality. The msgid domain of ``subject`` and
``preheader`` is the file's ``i18n_domain``, which is why no ``MessageFactory``
appears in this module.

**Note the template basename.** ``notification`` is *also* registered by
``dummy.minimal`` **and** by ``imio.emailkit`` itself. There is no clash, because
every lookup is namespaced: ``dummy.complete:notification``,
``dummy.minimal:notification`` and ``imio.emailkit:notification`` are three
different templates in three different files. The bare name ``notification``
resolves to none of them, on purpose -- accepting it would make which one you get
depend on the order the three packages' ZCML happens to execute in.

Packaging, for a real add-on: the compiled output is committed and must ship in the
sdist, while the Maizzle project must not::

    recursive-include src/dummy/complete/templates *.pt
    prune src/dummy/complete/emails
"""
