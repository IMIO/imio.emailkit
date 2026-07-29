"""SPEC §4 -- entry-point discovery of **external** add-ons (Phase 4 gate 8).

``tests/test_discovery.py`` covers the mechanism as ``imio.emailkit`` uses it on
itself ("it is its own first consumer"). This module covers what that cannot: two
*other* distributions, each with its own ``imio.emailkit.templates`` entry point,
its own registration dict, its own ``emails/`` sources and its own committed
``templates/*.pt``.

The add-ons are ``tests/dummies/dummy/minimal`` and
``tests/dummies/dummy/complete``; ``tests/dummies/README.md`` says what each of
them is for, and ``tests/dummyaddons.py`` says how they get discovered without
being pip-installed.

**The collision case is the one that matters.** Three distributions register a
template whose basename is ``notification``: both dummies and ``imio.emailkit``
itself. §4's answer is that lookups are namespaced, so there is nothing to collide
-- and the assertions below are written to fail if scan order ever started
deciding which one you get.
"""

import dummyaddons
import pytest
import support


support.require_runtime()

from imio.emailkit import render  # noqa: E402


(TemplateNotFound,) = support.require_contract(
    "imio.emailkit.interfaces", "§4", "TemplateNotFound"
)


#: The basename all three distributions share, which is the whole point of §4's
#: namespacing.
SHARED_BASENAME = support.NOTIFICATION

#: Every template name that must be discoverable while the dummies are installed:
#: the two add-ons' plus ``imio.emailkit``'s own. The host package is included on
#: purpose -- an installation mechanism that shadowed the host's own registration
#: would otherwise look like a success.
EXPECTED = (
    *dummyaddons.all_qualified_names(),
    support.qualified(SHARED_BASENAME),
)


@pytest.fixture(autouse=True)
def dummy_addons_installed():
    """The two dummy distributions, visible for the duration of each test."""
    with dummyaddons.installed() as addons:
        yield addons


@pytest.fixture
def templates(integration):
    from imio.emailkit.discovery import get_templates

    return get_templates()


class TestBothAddonsAreFound:
    """§4: "``imio.emailkit`` scans the entry-point group once at startup"."""

    def test_every_dummy_template_is_discovered(self, templates):
        missing = [name for name in EXPECTED if name not in templates]

        assert missing == [], (
            f"not discovered: {missing}. Registered: {sorted(templates)}"
        )

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_addon_contributes_exactly_what_it_registers(self, templates, addon):
        """No more and no less than its registration dict lists.

        Driven off the add-on's own ``emailkit`` dict rather than off a list
        restated here, so the assertion cannot drift away from the thing it is
        about.
        """
        registered = tuple(sorted(addon.registration()["templates"]))
        found = tuple(
            sorted(
                name.split(":", 1)[1]
                for name in templates
                if name.startswith(f"{addon.package}:")
            )
        )

        assert found == registered == addon.templates

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_names_are_namespaced_by_the_entry_point_name(self, templates, addon):
        """§4: "Template names are namespaced at lookup"."""
        for basename in addon.templates:
            template = templates[addon.qualified(basename)]

            assert template.package == addon.package
            assert template.basename == basename
            assert template.name == f"{addon.package}:{basename}"

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_files_come_from_the_addons_own_directory(self, templates, addon):
        """§4 resolves ``<package>/<directory>/<name>.pt``.

        ``dummy.minimal`` omits ``directory`` and relies on the documented
        ``templates`` default; ``dummy.complete`` states it. Both must land in
        their own package, and a template resolved out of the *host's* directory
        would be the failure this catches.
        """
        for basename in addon.templates:
            html_path = templates[addon.qualified(basename)].html_path

            assert html_path.is_file(), f"{html_path} does not exist"
            assert html_path.parent == addon.templates_dir.resolve(), (
                f"{addon.qualified(basename)} resolved to {html_path}, outside "
                f"{addon.templates_dir}"
            )

    def test_the_dummies_are_not_discovered_when_not_installed(self, integration):
        """The negative control for the whole module.

        Without it, every assertion above could be passing because the templates
        were somehow always there. ``tests/dummyaddons.installed()`` is what makes
        them visible, so outside it they must be gone again.
        """
        from imio.emailkit.discovery import available_templates

        with dummyaddons.uninstalled():
            still_there = [
                name
                for name in dummyaddons.all_qualified_names()
                if name in available_templates()
            ]

        assert still_there == [], (
            f"{still_there} are discoverable without the dummy .dist-info on "
            "sys.path, so this module is not testing what it claims to test"
        )


class TestNoCollisionOnASharedBasename:
    """§4: two add-ons shipping the same template basename do not clash."""

    #: Every distribution that registers :data:`SHARED_BASENAME`.
    OWNERS = (
        support.PACKAGE_NAME,
        dummyaddons.MINIMAL.package,
        dummyaddons.COMPLETE.package,
    )

    def test_all_three_owners_resolve(self, templates):
        for package in self.OWNERS:
            assert f"{package}:{SHARED_BASENAME}" in templates

    def test_they_are_three_different_files(self, templates):
        paths = [
            templates[f"{package}:{SHARED_BASENAME}"].html_path
            for package in self.OWNERS
        ]

        assert len(set(paths)) == len(paths), (
            f"the shared basename {SHARED_BASENAME!r} resolved to the same file "
            f"for more than one package: {paths}"
        )

    def test_each_one_renders_its_own_content(self, templates):
        """Distinct paths are not enough; the *render* has to pick the right one.

        Each of the three fixtures has a different ``title``, so a lookup that
        silently returned another package's template shows up here as the wrong
        heading rather than as a passing test.
        """
        rendered = {}
        for addon in dummyaddons.ADDONS:
            html, _text = render(
                addon.qualified(SHARED_BASENAME),
                context=support.load_fixture_from(addon.fixtures_dir, SHARED_BASENAME),
                language="fr",
            )
            rendered[addon.package] = html

        host_html, _ = render(
            support.qualified(SHARED_BASENAME),
            context=support.load_fixture(SHARED_BASENAME),
            language="fr",
        )
        rendered[support.PACKAGE_NAME] = host_html

        for addon in dummyaddons.ADDONS:
            expected = support.load_fixture_from(addon.fixtures_dir, SHARED_BASENAME)[
                "title"
            ]

            assert expected in rendered[addon.package]
            assert expected not in rendered[support.PACKAGE_NAME], (
                f"{addon.package}'s content leaked into the host's render"
            )

    def test_the_bare_basename_still_resolves_to_nothing(self, integration):
        """§4, and now with three candidates instead of one.

        Accepting the bare name would make the answer depend on entry-point scan
        order, which is exactly the bug the namespace exists to prevent.
        """
        with pytest.raises(TemplateNotFound):
            render(SHARED_BASENAME, context={})


class TestAvailableListsEveryAddon:
    """§4: ``TemplateNotFound(name, available=[...])``."""

    UNKNOWN = "dummy.minimal:no_such_template"

    @pytest.fixture
    def failure(self, integration):
        with pytest.raises(TemplateNotFound) as exc_info:
            render(self.UNKNOWN, context={})
        return exc_info.value

    def test_available_lists_all_three_packages(self, failure):
        available = set(failure.available)
        missing = [name for name in EXPECTED if name not in available]

        assert missing == [], (
            f"TemplateNotFound.available omits {missing}. A developer reading this "
            "traceback is looking for the name they should have typed, and a list "
            "that only holds their own package's templates does not help."
        )

    def test_the_message_names_the_other_addons_templates(self, failure):
        """The list has to reach whoever reads the traceback."""
        message = str(failure)
        for name in EXPECTED:
            assert name in message

    def test_an_unknown_template_in_a_known_package_still_raises(self, failure):
        assert failure.name == self.UNKNOWN


class TestRegistrationMetadata:
    """§4: the subject and the optional preheader live in the registration."""

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_subject_msgid_reaches_the_template(self, templates, addon):
        declared = addon.registration()["templates"]
        for basename in addon.templates:
            template = templates[addon.qualified(basename)]

            assert template.subject == declared[basename]["subject"], (
                "the Template's subject is not the msgid the registration declares"
            )
            assert template.subject.domain == addon.package, (
                "the subject msgid carries the *add-on's* i18n domain, not "
                f"imio.emailkit's: got {template.subject.domain!r}"
            )

    def test_the_preheader_is_optional(self, templates):
        """§4: "Omitted -> the div collapses to nothing"."""
        minimal = templates[dummyaddons.MINIMAL.qualified("notification")]

        assert minimal.preheader is None, (
            "dummy.minimal registers no preheader; discovery must not invent one"
        )

    def test_the_preheader_reaches_the_template_when_declared(self, templates):
        declared = dummyaddons.COMPLETE.registration()["templates"]
        for basename in dummyaddons.COMPLETE.templates:
            template = templates[dummyaddons.COMPLETE.qualified(basename)]

            assert template.preheader == declared[basename]["preheader"]


class TestPlaintextTwins:
    """§4: the ``.txt.pt`` twin is primary; its absence is a warned fallback.

    The two dummies are on opposite sides of this on purpose, so both paths are
    exercised by a *registered* add-on rather than by moving a file aside.
    """

    def test_a_declared_twin_is_resolved(self, templates):
        for basename in dummyaddons.COMPLETE.twins:
            template = templates[dummyaddons.COMPLETE.qualified(basename)]

            assert template.text_path is not None
            assert template.text_path.is_file()

    def test_an_absent_twin_leaves_text_path_none(self, templates):
        template = templates[dummyaddons.MINIMAL.qualified("notification")]

        assert template.text_path is None

    def test_both_addons_still_render_a_plaintext_part(self, integration):
        """Twin or fallback, ``render()`` returns text either way (§6.1)."""
        for addon in dummyaddons.ADDONS:
            for basename in addon.templates:
                html, text = render(
                    addon.qualified(basename),
                    context=support.load_fixture_from(addon.fixtures_dir, basename),
                    language="fr",
                )

                assert text and text.strip(), f"{addon.qualified(basename)}: no text"
                assert "<html" not in text.lower(), (
                    f"{addon.qualified(basename)}: the plaintext part is HTML"
                )
                support.assert_render_is_clean(
                    html, f"{addon.qualified(basename)} html"
                )
                support.assert_render_is_clean(
                    text, f"{addon.qualified(basename)} text"
                )

    def test_the_twin_carries_what_the_fallback_loses(self, integration):
        """Why §4 makes the twin primary, asserted rather than asserted-about.

        ``dummy.complete:convocation`` has a hand-authored twin and its plaintext
        part contains the CTA **URL**; ``dummy.minimal`` has none and the naive
        extraction drops every ``<a href>`` it walks over. If the fallback ever
        started keeping links this test is where the documentation gets updated.
        """
        _html, text = render(
            dummyaddons.COMPLETE.qualified("convocation"),
            context=support.load_fixture_from(
                dummyaddons.COMPLETE.fixtures_dir, "convocation"
            ),
            language="fr",
        )
        url = support.load_fixture_from(
            dummyaddons.COMPLETE.fixtures_dir, "convocation"
        )["cta_url"]

        assert url in text, "the hand-authored twin lost the CTA url"


class TestOneBrokenRegistrationDoesNotHideTheOthers:
    """§4/discovery: a typo in one add-on must not cost the others their mails.

    Exercised by adding an unbuilt template name to ``dummy.minimal``'s *loaded*
    registration rather than by shipping a third, broken dummy add-on: a dummy
    that exists to be wrong would be read as documentation of how to be wrong.
    """

    def test_the_other_templates_survive_a_missing_pt_file(
        self, integration, monkeypatch, caplog
    ):
        from imio.emailkit.discovery import get_templates
        from imio.emailkit.discovery import invalidate_cache

        import logging

        registration = dummyaddons.MINIMAL.registration()
        broken = dict(registration["templates"])
        broken["never_compiled"] = {"subject": "whatever"}
        monkeypatch.setitem(registration, "templates", broken)
        invalidate_cache()

        with caplog.at_level(logging.WARNING, logger="imio.emailkit.discovery"):
            templates = get_templates()

        assert dummyaddons.MINIMAL.qualified("never_compiled") not in templates, (
            "a template whose .pt is missing must not be registered"
        )
        assert dummyaddons.MINIMAL.qualified("notification") in templates
        for name in dummyaddons.COMPLETE.templates:
            assert dummyaddons.COMPLETE.qualified(name) in templates
        assert any("never_compiled" in r.getMessage() for r in caplog.records), (
            "the skipped template was not named in any warning, so nobody would "
            f"learn why it is missing: {[r.getMessage() for r in caplog.records]}"
        )
