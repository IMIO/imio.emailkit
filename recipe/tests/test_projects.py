"""SPEC §5 step 1: which packages ship templates, and where their directories are."""

from imio.recipe.emailkit import projects

import pytest


class TestTheEntryPointGroup:
    def test_it_matches_the_runtime_exactly(self):
        """The one string this distribution duplicates on purpose.

        ``imio.emailkit.discovery`` owns it at runtime; the recipe restates it so
        that neither buildout nor a build script has to import the Plone runtime to
        find out what to look for. Duplication is only safe with a test that fails
        when the two drift, which is this one. Skipped, not passed, where the
        runtime is not installed -- a skip says "unverified", a pass would lie.
        """
        discovery = pytest.importorskip(
            "imio.emailkit.discovery",
            reason="imio.emailkit is not installed in this environment",
        )
        assert projects.ENTRY_POINT_GROUP == discovery.ENTRY_POINT_GROUP
        assert projects.DEFAULT_DIRECTORY == discovery.DEFAULT_DIRECTORY


class TestFindingTheMaizzleProject:
    def test_in_package_layout(self, consumer):
        """SPEC §4 draws ``emails/`` inside the package."""
        assert projects.find_emails_dir(consumer) == consumer / "emails"

    def test_root_layout(self, root_layout_consumer):
        """``imio.emailkit``'s own shape: four levels up, beside ``src/``."""
        found = projects.find_emails_dir(root_layout_consumer)
        assert found == root_layout_consumer.parents[2] / "emails"

    def test_an_emails_directory_without_a_config_is_not_a_maizzle_project(
        self, tmp_path
    ):
        """The check that stops a content folder called `emails` being picked up."""
        package_dir = tmp_path / "pkg"
        (package_dir / "emails").mkdir(parents=True)
        assert projects.find_emails_dir(package_dir) is None

    def test_none_when_the_sources_are_not_shipped(self, tmp_path):
        """The normal answer for an installed egg: §4 prunes ``emails/``."""
        package_dir = tmp_path / "installed" / "acme"
        package_dir.mkdir(parents=True)
        assert projects.find_emails_dir(package_dir) is None

    def test_it_does_not_ascend_past_the_limit(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f" / "g"
        deep.mkdir(parents=True)
        (tmp_path / "emails").mkdir()
        (tmp_path / "emails" / "maizzle.config.js").write_text("x", encoding="utf-8")
        assert projects.find_emails_dir(deep) is None


class TestTheProjectRecord:
    def test_it_records_spec_5s_triple(self, project, consumer):
        assert project.package == "acme.notifications"
        assert project.package_dir == consumer
        assert project.templates_dir == consumer / "templates"
        assert project.emails_dir == consumer / "emails"

    def test_the_registration_can_move_the_templates_directory(self, consumer):
        moved = projects.make_project("acme.notifications", consumer, "mails")
        assert moved.templates_dir == consumer / "mails"

    def test_a_missing_directory_key_means_templates(self, consumer):
        assert (
            projects.make_project("a", consumer, None).templates_dir.name == "templates"
        )

    def test_derived_paths(self, project, consumer):
        assert project.root == consumer
        assert project.sources_dir == consumer / "emails" / "src" / "templates"
        assert project.twins_dir == consumer / "emails" / "twins"
        assert project.tests_dir == consumer / "tests"
        assert project.compilable is True

    def test_an_installed_egg_is_not_compilable_and_says_so_without_raising(
        self, tmp_path
    ):
        package_dir = tmp_path / "installed" / "acme"
        package_dir.mkdir(parents=True)
        installed = projects.make_project("acme", package_dir)
        assert installed.compilable is False
        assert installed.emails_dir is None
        assert installed.sources_dir is None
        assert installed.vue_sources() == []
        # templates_dir is still known: it is where the `.pt` are *read* from.
        assert installed.templates_dir == package_dir / "templates"

    def test_vue_sources_finds_the_authored_templates(self, project):
        assert [path.name for path in project.vue_sources()] == ["hello.vue"]

    def test_vue_sources_includes_the_kit_only_for_the_package_that_ships_it(
        self, project, consumer
    ):
        """The design system is linted by its owner, and by nobody else.

        A consumer must not be told to fix a file inside an installed egg, and the
        kit must not escape the lint just because it lives outside
        ``emails/src/templates``.
        """
        assert project.kit_dir is None
        (consumer / "kit" / "layouts").mkdir(parents=True)
        (consumer / "kit" / "layouts" / "Main.vue").write_text(
            "<template/>", encoding="utf-8"
        )
        owner = projects.make_project("acme.notifications", consumer)
        assert owner.kit_dir == consumer / "kit"
        # Sorted by full path, so `emails/...` precedes `kit/...`.
        assert [path.name for path in owner.vue_sources()] == ["hello.vue", "Main.vue"]

    def test_tests_dir_falls_back_to_the_package(self, root_layout_consumer):
        """``<root>/tests`` when the checkout has one, else ``<package>/tests``."""
        project = projects.make_project("acme.roots", root_layout_consumer)
        assert project.tests_dir == root_layout_consumer.parents[2] / "tests"


class TestSelection:
    def test_no_package_means_all_of_them(self, project):
        assert projects.select([project]) == [project]

    def test_an_unknown_package_fails_loud_and_lists_what_there_was(self, project):
        with pytest.raises(projects.ProjectError) as raised:
            projects.select([project], "acme.typo")
        message = str(raised.value)
        assert "acme.typo" in message
        # A --package typo that silently compiled nothing would look exactly like
        # a successful build, so the message has to name the alternatives.
        assert "acme.notifications" in message


class FakeDist:
    def __init__(self, location, project_name="acme.notifications"):
        self.location = str(location)
        self.project_name = project_name

    @property
    def key(self):
        return self.project_name.lower()


class FakeEntryPoint:
    def __init__(self, name, module_name, dist):
        self.name = name
        self.module_name = module_name
        self.dist = dist


class FakeWorkingSet:
    def __init__(self, entry_points, dists=()):
        self._entry_points = list(entry_points)
        self._dists = list(dists) or [ep.dist for ep in entry_points]

    def iter_entry_points(self, group):
        return iter(self._entry_points)

    def __iter__(self):
        return iter(self._dists)


class TestCollectingFromBuildout:
    def test_it_resolves_a_package_off_dist_metadata_without_importing(self, consumer):
        dist = FakeDist(consumer.parents[1])
        working_set = FakeWorkingSet(
            [FakeEntryPoint("acme.notifications", "acme.notifications", dist)]
        )
        found = projects.from_working_set(working_set)
        assert [p.package for p in found] == ["acme.notifications"]
        assert found[0].package_dir == consumer

    def test_it_finds_a_src_layout_develop_egg(self, root_layout_consumer):
        """``dist.location`` can be the project root rather than its ``src``."""
        checkout = root_layout_consumer.parents[2]
        dist = FakeDist(checkout, "acme.roots")
        working_set = FakeWorkingSet([FakeEntryPoint("acme.roots", "acme.roots", dist)])
        found = projects.from_working_set(working_set)
        assert found[0].package_dir == root_layout_consumer

    def test_a_shadowed_installed_copy_is_silent(self, consumer, caplog):
        """A develop egg shadowing an installed one is the everyday case.

        Both distributions answer for the name and only one has the files. Warning
        about the other would put a permanent, meaningless warning in front of
        every buildout run, which is how people learn to ignore warnings.
        """
        good = FakeEntryPoint(
            "acme.notifications", "acme.notifications", FakeDist(consumer.parents[1])
        )
        empty = FakeEntryPoint(
            "acme.notifications", "acme.notifications", FakeDist("/nowhere")
        )
        found = projects.from_working_set(FakeWorkingSet([empty, good]))
        assert [p.package for p in found] == ["acme.notifications"]
        assert "could not be located" not in caplog.text

    def test_a_genuinely_broken_registration_warns_and_is_skipped(self, caplog):
        broken = FakeEntryPoint("acme.gone", "acme.gone", FakeDist("/nowhere"))
        assert projects.from_working_set(FakeWorkingSet([broken])) == []
        assert "could not be located" in caplog.text


class TestResolvingTheKit:
    def test_it_finds_the_kit_in_the_emailkit_egg(self, kit):
        dist = FakeDist(kit.parents[2], "imio.emailkit")
        working_set = FakeWorkingSet([], [dist])
        assert projects.kit_dir_from_working_set(working_set) == kit

    def test_a_dash_spelled_project_name_still_matches(self, kit):
        dist = FakeDist(kit.parents[2], "imio-emailkit")
        assert projects.kit_dir_from_working_set(FakeWorkingSet([], [dist])) == kit

    def test_no_emailkit_in_the_part_fails_loud(self):
        with pytest.raises(projects.ProjectError) as raised:
            projects.kit_dir_from_working_set(FakeWorkingSet([], []))
        assert "instance:eggs" in str(raised.value)

    def test_an_emailkit_without_a_kit_directory_fails_loud(self, tmp_path):
        package_dir = tmp_path / "sp" / "imio" / "emailkit"
        package_dir.mkdir(parents=True)
        dist = FakeDist(tmp_path / "sp", "imio.emailkit")
        with pytest.raises(projects.ProjectError) as raised:
            projects.kit_dir_from_working_set(FakeWorkingSet([], [dist]))
        assert "ships no `kit/`" in str(raised.value)
