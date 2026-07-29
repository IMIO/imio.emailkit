"""SPEC §4 -- template distribution & discovery.

``imio.emailkit`` registers its own templates through the very entry point an
external add-on uses ("it is its own first consumer"), so exercising *our* names
exercises the mechanism. Phase 1 stops there on purpose: discovery of external
add-ons via two dummy distributions is a Phase 4 deliverable
(``docs/plans/phase-1.md`` §7).

Almost everything here goes through ``render()`` rather than through the
discovery module's internals. That is deliberate: ``render(name, ...)`` is the
one entry point §6.1 pins by name, so these assertions survive any refactor of
``discovery.py`` -- and a lookup that "works" but that ``render()`` cannot use is
not a working lookup.
"""

import pytest
import support


support.require_runtime()

from imio.emailkit import render  # noqa: E402


(TemplateNotFound,) = support.require_contract(
    "imio.emailkit.interfaces", "§4", "TemplateNotFound"
)


UNKNOWN = support.qualified("no_such_template_at_all")


class TestOwnTemplatesAreFound:
    @pytest.mark.parametrize("template", support.RENDERABLE_TEMPLATES)
    def test_own_template_resolves(self, integration, template):
        """§4: `imio.emailkit` finds its own templates through its own entry
        point -- it is its own first consumer, so this exercises the mechanism an
        external addon will use."""
        html, text = render(
            support.qualified(template),
            context=support.load_fixture(template),
            language="fr",
        )

        assert html
        assert text is not None


class TestUnknownTemplate:
    def test_unknown_name_raises_template_not_found(self, integration):
        with pytest.raises(TemplateNotFound) as exc_info:
            render(UNKNOWN, context={})

        assert UNKNOWN in str(exc_info.value)

    def test_the_exception_carries_the_name_asked_for(self, integration):
        with pytest.raises(TemplateNotFound) as exc_info:
            render(UNKNOWN, context={})

        assert exc_info.value.name == UNKNOWN

    def test_available_is_populated(self, integration):
        """§4: ``TemplateNotFound(name, available=[...])``.

        An empty ``available`` is the failure this catches: a discovery scan that
        found nothing raises exactly the same exception as a typo, and without
        the list nobody can tell the two apart from a traceback.
        """
        with pytest.raises(TemplateNotFound) as exc_info:
            render(UNKNOWN, context={})

        available = list(exc_info.value.available)

        assert available, (
            "TemplateNotFound.available is empty -- typo and 'the entry point scan found nothing' are indistinguishable"
        )
        expected = {support.qualified(n) for n in support.RENDERABLE_TEMPLATES}
        assert expected.issubset(set(available)), (
            f"our own templates are missing from available={available}"
        )

    def test_available_is_useful_in_the_message(self, integration):
        """The list has to reach whoever reads the traceback, not just an
        attribute nobody inspects."""
        with pytest.raises(TemplateNotFound) as exc_info:
            render(UNKNOWN, context={})

        message = str(exc_info.value)
        one_known = support.qualified(support.NOTIFICATION)

        assert one_known in message

    def test_unknown_package_raises_template_not_found(self, integration):
        """A whole unregistered namespace, not just an unknown leaf."""
        with pytest.raises(TemplateNotFound):
            render("no.such.package:whatever", context={})


class TestNamesAreNamespaced:
    def test_a_bare_name_does_not_resolve(self, integration):
        """§4: "Template names are namespaced at lookup:
        ``imio.pm.notifications:item_published``".

        Two add-ons will eventually both ship ``item_published``; accepting the
        bare name would make which one you get depend on scan order.
        """
        with pytest.raises(TemplateNotFound):
            render(support.NOTIFICATION, context={})


class TestMissingPlaintextTwin:
    """§4: "missing ``.txt.pt`` twin -> warning at startup, ``render()`` falls
    back to a naive text extraction with a logged deprecation".

    Exercised on a real registered template rather than on a dummy add-on, which
    is Phase 4. The ``.pt``/``.txt.pt`` pair lives in the directory named by the
    registration (§4: ``"directory": "templates"``); when a twin *is* committed it
    is moved aside for the duration of the test, and when none exists yet the
    fallback is simply the live behaviour.
    """

    TEMPLATE = support.NOTIFICATION

    @pytest.fixture
    def twin_path(self):
        from pathlib import Path

        import imio.emailkit

        return (
            Path(imio.emailkit.__file__).parent
            / "templates"
            / f"{self.TEMPLATE}.txt.pt"
        )

    @pytest.fixture
    def without_twin(self, twin_path):
        """Guarantee the twin is absent, restoring it afterwards if it was there.

        No skip branch: the fallback §4 specifies must work whether the twin was
        never built or went missing in a refactor, and those are the same code
        path. A version of this test that skipped when no twin was committed would
        stop testing the fallback exactly when the fallback is what is running.
        """
        if not twin_path.exists():
            yield twin_path
            return
        stashed = twin_path.with_suffix(".pt.stashed")
        twin_path.rename(stashed)
        try:
            yield twin_path
        finally:
            stashed.rename(twin_path)

    def test_render_still_returns_text(self, integration, without_twin):
        """The fallback must produce text, not ``None`` and not the HTML."""
        html, text = render(
            support.qualified(self.TEMPLATE),
            context=support.load_fixture(self.TEMPLATE),
            language="fr",
        )

        assert text and text.strip()
        assert "<html" not in text.lower(), (
            "the fallback returned HTML: a plaintext part that is HTML is worse "
            "than no plaintext part"
        )
        assert html

    @pytest.fixture
    def forget_previous_warning(self):
        """Re-arm ``render``'s once-per-process warning.

        The once-only guard is right: §4 says "warning at **startup**", and a mail
        loop that logged a line per render would bury everything else. But it also
        means an earlier test in this process has already consumed the only
        warning, so it has to be re-armed here.

        Done through the public ``invalidate_cache()`` rather than by reaching for
        the private set. Note the trap that cost a skip before finding this:
        ``from imio.emailkit import render`` yields the **function**, because
        ``__init__`` rebinds that name over the submodule -- so the module has to
        be fetched from ``sys.modules``.
        """
        import sys

        render_module = sys.modules["imio.emailkit.render"]
        render_module.invalidate_cache()

    def test_a_warning_is_logged(
        self, integration, without_twin, forget_previous_warning, caplog
    ):
        """Silent fallback is the failure mode: the twin goes missing in a build
        and nobody learns until a client reads a mail as raw markup."""
        import logging

        with caplog.at_level(logging.WARNING, logger="imio.emailkit"):
            render(
                support.qualified(self.TEMPLATE),
                context=support.load_fixture(self.TEMPLATE),
                language="fr",
            )

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]

        assert warnings, "missing .txt.pt twin fell back silently"
        assert any(self.TEMPLATE in r.getMessage() for r in warnings), (
            f"no warning names the template: {[r.getMessage() for r in warnings]}"
        )
