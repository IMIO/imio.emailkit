"""The plumbing the three scripts share: option precedence and discovery output."""

from imio.recipe.emailkit import check_emails
from imio.recipe.emailkit import cli
from imio.recipe.emailkit import compile_emails
from imio.recipe.emailkit import preview_emails

import pytest


class TestOptionPrecedence:
    """Defaults < the part's baked-in ``config`` < the command line."""

    def test_defaults_when_there_is_no_config_at_all(self):
        arguments = compile_emails.parser().parse_args([])
        merged = cli.settings(None, arguments)
        assert merged["kit_mode"] == "path"
        assert merged["node_bin"] == "node"

    def test_the_parts_config_beats_the_defaults(self):
        arguments = compile_emails.parser().parse_args([])
        merged = cli.settings({"kit_mode": "copy", "kit_dir": "/kit"}, arguments)
        assert merged["kit_mode"] == "copy"
        assert merged["kit_dir"] == "/kit"

    def test_the_command_line_beats_the_parts_config(self):
        """So a developer can try ``--kit-mode copy`` without editing buildout.cfg."""
        arguments = compile_emails.parser().parse_args(["--kit-mode", "copy"])
        merged = cli.settings({"kit_mode": "path"}, arguments)
        assert merged["kit_mode"] == "copy"

    def test_a_none_in_the_config_does_not_erase_a_default(self):
        arguments = compile_emails.parser().parse_args([])
        merged = cli.settings({"node_bin": None}, arguments)
        assert merged["node_bin"] == "node"


class TestTheThreeParsers:
    @pytest.mark.parametrize("module", [compile_emails, check_emails, preview_emails])
    def test_every_script_accepts_the_shared_options(self, module):
        arguments = module.parser().parse_args(
            ["--package", "acme", "--kit-mode", "copy", "--list", "-v"]
        )
        assert arguments.package == "acme"
        assert arguments.kit_mode == "copy"
        assert arguments.list is True
        assert arguments.verbose is True

    def test_compile_emails_accepts_watch_and_new(self):
        arguments = compile_emails.parser().parse_args(["--watch", "--new", "x"])
        assert arguments.watch is True
        assert arguments.new == "x"

    def test_check_emails_can_run_either_check_alone(self):
        assert check_emails.parser().parse_args(["--no-lint"]).no_lint is True
        assert check_emails.parser().parse_args(["--lint-only"]).lint_only is True

    def test_an_unknown_kit_mode_is_refused_by_the_parser(self):
        with pytest.raises(SystemExit):
            compile_emails.parser().parse_args(["--kit-mode", "symlink"])


class TestReporting:
    def test_discovery_output_names_the_kit_the_mode_and_every_directory(
        self, project, kit, capsys
    ):
        cli.print_discovery([project], kit, {"kit_mode": "path"})
        out = capsys.readouterr().out
        assert str(kit) in out
        assert "kit-mode = path" in out
        assert str(project.templates_dir) in out
        assert str(project.emails_dir) in out

    def test_a_package_with_no_sources_is_reported_as_normal_not_broken(
        self, tmp_path, capsys
    ):
        from imio.recipe.emailkit import projects

        package_dir = tmp_path / "installed" / "acme"
        package_dir.mkdir(parents=True)
        installed = projects.make_project("acme", package_dir)
        assert cli.nothing_to_do([installed], "compile") == []
        out = capsys.readouterr().out
        assert "normal for an installed egg" in out
