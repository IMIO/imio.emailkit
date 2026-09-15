"""The two silent failure modes that would make every override test a lie.

Phase 0 found both, and both produce a *successful* run with plausible output:

1. **Caveat D1.** ``<include package="z3c.jbot" file="meta.zcml"/>`` registers the
   ``browser:jbot`` *directive* only. The ``ViewPageTemplateFile.__get__``
   monkeypatches live in ``z3c.jbot/configure.zcml``. With ``meta.zcml`` alone the
   directive parses, the ``TemplateManager`` is built with the **correct** path
   mapping, and the stock template still renders -- no error, no warning. In a
   real instance ``z3c.autoinclude`` hides the mistake; ``PLONE_FIXTURE`` disables
   autoinclude, so it is visible here and nowhere else.
2. **The engine swap.** Without the ``IPageTemplateEngine`` utility,
   ``zope.pagetemplate`` falls back to ``zope.tal``, where ``${...}`` passes
   through verbatim with no error while ``tal:repeat`` keeps working.

So this module asserts the *machinery*, and every other override module asserts
*rendered output*. Neither is sufficient alone: (1) makes a filename assertion
meaningless, (2) makes a marker assertion meaningless.
"""

import support


support.require_runtime()


class TestPageTemplateEngine:
    def test_engine_is_chameleon_not_zope_tal(self, portal):
        """Guard the ``${...}`` interpolation the whole suite depends on.

        ``portal`` is requested only to force the layer -- and therefore its ZCA
        registry -- to be set up.
        """
        from zope.component import queryUtility
        from zope.pagetemplate.interfaces import IPageTemplateEngine

        engine = queryUtility(IPageTemplateEngine)

        assert engine is not None, (
            "no IPageTemplateEngine utility: zope.pagetemplate will fall back to "
            "zope.tal and ship ${...} verbatim"
        )
        assert engine.__module__ == "Products.PageTemplates.engine"


class TestJbotPatchesAreLoaded:
    """These patches are installed by ``z3c.jbot/configure.zcml``.

    The add-on's own ``configure.zcml`` must include the whole ``z3c.jbot``
    package -- the test layer deliberately does not load it, so a regression to
    ``file="meta.zcml"`` fails here instead of silently disabling every override.

    There is deliberately no ``TemplateManager`` assertion any more. This package
    registers no ``browser:jbot`` directory since ``browser/default_mails.py``
    took the two stock views over, so there is no directory of ours to wire. The
    include is still required, and in the less obvious direction: the patches
    below are what ``render()._page_template`` invokes so that a *consumer* can
    override one of our resolved ``.pt`` files, which is what
    ``tests/test_layer_override.py`` exercises end to end.
    """

    def test_five_view_page_template_file_is_patched(self, portal):
        """The class behind ``browser:page template=...``.

        Still load-bearing: ``login_help.py`` reuses stock Plone's own
        ``login_help.pt`` by absolute path through a ``ViewPageTemplateFile``
        precisely so the form stays overridable by a site that already overrides
        it.
        """
        from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

        patched = vars(ViewPageTemplateFile).get("__get__")

        assert patched is not None
        assert patched.__module__ == "z3c.jbot.patches", (
            "z3c.jbot has not patched Products.Five ViewPageTemplateFile -- the "
            "browser:jbot directive is a no-op (Phase 0 caveat D1)"
        )

    def test_products_page_template_file_is_patched(self, portal):
        """The class ``render()`` loads our own templates with.

        ``render()`` uses ``Products.PageTemplates.PageTemplateFile`` precisely
        because it is both jbot-patched and has TAL path expressions. If this
        patch is absent, "z3c.jbot works on the resolved ``.pt`` files" is false.
        """
        from Products.PageTemplates.PageTemplateFile import PageTemplateFile

        patched = vars(PageTemplateFile).get("__get__")

        assert patched is not None
        assert patched.__module__ == "z3c.jbot.patches"
