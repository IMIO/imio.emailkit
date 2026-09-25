"""``dummy.complete`` -- a consumer add-on using every registration feature.

The ceiling, where ``dummy.minimal`` is the floor: two templates, a
``preheader`` on each, an explicit ``directory``, a hand-authored ``.txt.pt``
twin per template, and a template (``convocation``) that exercises the whole
kit component catalog plus ``tal:repeat`` and a locale helper.

The registration itself is in ``configure.zcml`` beside this module, run by
Zope's autoinclude when the add-on is installed. Its package is the lookup
namespace, so templates are reached as ``dummy.complete:convocation``, and
its ``i18n_domain`` is the msgid domain for ``subject``/``preheader``.

``notification`` is also registered by ``dummy.minimal`` and by
``imio.emailkit`` itself, with no clash: every lookup is namespaced. The bare
name ``notification`` resolves to none of them.

Packaging, for a real add-on: the compiled output ships in the sdist, the
Maizzle project does not::

    recursive-include src/dummy/complete/templates *.pt
    prune src/dummy/complete/emails
"""
