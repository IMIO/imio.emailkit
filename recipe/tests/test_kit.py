"""Wiring the design kit into a consumer, in both modes."""

from imio.recipe.emailkit import kit as kit_module

import json
import pytest


class TestPathMode:
    """The zero-copy mode, settled as viable and used as the default."""

    def test_it_writes_a_shim_and_copies_nothing(self, project, kit):
        target = kit_module.wire(project, kit, "path")
        assert target == project.emails_dir / ".kit"
        assert sorted(path.name for path in target.iterdir()) == [
            ".gitignore",
            "kit.json",
            "maizzle.config.base.js",
            "tailwind.css",
        ]
        # The point of `path` mode: the components stay in the egg.
        assert not (target / "components").exists()
        assert not (target / "layouts").exists()

    def test_the_shim_re_exports_the_real_module_so_kitdir_stays_the_egg(
        self, project, kit
    ):
        """Re-exporting keeps ``kitDir`` the egg's directory, not the shim's."""
        shim = project.emails_dir / ".kit" / "maizzle.config.base.js"
        kit_module.wire(project, kit, "path")
        body = shim.read_text(encoding="utf-8")
        source = json.dumps(str(kit / "maizzle.config.base.js"))
        assert f"export * from {source}" in body
        # `export *` does not carry `default`, so it needs its own line.
        assert f"import kitDefaultConfig from {source}" in body
        assert "export default kitDefaultConfig" in body

    def test_the_css_shim_reaches_the_kits_locked_entry(self, project, kit):
        kit_module.wire(project, kit, "path")
        body = (project.emails_dir / ".kit" / "tailwind.css").read_text(
            encoding="utf-8"
        )
        assert json.dumps(str(kit / "tailwind.css")) in body
        assert body.strip().endswith(";")


class TestCopyMode:
    def test_it_materialises_the_real_kit(self, project, kit):
        target = kit_module.wire(project, kit, "copy")
        assert (target / "layouts" / "Main.vue").exists()
        assert (target / "components" / "Button.vue").exists()
        assert (target / "strip-comments.js").exists()
        assert (target / "tailwind.css").read_text(encoding="utf-8") == (
            kit / "tailwind.css"
        ).read_text(encoding="utf-8")

    def test_the_consumers_import_specifier_is_the_same_in_both_modes(
        self, project, kit
    ):
        """Lets a consumer's config ignore ``kit-mode`` entirely."""
        for mode in ("path", "copy"):
            target = kit_module.wire(project, kit, mode)
            assert (target / kit_module.BASE_CONFIG).is_file()
            assert (target / kit_module.CSS_ENTRY).is_file()


class TestSwitchingModes:
    def test_switching_from_copy_to_path_leaves_no_copied_kit_behind(
        self, project, kit
    ):
        """Otherwise Maizzle keeps resolving components out of the stale copy."""
        kit_module.wire(project, kit, "copy")
        assert (project.emails_dir / ".kit" / "layouts").exists()
        kit_module.wire(project, kit, "path")
        assert not (project.emails_dir / ".kit" / "layouts").exists()

    def test_a_kit_file_deleted_upstream_disappears_from_the_copy(self, project, kit):
        kit_module.wire(project, kit, "copy")
        (kit / "components" / "Button.vue").unlink()
        kit_module.wire(project, kit, "copy")
        assert not (project.emails_dir / ".kit" / "components" / "Button.vue").exists()

    def test_wiring_is_idempotent(self, project, kit):
        first = kit_module.wire(project, kit, "path")
        contents = (first / kit_module.BASE_CONFIG).read_bytes()
        second = kit_module.wire(project, kit, "path")
        assert (second / kit_module.BASE_CONFIG).read_bytes() == contents


class TestHousekeeping:
    def test_the_wiring_ignores_itself_rather_than_editing_a_gitignore(
        self, project, kit
    ):
        """The recipe must not touch a consumer's ``.gitignore``."""
        target = kit_module.wire(project, kit, "path")
        assert (target / ".gitignore").read_text(encoding="utf-8").strip().endswith("*")

    def test_the_stamp_records_what_produced_what(self, project, kit):
        kit_module.wire(project, kit, "copy")
        stamp = kit_module.read_stamp(project)
        assert stamp == {
            "mode": "copy",
            "source": str(kit),
            "package": project.package,
            "generated_by": "imio.recipe.emailkit",
        }

    def test_no_stamp_before_the_first_wiring(self, project):
        assert kit_module.read_stamp(project) is None


class TestFailingLoud:
    def test_an_unknown_mode(self, project, kit):
        with pytest.raises(kit_module.KitError, match="kit-mode"):
            kit_module.wire(project, kit, "symlink")

    def test_a_missing_kit_directory(self, project, tmp_path):
        with pytest.raises(kit_module.KitError, match="does not exist"):
            kit_module.wire(project, tmp_path / "nope", "path")

    def test_a_package_with_no_sources_says_why_that_is_normal(self, tmp_path, kit):
        from imio.recipe.emailkit import projects

        package_dir = tmp_path / "installed" / "acme"
        package_dir.mkdir(parents=True)
        installed = projects.make_project("acme", package_dir)
        with pytest.raises(kit_module.KitError, match="pruned from the sdist"):
            kit_module.wire(installed, kit, "path")
