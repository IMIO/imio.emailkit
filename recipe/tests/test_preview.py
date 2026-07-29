"""``bin/preview-emails``: the parts that do not need a Plone runtime.

Rendering itself is covered by the buildout acceptance harness, which has the real
``imio.emailkit`` next door. What is worth unit-testing here is everything around
it: where a fixture is looked for, what the page offers, and what the watcher
watches -- the pieces where a mistake shows up as "the preview is silently empty".
"""

from imio.recipe.emailkit import preview_emails

import pytest
import threading
import time


@pytest.fixture
def configured():
    """The minimal Zope configuration ``preview-emails`` loads before rendering.

    Required by the theme tests and not merely convenient: ``plone.registry``'s ZCML
    is what registers the *persistent field* adapters, without which
    ``Registry.registerInterface`` raises "There is no persistent field equivalent
    for the field ...". That coupling between :func:`configure` and
    :func:`seed_theme` is easy to break silently, so it is exercised here rather
    than worked around.
    """
    pytest.importorskip("plone.registry", reason="needs the Plone runtime")
    pytest.importorskip("imio.emailkit", reason="needs the Plone runtime")
    preview_emails.configure([])


class TestFixtureLookup:
    def test_it_finds_the_spec_7_location(self, project):
        expected = project.tests_dir / "fixtures" / "hello.py"
        expected.write_text("CONTEXT = {}\n", encoding="utf-8")
        assert preview_emails.find_fixture(project, "hello") == expected

    def test_none_when_there_is_no_fixture(self, project):
        assert preview_emails.find_fixture(project, "hello") is None

    def test_a_fixture_is_loaded_by_path_not_imported(self, project):
        """§7 describes a *directory of data files*, not an importable package.

        Loading by path is also what keeps the preview and the golden test from ever
        disagreeing about what a fixture says.
        """
        path = project.tests_dir / "fixtures" / "hello.py"
        path.write_text("CONTEXT = {'title': 'Été'}\n", encoding="utf-8")
        assert preview_emails.load_fixture(path) == {"title": "Été"}
        import sys

        assert "hello" not in sys.modules

    def test_a_fixture_without_a_context_dict_says_so(self, project):
        path = project.tests_dir / "fixtures" / "hello.py"
        path.write_text("CONTEXTT = {}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="CONTEXT"):
            preview_emails.load_fixture(path)


class TestThePage:
    def test_it_offers_every_language_and_every_template(self, tmp_path):
        rows = [("acme:hello", "fr", None), ("acme:hello", "nl", None)]
        preview_emails.write_index(rows, tmp_path, ["fr", "nl"], generation=1)
        body = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert 'data-lang="fr"' in body
        assert 'data-lang="nl"' in body
        assert 'data-stem="acme.hello"' in body

    def test_a_failed_render_is_shown_rather_than_omitted(self, tmp_path):
        rows = [("acme:hello", "fr", "TemplateNotFound: acme:hello")]
        preview_emails.write_index(rows, tmp_path, ["fr"], generation=1)
        body = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "TemplateNotFound" in body

    def test_the_reload_script_lives_in_the_page_and_not_in_the_mails(self, tmp_path):
        """A preview must not change the bytes you came to inspect."""
        preview_emails.write_index([], tmp_path, ["fr"], generation=3, watch=True)
        body = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert preview_emails.VERSION_PATH in body
        assert "window.__generation = 3" in body
        assert "<iframe" in body

    def test_polling_is_off_when_not_watching(self, tmp_path):
        preview_emails.write_index([], tmp_path, ["fr"], generation=1, watch=False)
        body = (tmp_path / "index.html").read_text(encoding="utf-8")
        assert "const WATCHING = false" in body


class TestTheWatcher:
    def test_it_watches_sources_fixtures_and_twins_but_not_the_output(self, project):
        (project.tests_dir / "fixtures" / "hello.py").write_text(
            "CONTEXT={}", encoding="utf-8"
        )
        (project.twins_dir / "hello.txt.pt").write_text("x", encoding="utf-8")
        (project.templates_dir / "hello.pt").write_text("x", encoding="utf-8")
        watched = {path.name for path in preview_emails.watched_paths([project])}
        assert watched == {"hello.vue", "hello.py", "hello.txt.pt"}
        # The compiled output is what a pass *produces*; watching it would make
        # every rebuild trigger another rebuild.
        assert "hello.pt" not in watched

    def _run(self, project, pass_once):
        """Start the loop, change a source, wait for one pass, stop.

        The change has to happen *after* the loop has taken its first fingerprint,
        which is why this drives a real thread instead of pre-editing the file: a
        test that edited first would leave the loop with nothing to notice, and
        would hang rather than fail.
        """
        stop = threading.Event()
        done = threading.Event()

        def wrapped():
            try:
                pass_once()
            finally:
                done.set()

        thread = threading.Thread(
            target=preview_emails.watch_loop,
            args=([project], wrapped, stop),
            kwargs={"interval": 0.01},
            daemon=True,
        )
        thread.start()
        time.sleep(0.05)
        (project.sources_dir / "hello.vue").write_text(
            "<template><div>changed</div></template>", encoding="utf-8"
        )
        assert done.wait(10), "the watcher never noticed the change"
        stop.set()
        thread.join(10)
        assert not thread.is_alive()

    def test_a_changed_source_triggers_a_pass(self, project):
        passes = []
        self._run(project, lambda: passes.append(1))
        assert passes

    def test_an_exception_in_a_pass_does_not_kill_the_watcher(self, project, capsys):
        """A watcher that dies on a half-saved file is a watcher you restart all day."""
        calls = []

        def pass_once():
            calls.append(1)
            raise RuntimeError("bad save")

        self._run(project, pass_once)
        assert calls
        assert "bad save" in capsys.readouterr().err


class TestTheThemePanelInItsCommandLineForm:
    def test_it_parses_token_equals_value(self):
        assert preview_emails._theme_overrides(["primary_color=#123456"]) == {
            "primary_color": "#123456"
        }

    def test_a_missing_equals_sign_is_refused(self):
        with pytest.raises(SystemExit):
            preview_emails._theme_overrides(["primary_color"])

    def test_it_seeds_the_kits_own_defaults(self, configured):
        """Without a registry every token collapses to the empty string.

        The preview would then show an unbranded shell and an empty
        ``primary_color`` where a colour belongs, which reads as a broken kit rather
        than as a missing site.
        """
        registry = preview_emails.seed_theme({})
        assert registry["imio.emailkit.theme.primary_color"]

    def test_an_unknown_token_is_refused_rather_than_silently_ignored(self, configured):
        """A typo'd token that did nothing would look like a broken kit."""
        with pytest.raises(ValueError, match="not a theme token"):
            preview_emails.seed_theme({"primaryColour": "#123456"})

    def test_an_override_reaches_the_registry(self, configured):
        registry = preview_emails.seed_theme({"primary_color": "#123456"})
        assert registry["imio.emailkit.theme.primary_color"] == "#123456"
