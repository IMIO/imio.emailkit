"""The one module that knows Node exists (SPEC §1: a developer/CI tool only)."""

from conftest import invocations
from conftest import NPM_LOG
from imio.recipe.emailkit import node as node_module

import os
import pytest


class TestResolvingTheToolchain:
    def test_a_bare_name_is_looked_up_on_path(self, node_on_path):
        binary, _logs = node_on_path
        node, npm, npx = node_module.resolve("node")
        assert (node, npm, npx) == (
            str(binary / "node"),
            str(binary / "npm"),
            str(binary / "npx"),
        )

    def test_npm_and_npx_are_taken_beside_an_explicit_node_bin(self, node_on_path):
        """§5 names only ``node-bin``; one option, three executables."""
        binary, _logs = node_on_path
        node, npm, npx = node_module.resolve(str(binary / "node"))
        assert node == str(binary / "node")
        assert npm == str(binary / "npm")
        assert npx == str(binary / "npx")

    def test_a_node_bin_whose_siblings_are_missing_says_which_one(self, tmp_path):
        lonely = tmp_path / "bin"
        lonely.mkdir()
        (lonely / "node").write_text("#!/bin/sh\n", encoding="utf-8")
        with pytest.raises(node_module.NodeError, match="npm"):
            node_module.resolve(str(lonely / "node"))

    def test_no_node_anywhere_explains_that_nothing_else_needs_it(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))
        with pytest.raises(node_module.NodeError) as raised:
            node_module.resolve("node")
        message = str(raised.value)
        assert "buildout never invokes it" in message

    def test_available_never_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))
        assert node_module.available("node") is False


class TestTheNpmStalenessCheck:
    """SPEC §5: ``npm ci`` "only if ``node_modules`` is stale vs. lockfile"."""

    def test_no_node_modules_means_install(self, project, node_on_path):
        binary, logs = node_on_path
        (project.emails_dir / "package-lock.json").write_text("{}", encoding="utf-8")
        assert node_module.ensure_dependencies(project.emails_dir, str(binary / "npm"))
        assert invocations(logs, NPM_LOG) == ["ci"]

    def test_a_matching_stamp_skips_the_install(self, project, node_on_path):
        binary, logs = node_on_path
        (project.emails_dir / "package-lock.json").write_text("{}", encoding="utf-8")
        node_module.ensure_dependencies(project.emails_dir, str(binary / "npm"))
        assert not node_module.ensure_dependencies(
            project.emails_dir, str(binary / "npm")
        )
        assert invocations(logs, NPM_LOG) == ["ci"]

    def test_a_changed_lockfile_reinstalls(self, project, node_on_path):
        binary, logs = node_on_path
        lockfile = project.emails_dir / "package-lock.json"
        lockfile.write_text("{}", encoding="utf-8")
        node_module.ensure_dependencies(project.emails_dir, str(binary / "npm"))
        lockfile.write_text('{"changed": true}', encoding="utf-8")
        assert node_module.ensure_dependencies(project.emails_dir, str(binary / "npm"))
        assert invocations(logs, NPM_LOG) == ["ci", "ci"]

    def test_the_digest_answers_the_question_mtimes_only_approximate(
        self, project, node_on_path
    ):
        """A touched-but-unchanged lockfile must not trigger a reinstall.

        The Makefile precursor compares mtimes, which npm and git both perturb for
        unrelated reasons. A digest of the lockfile is the actual question §5 asks.
        """
        binary, logs = node_on_path
        lockfile = project.emails_dir / "package-lock.json"
        lockfile.write_text("{}", encoding="utf-8")
        node_module.ensure_dependencies(project.emails_dir, str(binary / "npm"))
        os.utime(lockfile, (10**9, 10**9))
        assert not node_module.ensure_dependencies(
            project.emails_dir, str(binary / "npm")
        )
        assert invocations(logs, NPM_LOG) == ["ci"]

    def test_no_lockfile_falls_back_to_npm_install(self, project, node_on_path):
        """``npm ci`` needs a lockfile; the fallback is also what creates one."""
        binary, logs = node_on_path
        assert node_module.ensure_dependencies(project.emails_dir, str(binary / "npm"))
        assert invocations(logs, NPM_LOG) == ["install"]

    def test_force_reinstalls_regardless(self, project, node_on_path):
        binary, logs = node_on_path
        (project.emails_dir / "package-lock.json").write_text("{}", encoding="utf-8")
        node_module.ensure_dependencies(project.emails_dir, str(binary / "npm"))
        node_module.ensure_dependencies(
            project.emails_dir, str(binary / "npm"), force=True
        )
        assert invocations(logs, NPM_LOG) == ["ci", "ci"]

    def test_a_directory_that_is_not_an_npm_project_fails_loud(
        self, tmp_path, node_on_path
    ):
        binary, _logs = node_on_path
        with pytest.raises(node_module.NodeError, match=r"package\.json"):
            node_module.ensure_dependencies(tmp_path, str(binary / "npm"))


class TestRunningCommands:
    def test_a_non_zero_exit_raises_with_the_command_in_the_message(
        self, project, node_on_path
    ):
        binary, _logs = node_on_path
        os.environ["EMAILKIT_FAKE_EXIT"] = "7"
        with pytest.raises(node_module.NodeError, match="exited 7"):
            node_module.build(project.emails_dir, str(binary / "npx"))

    def test_a_missing_executable_raises_rather_than_tracebacks(self, project):
        with pytest.raises(node_module.NodeError, match="could not run"):
            node_module.run(["/definitely/not/here"], cwd=project.emails_dir)

    def test_watch_delegates_to_maizzles_dev_server(self, project, node_on_path):
        """§5: "``--watch`` delegates to Maizzle's dev server"."""
        binary, logs = node_on_path
        node_module.build(project.emails_dir, str(binary / "npx"), watch=True)
        assert invocations(logs, "npx.log") == ["maizzle dev"]
