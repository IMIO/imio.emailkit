"""ZCML registration of external consumer add-ons.

Two add-ons register templates alongside ``imio.emailkit``'s own:
``tests/dummies/dummy/minimal`` and ``tests/dummies/dummy/complete``. See
``tests/dummies/README.md`` for what each is for, and ``tests/dummyaddons.py``
for how their ZCML runs without a pip install.

Assertions read each add-on's own ``configure.zcml`` through :func:`declared`,
so they cannot drift from what the file actually says.

All three packages register a template named ``notification``. Lookups are
namespaced by package, so there is no collision.
"""

from xml.etree import ElementTree

import dummyaddons
import pytest
import support


support.require_runtime()

from imio.emailkit import render  # noqa: E402


(TemplateNotFound,) = support.require_contract(
    "imio.emailkit.interfaces", "TemplateNotFound's docstring", "TemplateNotFound"
)


#: The XML namespace the directives use. Written out, not imported, so the
#: test fails if the namespace URI ever changes.
EMAILKIT_NS = "http://namespaces.imio.be/emailkit"

#: The basename all three packages share.
SHARED_BASENAME = support.NOTIFICATION

#: Every template name that must be registered while the dummies are
#: installed: the two add-ons' plus ``imio.emailkit``'s own.
EXPECTED = (
    *dummyaddons.all_qualified_names(),
    support.qualified(SHARED_BASENAME),
)


def declared(addon):
    """``{basename: {attribute: value}}`` from the add-on's ``configure.zcml``.

    Asserts there is exactly one ``<emailkit:templates>`` block: a second
    block in the same package is a configuration conflict at startup.
    """
    # This file is the add-on's own committed configure.zcml, not external input.
    root = ElementTree.parse(addon.zcml).getroot()  # noqa: S314
    blocks = root.findall(f"{{{EMAILKIT_NS}}}templates")

    assert len(blocks) == 1, (
        f"{addon.zcml} has {len(blocks)} <emailkit:templates> blocks; a package "
        "gets one, and a second one conflicts at startup"
    )
    return {
        template.get("name"): dict(template.attrib)
        for template in blocks[0].findall(f"{{{EMAILKIT_NS}}}template")
    }


def msgid_and_default(value):
    """Split a ``"[msgid] Default text"`` attribute the way the directive does."""
    assert value.startswith("["), (
        f"{value!r} does not use the explicit `[msgid] Default text` form, so the "
        "whole string would become the msgid"
    )
    msgid, _, default = value[1:].partition("]")
    return msgid.strip(), default.strip()


@pytest.fixture(autouse=True)
def dummy_addons_installed():
    """Both dummy add-ons registered for the duration of each test."""
    with dummyaddons.installed() as addons:
        yield addons


@pytest.fixture
def templates(integration):
    from imio.emailkit.discovery import get_templates

    return get_templates()


class TestBothAddonsAreRegistered:
    """Executing a consumer's ZCML registers its templates, namespaced."""

    def test_every_dummy_template_is_registered(self, templates):
        missing = [name for name in EXPECTED if name not in templates]

        assert missing == [], (
            f"not registered: {missing}. Registered: {sorted(templates)}"
        )

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_addon_contributes_exactly_what_its_zcml_declares(
        self, templates, addon
    ):
        """No more and no less than its ``<emailkit:templates>`` block lists."""
        registered = tuple(
            sorted(
                name.split(":", 1)[1]
                for name in templates
                if name.startswith(f"{addon.package}:")
            )
        )

        assert registered == tuple(sorted(declared(addon))) == addon.templates

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_names_are_namespaced_by_the_registering_package(self, templates, addon):
        """The namespace is the package owning the ZCML file, not an
        attribute the consumer writes."""
        for basename in addon.templates:
            template = templates[addon.qualified(basename)]

            assert template.package == addon.package
            assert template.basename == basename
            assert template.name == f"{addon.package}:{basename}"

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_files_come_from_the_addons_own_directory(self, templates, addon):
        """Resolves ``<package>/<directory>/<name>.pt``.

        ``dummy.minimal`` omits ``directory`` and uses the default;
        ``dummy.complete`` states it. Both must resolve inside their own
        package, not the host's.
        """
        for basename in addon.templates:
            html_path = templates[addon.qualified(basename)].html_path

            assert html_path.is_file(), f"{html_path} does not exist"
            assert html_path.parent == addon.templates_dir.resolve(), (
                f"{addon.qualified(basename)} resolved to {html_path}, outside "
                f"{addon.templates_dir}"
            )

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_templates_directory_is_recorded_for_the_build_tooling(self, addon):
        """The build tooling needs a package's output directory even before
        its first build has registered any template."""
        from imio.emailkit.discovery import registered_directories

        directories = registered_directories()

        assert directories[addon.package] == addon.templates_dir.resolve()

    def test_the_dummies_are_not_registered_when_not_installed(self, integration):
        """Negative control: outside ``installed()``, the dummy templates
        must be gone."""
        from imio.emailkit.discovery import available_templates

        with dummyaddons.uninstalled():
            still_there = [
                name
                for name in dummyaddons.all_qualified_names()
                if name in available_templates()
            ]

        assert still_there == [], (
            f"{still_there} are registered without the dummy add-ons installed, so "
            "this module is not testing what it claims to test"
        )


class TestNoCollisionOnASharedBasename:
    """Two add-ons shipping the same template basename do not clash."""

    #: Every package that registers :data:`SHARED_BASENAME`.
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
        """The render must pick the right file, not just resolve a distinct
        path. Each fixture has a different title, so a wrong lookup shows up
        as the wrong heading."""
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
        """The bare name must not resolve, even with three candidates
        registered. Accepting it would make the result depend on ZCML load
        order."""
        with pytest.raises(TemplateNotFound):
            render(SHARED_BASENAME, context={})


class TestAvailableListsEveryAddon:
    """``TemplateNotFound(name, available=[...])``."""

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
        """The list must appear in the exception message, not just the object."""
        message = str(failure)
        for name in EXPECTED:
            assert name in message

    def test_an_unknown_template_in_a_known_package_still_raises(self, failure):
        assert failure.name == self.UNKNOWN


class TestRegistrationMetadata:
    """The subject and the optional preheader live in the registration."""

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_subject_msgid_reaches_the_template(self, templates, addon):
        for basename, attributes in declared(addon).items():
            template = templates[addon.qualified(basename)]
            msgid, default = msgid_and_default(attributes["subject"])

            assert template.subject == msgid, (
                "the Template's subject is not the msgid its ZCML declares"
            )
            assert template.subject.default == default, (
                "the default text after the msgid is what reaches the inbox until a "
                "catalog translates it, and it did not survive the registration"
            )

    @pytest.mark.parametrize("addon", dummyaddons.ADDONS, ids=lambda a: a.package)
    def test_the_subject_msgid_carries_the_addons_own_domain(self, templates, addon):
        """The msgid domain comes from the add-on's own ``i18n_domain``. This
        lets a consumer skip a ``MessageFactory`` and keeps its subject out
        of ``imio.emailkit``'s own domain."""
        for basename in addon.templates:
            domain = templates[addon.qualified(basename)].subject.domain

            assert domain == addon.package, (
                f"{addon.qualified(basename)}'s subject msgid carries the domain "
                f"{domain!r}, not the add-on's own {addon.package!r}"
            )
            assert domain != support.PACKAGE_NAME

    def test_the_preheader_is_optional(self, templates):
        """The preheader is optional; when omitted, the div collapses to
        nothing."""
        minimal = templates[dummyaddons.MINIMAL.qualified("notification")]

        assert "preheader" not in declared(dummyaddons.MINIMAL)["notification"], (
            "dummy.minimal is the floor and declares no preheader; this test has "
            "nothing left to say if it starts declaring one"
        )
        assert minimal.preheader is None, (
            "dummy.minimal declares no preheader; registration must not invent one"
        )

    def test_the_preheader_reaches_the_template_when_declared(self, templates):
        for basename, attributes in declared(dummyaddons.COMPLETE).items():
            template = templates[dummyaddons.COMPLETE.qualified(basename)]
            msgid, default = msgid_and_default(attributes["preheader"])

            assert template.preheader == msgid
            assert template.preheader.default == default
            assert template.preheader.domain == dummyaddons.COMPLETE.package


class TestPlaintextTwins:
    """The ``.txt.pt`` twin is used when present; its absence falls back
    with a warning. The two dummies exercise both paths."""

    def test_a_declared_twin_is_resolved(self, templates):
        for basename in dummyaddons.COMPLETE.twins:
            template = templates[dummyaddons.COMPLETE.qualified(basename)]

            assert template.text_path is not None
            assert template.text_path.is_file()

    def test_an_absent_twin_leaves_text_path_none(self, templates):
        template = templates[dummyaddons.MINIMAL.qualified("notification")]

        assert template.text_path is None

    def test_both_addons_still_render_a_plaintext_part(self, integration):
        """Twin or fallback, ``render()`` returns text either way."""
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
        """``dummy.complete:convocation`` has a hand-authored twin whose text
        includes the CTA URL. ``dummy.minimal`` has none, and the automatic
        fallback drops every ``<a href>``."""
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
    """A broken template in one add-on must not cost the others their
    mails. Registers an extra template that names a ``.pt`` file that was
    never built, through the real directive on a fresh configuration
    machine, as a consumer's instance start does with the same mistake."""

    ZCML = """\
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="dummy.minimal">
  <emailkit:templates>
    <emailkit:template name="notification" subject="[s_notification] N" />
    <emailkit:template name="never_compiled" subject="[s_never] X" />
  </emailkit:templates>
</configure>
"""

    def test_the_other_templates_survive_a_missing_pt_file(self, integration, caplog):
        from imio.emailkit.discovery import get_templates
        from zope.configuration import xmlconfig
        from zope.configuration.config import ConfigurationMachine

        import imio.emailkit
        import importlib
        import logging

        machine = ConfigurationMachine()
        xmlconfig.registerCommonDirectives(machine)
        xmlconfig.include(machine, file="meta.zcml", package=imio.emailkit)
        # `<include package=...>` sets this. The directive reads it to derive
        # the namespace and the directory base.
        machine.package = importlib.import_module(dummyaddons.MINIMAL.package)

        with caplog.at_level(logging.WARNING, logger="imio.emailkit.discovery"):
            xmlconfig.string(self.ZCML, context=machine)

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
