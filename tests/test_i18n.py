"""The FR and NL catalogs must actually resolve at runtime.

A missing ``i18n:domain`` declaration makes ``i18n:translate`` render the
English default everywhere, which looks like success. Only a differential
check (FR output != NL output) can tell the two apart, so nothing here
asserts on a specific msgid.
"""

import pytest
import support


support.require_runtime()

from imio.emailkit import render  # noqa: E402


#: Languages the package ships as first-class i18n.
SHIPPED_LANGUAGES = ("fr", "nl", "de")

#: The two the iMio client base actually requires.
REQUIRED_LANGUAGES = ("fr", "nl")


class TestTheTranslationDomainExists:
    def test_the_domain_is_registered(self, integration):
        """Every ``i18n:translate`` would silently return its default text."""
        from zope.component import queryUtility
        from zope.i18n.interfaces import ITranslationDomain

        domain = queryUtility(ITranslationDomain, name=support.PACKAGE_NAME)

        assert domain is not None, (
            f"no ITranslationDomain named {support.PACKAGE_NAME!r}: i18n:translate "
            "will fall back to the msgid default everywhere, with no error"
        )

    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_the_catalog_is_known_to_the_domain(self, integration, language):
        from zope.component import getUtility
        from zope.i18n.interfaces import ITranslationDomain

        domain = getUtility(ITranslationDomain, name=support.PACKAGE_NAME)

        assert language in domain.getCatalogsInfo(), (
            f"the {support.PACKAGE_NAME} domain has no {language} catalog"
        )


class TestCatalogsAreShipped:
    """A ``.po`` without a compiled ``.mo`` serves untranslated text for
    the run that compiles it."""

    @pytest.fixture
    def locales(self):
        from pathlib import Path

        import imio.emailkit

        return Path(imio.emailkit.__file__).parent / "locales"

    def test_the_pot_is_committed(self, locales):
        assert (locales / f"{support.PACKAGE_NAME}.pot").exists()

    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_the_po_is_committed(self, locales, language):
        path = locales / language / "LC_MESSAGES" / f"{support.PACKAGE_NAME}.po"

        assert path.exists(), f"missing catalog: {path}"

    @pytest.mark.parametrize("language", REQUIRED_LANGUAGES)
    def test_the_mo_is_compiled(self, locales, language):
        path = locales / language / "LC_MESSAGES" / f"{support.PACKAGE_NAME}.mo"

        assert path.exists(), (
            f"missing compiled catalog: {path}. Run `make i18n` and commit the "
            "result -- the .mo files are committed on purpose."
        )

    def test_german_is_shipped(self, locales):
        """Separate, so a missing catalog is not a surprise inside the
        FR/NL run."""
        path = locales / "de" / "LC_MESSAGES" / f"{support.PACKAGE_NAME}.po"

        assert path.exists(), f"German is expected to be shipped: {path}"


@pytest.mark.parametrize(
    "template", support.RENDERABLE_TEMPLATES, ids=support.RENDERABLE_TEMPLATES
)
class TestTemplatesAreReallyTranslated:
    def test_fr_and_nl_renders_differ_beyond_the_lang_attribute(
        self, integration, template
    ):
        """The ``lang`` attribute is stripped first: it always differs, and
        would make this pass even on broken i18n."""
        context = support.load_fixture(template)
        name = support.qualified(template)

        html_fr, text_fr = render(name, context=dict(context), language="fr")
        html_nl, text_nl = render(name, context=dict(context), language="nl")

        stripped_fr = support.LANG_ATTRIBUTE.sub("<html", html_fr)
        stripped_nl = support.LANG_ATTRIBUTE.sub("<html", html_nl)

        assert stripped_fr != stripped_nl, (
            "the French and Dutch renders are identical once lang= is removed: "
            "either the template has no i18n:translate, or i18n:domain is "
            "missing from the compiled output"
        )
        assert text_fr != text_nl, (
            "the plaintext twins are identical across languages -- the twin is not "
            "being translated"
        )

    def test_the_registered_subject_is_translated(self, integration, template):
        """Read from the registration, not a rendered header: the subject
        never appears in the body. Differential, since an untranslated
        msgid still returns its English default.
        """
        from imio.emailkit import discovery
        from zope.i18n import translate

        msgid = discovery.get_template(support.qualified(template)).subject

        fr = translate(msgid, target_language="fr")
        nl = translate(msgid, target_language="nl")

        assert fr != nl, (
            f"the subject msgid {msgid!r} translates identically in fr and nl "
            f"({fr!r}): the catalogs have no entry for it, so every commune gets "
            "the English default"
        )
        assert fr != str(msgid), f"{msgid!r} is untranslated in French"

    def test_the_registered_preheader_is_translated(self, integration, template):
        """Shown by every inbox next to the subject; an untranslated one
        reaches every recipient in the wrong language."""
        from imio.emailkit import discovery
        from zope.i18n import translate

        msgid = discovery.get_template(support.qualified(template)).preheader
        if msgid is None:
            pytest.skip(f"{template} registers no preheader, which is allowed")

        fr = translate(msgid, target_language="fr")
        nl = translate(msgid, target_language="nl")

        assert fr != nl, f"the preheader msgid {msgid!r} is not translated ({fr!r})"
