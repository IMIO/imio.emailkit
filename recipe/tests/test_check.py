"""``bin/check-emails``: the staleness check and the lint delegation."""

from conftest import invocations
from conftest import NPX_LOG
from imio.recipe.emailkit import check_emails
from imio.recipe.emailkit import kit as kit_module

import os
import pytest
import sys
import textwrap


@pytest.fixture
def wired(project, kit, node_on_path):
    """A project with the kit wired and the fake build pointed at ``templates/``."""
    binary, logs = node_on_path
    os.environ["EMAILKIT_FAKE_OUTPUT"] = str(project.templates_dir)
    kit_module.wire(project, kit, "path")
    return project, kit, binary, logs


def run_gate(project, kit, binary):
    return check_emails.check_project(
        project,
        kit_dir=kit,
        kit_mode="path",
        npm=str(binary / "npm"),
        npx=str(binary / "npx"),
    )


class TestTheStalenessGate:
    def test_a_matching_committed_file_is_ok(self, wired, capsys):
        project, kit, binary, _logs = wired
        (project.templates_dir / "hello.pt").write_text(
            "<html>built ${title}</html>\n", encoding="utf-8"
        )
        assert run_gate(project, kit, binary) == 0
        assert "ok" in capsys.readouterr().out

    def test_a_tampered_file_is_stale_and_shows_a_diff(self, wired, capsys):
        project, kit, binary, _logs = wired
        (project.templates_dir / "hello.pt").write_text(
            "<html>hand edited</html>\n", encoding="utf-8"
        )
        assert run_gate(project, kit, binary) == 1
        out = capsys.readouterr().out
        assert check_emails.STALE in out
        assert "hand edited" in out
        assert "+++ fresh build" in out

    def test_a_built_file_that_was_never_committed_is_reported(self, wired, capsys):
        project, kit, binary, _logs = wired
        assert run_gate(project, kit, binary) == 1
        assert check_emails.MISSING in capsys.readouterr().out

    def test_a_committed_file_the_build_no_longer_produces_is_an_orphan(
        self, wired, capsys
    ):
        project, kit, binary, _logs = wired
        (project.templates_dir / "hello.pt").write_text(
            "<html>built ${title}</html>\n", encoding="utf-8"
        )
        (project.templates_dir / "gone.pt").write_text(
            "<html>old</html>\n", encoding="utf-8"
        )
        assert run_gate(project, kit, binary) == 1
        assert check_emails.ORPHAN in capsys.readouterr().out

    def test_hand_written_templates_outside_the_build_are_left_alone(
        self, wired, capsys
    ):
        """A browser view's ``.pt`` must not be reported as an orphan."""
        project, kit, binary, _logs = wired
        (project.templates_dir / "hello.pt").write_text(
            "<html>built ${title}</html>\n", encoding="utf-8"
        )
        views = project.package_dir / "browser" / "templates"
        views.mkdir(parents=True)
        (views / "preview.pt").write_text(
            "<html>hand written</html>\n", encoding="utf-8"
        )
        assert run_gate(project, kit, binary) == 0
        assert "preview.pt" not in capsys.readouterr().out
        assert (views / "preview.pt").exists()

    def test_the_twins_are_copied_in_before_the_diff(self, wired):
        """Otherwise every hand-authored twin would be reported as an ORPHAN."""
        project, kit, binary, _logs = wired
        (project.twins_dir / "hello.txt.pt").write_text(
            "plain ${title}\n", encoding="utf-8"
        )
        (project.templates_dir / "hello.pt").write_text(
            "<html>built ${title}</html>\n", encoding="utf-8"
        )
        (project.templates_dir / "hello.txt.pt").write_text(
            "plain ${title}\n", encoding="utf-8"
        )
        assert run_gate(project, kit, binary) == 0


class TestRestoringTheWorkingTree:
    def test_the_committed_output_is_put_back_byte_for_byte(self, wired):
        project, kit, binary, _logs = wired
        committed = project.templates_dir / "hello.pt"
        committed.write_text("<html>hand edited</html>\n", encoding="utf-8")
        run_gate(project, kit, binary)
        assert committed.read_text(encoding="utf-8") == "<html>hand edited</html>\n"

    def test_a_file_the_build_created_is_removed_again(self, wired):
        project, kit, binary, _logs = wired
        run_gate(project, kit, binary)
        assert not (project.templates_dir / "hello.pt").exists()

    def test_restoration_happens_even_when_the_build_fails(self, wired):
        project, kit, binary, _logs = wired
        committed = project.templates_dir / "hello.pt"
        committed.write_text("<html>committed</html>\n", encoding="utf-8")
        os.environ["EMAILKIT_FAKE_EXIT"] = "1"
        from imio.recipe.emailkit import node as node_module

        with pytest.raises(node_module.NodeError):
            run_gate(project, kit, binary)
        assert committed.read_text(encoding="utf-8") == "<html>committed</html>\n"

    def test_the_build_really_did_run(self, wired):
        project, kit, binary, logs = wired
        run_gate(project, kit, binary)
        assert any("maizzle build" in line for line in invocations(logs, NPX_LOG))


#: A stand-in for ``imio.emailkit.lint``, under a name nothing else can shadow.
STUB_MODULE = "emailkit_lint_stub"


@pytest.fixture
def stub_lint(tmp_path, monkeypatch):
    """Install a fake lint module and reach it exactly the way the check does."""

    def install(body):
        root = tmp_path / "stub"
        root.mkdir(exist_ok=True)
        (root / f"{STUB_MODULE}.py").write_text(textwrap.dedent(body), encoding="utf-8")
        monkeypatch.syspath_prepend(str(root))
        return root

    return install


class TestTheLintGate:
    def test_it_invokes_the_module_by_the_agreed_interface(
        self, project, tmp_path, stub_lint
    ):
        """``python -m <module> <paths>``, verbatim."""
        stub_lint(f"""
            import sys
            open({str(tmp_path / "argv.txt")!r}, "w").write("\\n".join(sys.argv[1:]))
            sys.exit(0)
            """)
        assert check_emails.lint_gate([project], module=STUB_MODULE) == 0
        linted = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
        assert linted == [str(path) for path in project.vue_sources()]

    def test_a_non_zero_lint_fails_the_gate(self, project, stub_lint):
        stub_lint("import sys; sys.exit(3)")
        assert check_emails.lint_gate([project], module=STUB_MODULE) == 1

    def test_a_clean_lint_passes_the_gate(self, project, stub_lint):
        stub_lint("import sys; sys.exit(0)")
        assert check_emails.lint_gate([project], module=STUB_MODULE) == 0

    def test_a_missing_lint_module_fails_rather_than_skipping(self, project, capsys):
        """A missing module must fail loud, not report a false success."""
        assert check_emails.lint_gate([project], module="no_such_lint_module") == 1
        assert "not importable" in capsys.readouterr().err

    def test_nothing_to_lint_is_not_a_failure(self, tmp_path):
        from imio.recipe.emailkit import projects

        package_dir = tmp_path / "installed" / "acme"
        package_dir.mkdir(parents=True)
        installed = projects.make_project("acme", package_dir)
        assert check_emails.lint_gate([installed]) == 0

    def test_the_child_gets_this_processs_sys_path(self):
        """``sys.executable`` alone knows nothing about the part's eggs."""
        entries = check_emails._child_environment()["PYTHONPATH"].split(os.pathsep)
        for entry in sys.path:
            if entry:
                assert entry in entries
