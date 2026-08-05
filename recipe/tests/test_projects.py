"""SPEC §5 step 1: which packages ship templates, and where their directories are."""

from imio.recipe.emailkit import projects

import pytest


class TestTheMarker:
    def test_marker_matches_the_runtime(self):
        """The one string this distribution duplicates on purpose.

        ``imio.emailkit.scan`` owns it at runtime; the recipe restates it so that
        neither buildout nor a build script has to import the Plone runtime to
        find out what to look for. Duplication is only safe with a test that fails
        when the two drift, which is this one. Skipped, not passed, where the
        runtime is not installed -- a skip says "unverified", a pass would lie.
        """
        imio_emailkit_scan = pytest.importorskip(
            "imio.emailkit.scan",
            reason="imio.emailkit is not installed in this environment",
        )
        assert projects.MARKER == imio_emailkit_scan.MARKER


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


def make_dist_dir(tmp_path, dotted="acme.mail", marker=True, src_layout=False):
    """A minimal on-disk distribution: a dotted package with a ``configure.zcml``.

    ``marker=False`` writes a ZCML file that mentions a *different* namespace, so
    the marker-scan tests can prove a non-emailkit addon is left alone rather than
    merely proving an addon with no ZCML at all is.
    """
    root = tmp_path / "dist"
    base = root / "src" if src_layout else root
    parts = dotted.split(".")
    package_dir = base.joinpath(*parts)
    package_dir.mkdir(parents=True)
    for depth in range(1, len(parts)):
        (base.joinpath(*parts[:depth]) / "__init__.py").write_text("")
    (package_dir / "__init__.py").write_text("")
    body = "namespaces.imio.be/emailkit" if marker else "namespaces.zope.org"
    (package_dir / "configure.zcml").write_text(
        f"<configure><!-- {body} --></configure>"
    )
    return root, package_dir


class FakeDist:
    """Stands in for a ``pkg_resources`` distribution.

    ``top_level`` feeds :func:`projects._top_level_names`'s metadata branch;
    omitted, the filesystem fallback is exercised instead. ``project_name`` is
    unrelated -- it is what :func:`projects.kit_dir_from_working_set` compares
    against, kept here so both collectors can share one fake.
    """

    def __init__(self, location, project_name="acme.notifications", top_level=()):
        self.location = str(location)
        self.project_name = project_name
        self._top_level = list(top_level)

    @property
    def key(self):
        return self.project_name.lower()

    def get_metadata_lines(self, name):
        if name == "top_level.txt" and self._top_level:
            return list(self._top_level)
        # Real `pkg_resources` providers raise this (`NullProvider.get_metadata`
        # opens the file straight off disk) when the metadata directory exists
        # but the specific file does not, not `KeyError` -- so the fake raises
        # it too, to keep `_top_level_names`'s except clause honest.
        raise FileNotFoundError(name)

    def __str__(self):
        return self.location


class TestCollectingFromBuildout:
    def test_marker_package_found(self, tmp_path):
        root, package_dir = make_dist_dir(tmp_path)
        dist = FakeDist(root, top_level=["acme"])
        found = projects.from_working_set([dist])
        assert [p.package for p in found] == ["acme.mail"]
        assert found[0].package_dir == package_dir

    def test_unmarked_package_ignored(self, tmp_path):
        root, _package_dir = make_dist_dir(tmp_path, marker=False)
        dist = FakeDist(root, top_level=["acme"])
        assert projects.from_working_set([dist]) == []

    def test_src_layout_found(self, tmp_path):
        """``dist.location`` can be the project root rather than its ``src``."""
        root, package_dir = make_dist_dir(tmp_path, src_layout=True)
        dist = FakeDist(root, top_level=["acme"])
        found = projects.from_working_set([dist])
        assert found[0].package_dir == package_dir

    def test_no_top_level_metadata_falls_back_to_filesystem(self, tmp_path):
        root, _package_dir = make_dist_dir(tmp_path)
        dist = FakeDist(root)
        found = projects.from_working_set([dist])
        assert [p.package for p in found] == ["acme.mail"]

    def test_a_marked_file_outside_a_package_directory_is_skipped(
        self, tmp_path, caplog
    ):
        """A ``configure.zcml`` with no ``__init__.py`` beside it is not a package.

        Cannot happen for a real Python package, but a stray ``.zcml`` under a
        data directory should not crash the scan -- it should be logged and
        skipped, the same way a genuinely broken registration used to be.
        """
        root, package_dir = make_dist_dir(tmp_path)
        (package_dir / "__init__.py").unlink()
        dist = FakeDist(root, top_level=["acme"])
        assert projects.from_working_set([dist]) == []
        assert "not a package directory" in caplog.text

    def test_two_dists_agreeing_on_a_name_deduplicate_silently(self, tmp_path):
        """A develop egg shadowing an installed copy is the everyday case.

        Both distributions genuinely have the files (unlike the old entry-point
        world, where one could point at a module that was not there), so there is
        nothing to warn about -- whichever dist sorts first simply wins.
        """
        root_a, _dir_a = make_dist_dir(tmp_path / "a")
        root_b, _dir_b = make_dist_dir(tmp_path / "b")
        dists = [
            FakeDist(root_a, top_level=["acme"]),
            FakeDist(root_b, top_level=["acme"]),
        ]
        found = projects.from_working_set(dists)
        assert [p.package for p in found] == ["acme.mail"]

    def test_an_ancestor_named_like_a_pruned_dir_does_not_hide_the_dist(self, tmp_path):
        """PRUNE_DIRS must match the walked subtree, not the absolute path.

        A checkout parked under `.../emails/dist/...` (or under `node_modules`,
        `.git`, `__pycache__` -- any ancestor happening to share a name with
        :data:`projects.PRUNE_DIRS`) is a perfectly ordinary thing to have on
        disk. Only the directories *inside* the dist's own top-level package
        are supposed to be pruned from the ZCML walk.
        """
        outer = tmp_path / "emails"
        root, package_dir = make_dist_dir(outer, src_layout=True)
        dist = FakeDist(root, top_level=["acme"])
        found = projects.from_working_set([dist])
        assert [p.package for p in found] == ["acme.mail"]
        assert found[0].package_dir == package_dir


class TestTheWalkCache:
    def test_a_shared_top_level_directory_is_walked_once_per_collection(
        self, tmp_path, monkeypatch
    ):
        """N dists sharing one namespace top-level should cost one walk, not N.

        ``top_level.txt`` says ``imio`` for every ``imio.*`` dist, so without
        memoization each of them would re-rglob the whole shared
        ``site-packages/imio/`` subtree.
        """
        root, _package_dir = make_dist_dir(tmp_path, dotted="imio.mail")
        calls = []
        original = projects._scan_top_dir

        def counting(top_dir):
            calls.append(top_dir)
            return original(top_dir)

        monkeypatch.setattr(projects, "_scan_top_dir", counting)

        dist_a = FakeDist(root, project_name="imio.mail", top_level=["imio"])
        dist_b = FakeDist(root, project_name="imio.other", top_level=["imio"])
        cache = {}
        assert [p for p, _d in projects.iter_marker_packages(dist_a, cache)] == [
            "imio.mail"
        ]
        assert [p for p, _d in projects.iter_marker_packages(dist_b, cache)] == [
            "imio.mail"
        ]
        assert len(calls) == 1


class TestCollectingFromEnvironment:
    """``from_environment`` needs a real ``imio.emailkit`` to scan against.

    Skipped, not passed, in the buildout-only test environment -- the recipe's
    own suite runs twice (``make recipe-test``), and this half of the coverage
    is the Plone-runtime run's job.
    """

    def test_a_failed_scan_warns_and_skips_but_others_still_build(
        self, tmp_path, monkeypatch, caplog
    ):
        pytest.importorskip("imio.emailkit.scan")
        pytest.importorskip("pkg_resources")
        from imio.emailkit import discovery

        good_root = tmp_path / "good"
        good_pkg = good_root / "acme_good"
        (good_pkg / "templates").mkdir(parents=True)
        (good_pkg / "templates" / "hello.pt").write_text("<html/>", encoding="utf-8")
        (good_pkg / "__init__.py").write_text("", encoding="utf-8")
        (good_pkg / "configure.zcml").write_text(
            '<configure xmlns="http://namespaces.zope.org/zope"\n'
            '    xmlns:emailkit="http://namespaces.imio.be/emailkit"\n'
            '    i18n_domain="acme_good">\n'
            '  <include package="imio.emailkit" file="meta.zcml" />\n'
            "  <emailkit:templates>\n"
            '    <emailkit:template name="hello" subject="[s_hello] Hello" />\n'
            "  </emailkit:templates>\n"
            "</configure>\n",
            encoding="utf-8",
        )

        # Missing the required `subject` -- a genuine consumer mistake, the same
        # one a real instance would refuse to start on.
        bad_root = tmp_path / "bad"
        bad_pkg = bad_root / "acme_bad"
        bad_pkg.mkdir(parents=True)
        (bad_pkg / "__init__.py").write_text("", encoding="utf-8")
        (bad_pkg / "configure.zcml").write_text(
            '<configure xmlns="http://namespaces.zope.org/zope"\n'
            '    xmlns:emailkit="http://namespaces.imio.be/emailkit"\n'
            '    i18n_domain="acme_bad">\n'
            '  <include package="imio.emailkit" file="meta.zcml" />\n'
            "  <emailkit:templates>\n"
            '    <emailkit:template name="broken" />\n'
            "  </emailkit:templates>\n"
            "</configure>\n",
            encoding="utf-8",
        )

        monkeypatch.syspath_prepend(str(good_root))
        monkeypatch.syspath_prepend(str(bad_root))
        monkeypatch.setattr(
            "pkg_resources.working_set",
            [
                FakeDist(good_root, top_level=["acme_good"]),
                FakeDist(bad_root, top_level=["acme_bad"]),
            ],
        )

        with discovery.overlay():
            discovery.reset()
            found = projects.from_environment()

        assert [p.package for p in found] == ["acme_good"]
        assert "acme_bad" in caplog.text

    def test_a_subpackages_parent_relative_directory_is_found_not_crashed(
        self, tmp_path, monkeypatch, caplog
    ):
        """``directory="../templates"`` is legal (``zcml.py``'s own docstring:
        "a subpackage's block may point at its parent's files with
        `../templates`") and used to crash the whole collection:
        ``templates_dir.relative_to(package_dir)`` cannot express a `..`
        segment and raised, uncaught, past the per-package guard.
        """
        pytest.importorskip("imio.emailkit.scan")
        pytest.importorskip("pkg_resources")
        from imio.emailkit import discovery

        root = tmp_path / "root"
        top_pkg = root / "acme_sub"
        sub_pkg = top_pkg / "sub"
        (top_pkg / "templates").mkdir(parents=True)
        sub_pkg.mkdir(parents=True)
        (top_pkg / "__init__.py").write_text("", encoding="utf-8")
        (sub_pkg / "__init__.py").write_text("", encoding="utf-8")
        (sub_pkg / "configure.zcml").write_text(
            '<configure xmlns="http://namespaces.zope.org/zope"\n'
            '    xmlns:emailkit="http://namespaces.imio.be/emailkit"\n'
            '    i18n_domain="acme_sub.sub">\n'
            '  <include package="imio.emailkit" file="meta.zcml" />\n'
            '  <emailkit:templates directory="../templates">\n'
            '    <emailkit:template name="hello" subject="[s_hello] Hello" />\n'
            "  </emailkit:templates>\n"
            "</configure>\n",
            encoding="utf-8",
        )

        monkeypatch.syspath_prepend(str(root))
        monkeypatch.setattr(
            "pkg_resources.working_set",
            [FakeDist(root, top_level=["acme_sub"])],
        )

        with discovery.overlay():
            discovery.reset()
            found = projects.from_environment()

        assert [p.package for p in found] == ["acme_sub.sub"]
        assert found[0].templates_dir == (top_pkg / "templates").resolve()
        assert "Could not scan" not in caplog.text

    def test_a_shadowed_dist_resolves_to_the_importable_copy(
        self, tmp_path, monkeypatch
    ):
        """Two on-disk copies of one package; only one is on ``sys.path``.

        The marker walk finds ZCML on disk regardless of ``sys.path`` -- it
        never imports anything -- so it can name a directory that Python will
        never actually import from once a develop egg shadows an installed
        copy. ``scan.scan_package`` imports the dotted name for real and
        always executes against whichever copy ``sys.path`` resolves; trusting
        the marker walk's guess instead used to crash outright, because the
        two copies do not even share a prefix to be `..`-relative about.
        """
        pytest.importorskip("imio.emailkit.scan")
        pytest.importorskip("pkg_resources")
        from imio.emailkit import discovery

        def write_copy(root):
            package_dir = root / "acme_shadow"
            (package_dir / "templates").mkdir(parents=True)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_dir / "configure.zcml").write_text(
                '<configure xmlns="http://namespaces.zope.org/zope"\n'
                '    xmlns:emailkit="http://namespaces.imio.be/emailkit"\n'
                '    i18n_domain="acme_shadow">\n'
                '  <include package="imio.emailkit" file="meta.zcml" />\n'
                "  <emailkit:templates>\n"
                '    <emailkit:template name="hello" subject="[s_hello] Hello" />\n'
                "  </emailkit:templates>\n"
                "</configure>\n",
                encoding="utf-8",
            )
            return package_dir

        # Sorts before `importable_root` by `str()`, so it is the copy
        # `from_environment`'s dedup picks first -- the everyday shadowing case.
        not_importable_root = tmp_path / "a_installed"
        importable_root = tmp_path / "z_develop"
        write_copy(not_importable_root)
        importable_pkg = write_copy(importable_root)

        monkeypatch.syspath_prepend(str(importable_root))
        monkeypatch.setattr(
            "pkg_resources.working_set",
            [
                FakeDist(not_importable_root, top_level=["acme_shadow"]),
                FakeDist(importable_root, top_level=["acme_shadow"]),
            ],
        )

        with discovery.overlay():
            discovery.reset()
            found = projects.from_environment()

        assert [p.package for p in found] == ["acme_shadow"]
        assert found[0].package_dir == importable_pkg.resolve()
        assert found[0].templates_dir == (importable_pkg / "templates").resolve()


class TestResolvingTheKit:
    def test_it_finds_the_kit_in_the_emailkit_egg(self, kit):
        dist = FakeDist(kit.parents[2], "imio.emailkit")
        assert projects.kit_dir_from_working_set([dist]) == kit

    def test_a_dash_spelled_project_name_still_matches(self, kit):
        dist = FakeDist(kit.parents[2], "imio-emailkit")
        assert projects.kit_dir_from_working_set([dist]) == kit

    def test_no_emailkit_in_the_part_fails_loud(self):
        with pytest.raises(projects.ProjectError) as raised:
            projects.kit_dir_from_working_set([])
        assert "instance:eggs" in str(raised.value)

    def test_an_emailkit_without_a_kit_directory_fails_loud(self, tmp_path):
        package_dir = tmp_path / "sp" / "imio" / "emailkit"
        package_dir.mkdir(parents=True)
        dist = FakeDist(tmp_path / "sp", "imio.emailkit")
        with pytest.raises(projects.ProjectError) as raised:
            projects.kit_dir_from_working_set([dist])
        assert "ships no `kit/`" in str(raised.value)
