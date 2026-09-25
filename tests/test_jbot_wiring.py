"""Guard the two silent failure modes behind every override test:
including only ``z3c.jbot/meta.zcml`` parses fine but skips the real
monkeypatches, and a missing ``IPageTemplateEngine`` utility lets
``${...}`` pass through unrendered. Other tests check rendered output;
this one checks the machinery both depend on.
"""

import support


support.require_runtime()


class TestPageTemplateEngine:
    def test_engine_is_chameleon_not_zope_tal(self, portal):
        """``portal`` is requested only to set up the layer's ZCA registry."""
        from zope.component import queryUtility
        from zope.pagetemplate.interfaces import IPageTemplateEngine

        engine = queryUtility(IPageTemplateEngine)

        assert engine is not None, (
            "no IPageTemplateEngine utility: zope.pagetemplate will fall back to "
            "zope.tal and ship ${...} verbatim"
        )
        assert engine.__module__ == "Products.PageTemplates.engine"


class TestJbotPatchesAreLoaded:
    """The add-on must include the whole ``z3c.jbot`` package, not just
    ``meta.zcml``, or these patches never load."""

    def test_five_view_page_template_file_is_patched(self, portal):
        """The class behind ``browser:page template=...``."""
        from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

        patched = vars(ViewPageTemplateFile).get("__get__")

        assert patched is not None
        assert patched.__module__ == "z3c.jbot.patches", (
            "z3c.jbot has not patched Products.Five ViewPageTemplateFile: the "
            "browser:jbot directive is a no-op"
        )

    def test_products_page_template_file_is_patched(self, portal):
        """The class ``render()`` uses to load our own templates."""
        from Products.PageTemplates.PageTemplateFile import PageTemplateFile

        patched = vars(PageTemplateFile).get("__get__")

        assert patched is not None
        assert patched.__module__ == "z3c.jbot.patches"
