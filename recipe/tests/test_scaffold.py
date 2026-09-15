"""``--new NAME``: "the four files a template needs"."""

from imio.recipe.emailkit import projects
from imio.recipe.emailkit import scaffold

import pytest


class TestTheFourFiles:
    def test_it_writes_exactly_the_four_spec_5_names(self, project):
        paths = scaffold.new_template(project, "convocation")
        names = sorted(path.name for path in paths)
        assert names == [
            "convocation.fr.html",
            "convocation.py",
            "convocation.registration.txt",
            "convocation.vue",
        ]

    def test_they_land_where_the_rest_of_the_project_expects_them(self, project):
        scaffold.new_template(project, "convocation")
        assert (project.sources_dir / "convocation.vue").is_file()
        assert (project.tests_dir / "fixtures" / "convocation.py").is_file()
        assert (project.tests_dir / "golden" / "convocation.fr.html").is_file()

    def test_the_fixture_defines_a_context_dict(self, project):
        """The fixture's contract, and what ``bin/preview-emails`` loads by path."""
        scaffold.new_template(project, "convocation")
        body = (project.tests_dir / "fixtures" / "convocation.py").read_text(
            encoding="utf-8"
        )
        namespace = {}
        exec(compile(body, "fixture", "exec"), namespace)  # noqa: S102 - our own text
        assert isinstance(namespace["CONTEXT"], dict)
        assert set(namespace["CONTEXT"]) == {"title", "intro"}

    def test_the_golden_file_is_a_visible_placeholder_not_a_plausible_snapshot(
        self, project
    ):
        """A golden that silently agreed with the first render would catch nothing."""
        scaffold.new_template(project, "convocation")
        body = (project.tests_dir / "golden" / "convocation.fr.html").read_text(
            encoding="utf-8"
        )
        assert "PLACEHOLDER" in body
        assert "update-golden" in body

    def test_the_registration_stub_is_pasteable_and_names_the_package(self, project):
        stub = scaffold.registration_stub(project, "convocation")
        assert '"convocation"' in stub
        assert "email_subject_convocation" in stub
        assert project.package in stub

    def test_the_registration_stub_is_zcml_not_the_old_dict_form(self, project):
        """Registration moved from a Python dict to a ZCML directive; the
        scaffold must teach the current form, not the old one."""
        stub = scaffold.registration_stub(project, "convocation")
        assert "<emailkit:template" in stub
        assert 'name="convocation"' in stub
        assert "email_preheader_convocation" in stub
        # The old form this replaces, so a regression is caught rather than
        # merely un-asserted.
        assert "emailkit` dict" not in stub
        assert "MessageFactory" not in stub


class TestTheSkeletonEncodesTheAuthoringRules:
    """The point of scaffolding: start on the right side of every authoring rule."""

    def test_no_chameleon_placeholder_in_a_literal_style_or_class_attribute(
        self, project
    ):
        """The amended rule: it kills CSS inlining document-wide, silently."""
        scaffold.new_template(project, "convocation")
        body = (project.sources_dir / "convocation.vue").read_text(encoding="utf-8")
        import re

        for attribute in ("class", "style"):
            for match in re.finditer(rf'{attribute}="([^"]*)"', body):
                assert "${" not in match.group(1)

    def test_no_double_dash_anywhere_in_the_vue_source(self, project):
        """Chameleon refuses to parse it, at runtime, on a green build.

        Asserted over the whole file rather than only inside its comments, which is
        both simpler and stricter, and which is exactly how the repo-wide rule is
        written: "No ``--`` in any comment, anywhere".
        A ``.vue`` source's comments are the ones that become HTML comments in the
        compiled output, so this is the file where the rule bites.
        """
        scaffold.new_template(project, "convocation")
        body = (project.sources_dir / "convocation.vue").read_text(encoding="utf-8")
        assert "--" not in body

    def test_it_uses_a_kit_component_rather_than_raw_table_markup(self, project):
        scaffold.new_template(project, "convocation")
        body = (project.sources_dir / "convocation.vue").read_text(encoding="utf-8")
        assert "<KitMain>" in body

    def test_no_tal_or_i18n_attribute_on_a_kit_component(self, project):
        scaffold.new_template(project, "convocation")
        body = (project.sources_dir / "convocation.vue").read_text(encoding="utf-8")
        import re

        for match in re.finditer(r"<Kit\w+([^>]*)>", body):
            assert "tal:" not in match.group(1)
            assert "i18n:" not in match.group(1)


class TestFailingLoud:
    def test_it_refuses_to_overwrite_and_lists_what_is_in_the_way(self, project):
        scaffold.new_template(project, "convocation")
        with pytest.raises(scaffold.ScaffoldError) as raised:
            scaffold.new_template(project, "convocation")
        assert "convocation.vue" in str(raised.value)
        assert "--force" in str(raised.value)

    def test_force_overwrites(self, project):
        scaffold.new_template(project, "convocation")
        (project.sources_dir / "convocation.vue").write_text("edited", encoding="utf-8")
        scaffold.new_template(project, "convocation", force=True)
        assert "KitMain" in (project.sources_dir / "convocation.vue").read_text(
            encoding="utf-8"
        )

    @pytest.mark.parametrize("name", ["", "with space", "../escape", "a/b", "dot.name"])
    def test_a_name_that_is_not_a_usable_stem_is_refused(self, project, name):
        """The name becomes a filename, a module name *and* a lookup key."""
        with pytest.raises(scaffold.ScaffoldError):
            scaffold.new_template(project, name)

    def test_an_installed_egg_has_nowhere_to_put_them(self, tmp_path):
        package_dir = tmp_path / "installed" / "acme"
        package_dir.mkdir(parents=True)
        installed = projects.make_project("acme", package_dir)
        with pytest.raises(scaffold.ScaffoldError, match="only works in a checkout"):
            scaffold.new_template(installed, "convocation")


class TestTheNextStepsMessage:
    def test_it_names_the_vue_file_and_the_four_steps(self, project):
        paths = scaffold.new_template(project, "convocation")
        message = scaffold.next_steps(project, "convocation", paths)
        assert "convocation.vue" in message
        assert "preview-emails --package acme.notifications" in message
        assert "update-golden" in message
        assert "<emailkit:templates>" in message
        assert "`emailkit` dict" not in message

    def test_the_registration_stub_names_the_namespace_declaration(self, project):
        # Without `xmlns:emailkit=<the URI>` on the consumer's <configure>
        # root, the pasted block does not parse -- and the marker grep the
        # recipe discovers packages with matches exactly that URI, so the
        # package would not even be found. The stub must say so.
        stub = scaffold.registration_stub(project, "convocation")
        assert "xmlns:emailkit" in stub
        assert projects.MARKER in stub
