"""The FR and NL catalogs must actually resolve at runtime.

Phase 0's caveat A3 is why this file is not boilerplate. The compiled output
carried **zero** ``i18n:domain`` declarations, so every ``i18n:translate``
rendered its msgid's *default* text -- **indistinguishable from success**, because
the English default appears in the output either way. Only a differential
assertion (FR output != NL output) can tell "translated" from "silently fell back
to the source language".

So nothing here asserts on a specific msgid: msgids belong to the template
author, and a test that hardcodes them breaks on every rename while still not
proving substitution. What is asserted is that the domain exists, its catalogs are
compiled and shipped, and the same template in two languages produces two
different mails.
"""

import pytest
import support


support.require_runtime()

from imio.emailkit import render  # noqa: E402


#: "First-class i18n (FR/NL/DE)"; "(FR/NL/DE shipped)".
SHIPPED_LANGUAGES = ("fr", "nl", "de")

#: The two the Phase 1 exit criteria and the iMio client base actually require.
REQUIRED_LANGUAGES = ("fr", "nl")


class TestTheTranslationDomainExists:
    def test_the_domain_is_registered(self, integration):
        """Without a registered ``imio.emailkit`` domain, every
        ``i18n:translate`` in every template silently returns its default text.
        This is caveat A3's root cause, and it is one utility lookup to rule out.
        """
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
    """``.po`` without ``.mo`` is the failure that only bites once.

    ``zope.i18n`` compiles a stale ``.po`` on start-up, but the freshly written
    ``.mo`` is not picked up by the run that produced it -- so a checkout with
    out-of-date ``.mo`` files serves untranslated text exactly once, which in CI
    reads as a missing translation and on a developer's machine reads as nothing
    at all.
    """

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
        """German ships too. Its own test so a missing German catalog is one
        clear failure rather than a parametrised surprise in the middle of the
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
        """The differential assertion caveat A3 demands.

        The ``lang`` attribute is stripped from both sides first, because it
        differs by construction and would make this pass on a template whose
        i18n is entirely broken.
        """
        context = support.load_fixture(template)
        name = support.qualified(template)

        html_fr, text_fr = render(name, context=dict(context), language="fr")
        html_nl, text_nl = render(name, context=dict(context), language="nl")

        stripped_fr = support.LANG_ATTRIBUTE.sub("<html", html_fr)
        stripped_nl = support.LANG_ATTRIBUTE.sub("<html", html_nl)

        assert stripped_fr != stripped_nl, (
            "the French and Dutch renders are identical once lang= is removed: "
            "either the template has no i18n:translate, or i18n:domain is missing "
            "from the compiled output (Phase 0 caveat A3)"
        )
        assert text_fr != text_nl, (
            "the plaintext twins are identical across languages -- the twin is not "
            "being translated"
        )

    def test_the_registered_subject_is_translated(self, integration, template):
        """The "**subject lives in the registration** as an i18n msgid,
        translated per recipient language at send time".

        Taken from the registration rather than from a rendered header, because
        that is where it is put -- for a discovered template the subject never
        appears in the body at all. The assertion is differential for caveat A3's
        reason: a msgid with no catalog entry returns its English default, which
        reads exactly like a successful translation.
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
        """``preheader`` is an optional msgid per template, rendered into
        the layout's hidden div -- "the highest-visibility email feature that
        everyone forgets; every inbox shows it". An untranslated one is shown to
        every recipient, in the wrong language, next to the subject."""
        from imio.emailkit import discovery
        from zope.i18n import translate

        msgid = discovery.get_template(support.qualified(template)).preheader
        if msgid is None:
            pytest.skip(f"{template} registers no preheader, which is allowed")

        fr = translate(msgid, target_language="fr")
        nl = translate(msgid, target_language="nl")

        assert fr != nl, f"the preheader msgid {msgid!r} is not translated ({fr!r})"
