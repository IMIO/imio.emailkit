"""The CI contract, run against the two dummy consumer add-ons.

Every consumer add-on's CI must run ``bin/check-emails`` (build output is
not stale, sources pass the authoring lint) and its golden-file tests
(runtime rendering is intact). Each check is shown both passing and
failing here, so a check that silently compares nothing cannot look like a
passing one. Node-dependent tests skip when the toolchain is absent; each
failing case also has a Node-free twin.
"""

from pathlib import Path

import dummyaddons
import importlib.util
import pytest
import shutil
import support


support.require_runtime()


NODE_MISSING = (
    "Node is not available (npx and/or emails/node_modules). The staleness "
    "check compiles the add-on and diffs against the committed output, so it "
    "cannot run without the Maizzle toolchain. The failing-side assertions "
    "below do not need Node and still run."
)


@pytest.fixture(autouse=True)
def dummy_addons_installed():
    with dummyaddons.installed() as addons:
        yield addons


@pytest.fixture(params=dummyaddons.ADDONS, ids=lambda a: a.package)
def addon(request):
    return request.param


def require_node():
    if not dummyaddons.node_available():
        pytest.skip(NODE_MISSING)


class TestTheContractIsWiredUp:
    """Every artifact both checks need, for every registered template."""

    def test_the_addon_ships_maizzle_sources(self, addon):
        sources = sorted(
            p.name for p in (addon.emails_dir / "src" / "templates").glob("*.vue")
        )
        expected = sorted(f"{name}.vue" for name in addon.templates)

        assert sources == expected, (
            f"{addon.package}: `emails/src/templates/` holds {sources}, but its "
            f"registration declares {list(addon.templates)}"
        )

    def test_the_addon_ships_a_maizzle_config(self, addon):
        assert (addon.emails_dir / "maizzle.config.js").is_file()

    def test_every_registered_template_has_committed_build_output(self, addon):
        missing = [
            f"{name}.pt"
            for name in addon.templates
            if not (addon.templates_dir / f"{name}.pt").is_file()
        ]

        assert missing == [], (
            f"{addon.package}: registered but not committed: {missing}. The "
            "compiled output is committed to git; a registration without it is "
            "skipped at discovery with a warning nobody reads."
        )

    def test_every_registered_template_has_a_fixture(self, addon):
        missing = [
            name
            for name in addon.templates
            if not (addon.fixtures_dir / f"{name}.py").is_file()
        ]

        assert missing == [], f"{addon.package}: no fixture for {missing}"

    def test_every_snapshotted_template_has_a_complete_set(self, addon):
        """Whatever is snapshotted is snapshotted completely: a French
        snapshot with no English one means an interrupted golden-update run."""
        snapshotted = {
            path.name.split(".")[0] for path in addon.golden_dir.glob("*.*.*")
        }
        missing = [
            f"{name}.{language}.{suffix}"
            for name in sorted(snapshotted)
            for language in addon.languages
            for suffix in ("html", "txt")
            if not (addon.golden_dir / f"{name}.{language}.{suffix}").is_file()
        ]

        assert missing == [], (
            f"{addon.package}: incomplete snapshot set, missing {missing}. "
            "Re-run EMAILKIT_UPDATE_GOLDEN=1, or delete the partial set."
        )

    def test_no_snapshot_outlives_its_template(self, addon):
        """A snapshot for a template that is no longer registered is dead
        weight: no test reads it and no target regenerates it."""
        snapshotted = {
            path.name.split(".")[0] for path in addon.golden_dir.glob("*.*.*")
        }
        orphans = sorted(snapshotted - set(addon.templates))

        assert orphans == [], (
            f"{addon.package}: snapshots for unregistered templates: {orphans}"
        )

    def test_the_addon_has_its_own_test_suite_using_the_shipped_base_class(self, addon):
        """Must import the base class from the egg, not a copy."""
        modules = sorted(addon.suite_dir.glob("test_*.py"))

        assert modules, f"{addon.package} ships no test module in {addon.suite_dir}"
        sources = "\n".join(p.read_text(encoding="utf-8") for p in modules)
        assert "from imio.emailkit.golden import GoldenTemplateTests" in sources, (
            f"{addon.package}'s suite does not import the shipped base class"
        )

    def test_only_declared_twins_are_committed(self, addon):
        """``maizzle build`` empties its output directory, so a twin that
        only exists in ``templates/`` silently disappears on the next build."""
        committed = sorted(p.name for p in addon.templates_dir.glob("*.txt.pt"))
        sourced = sorted(f"{name}.txt.pt" for name in addon.twins)

        assert committed == sourced, (
            f"{addon.package}: committed twins {committed} do not match the ones "
            f"sourced in emails/twins/ ({sourced}). A twin that exists only in "
            "templates/ is deleted by the next build."
        )


class TestStalenessGate:
    """The committed ``.pt`` files must match what a fresh build produces."""

    def test_committed_output_is_not_stale(self, addon):
        """The passing case: compiles the add-on for real."""
        require_node()

        committed, fresh = dummyaddons.rebuild(addon)
        report = dummyaddons.compare_output(committed, fresh)

        assert report, "the staleness gate compared nothing, which is not a pass"
        assert not dummyaddons.is_stale(report), (
            f"{addon.package}: committed email templates are stale.\n"
            + dummyaddons.format_report(report)
        )

    def test_the_gate_goes_red_when_a_committed_template_is_edited(self, addon):
        """Simulates a hand-edited compiled ``.pt`` file. Restored after."""
        require_node()

        target = addon.templates_dir / f"{addon.templates[0]}.pt"
        original = target.read_bytes()
        try:
            target.write_bytes(original.replace(b"<h1", b"<h2", 1))
            _committed, fresh = dummyaddons.rebuild(addon)
            report = dummyaddons.compare_output(addon.templates_dir, fresh)
        finally:
            target.write_bytes(original)

        assert dummyaddons.is_stale(report), (
            "a hand-edited compiled template was reported as up to date:\n"
            + dummyaddons.format_report(report)
        )
        assert (dummyaddons.STALE, target.name) in report, (
            f"the report does not name {target.name}:\n"
            + dummyaddons.format_report(report)
        )
        assert target.read_bytes() == original, "the tampered file was not restored"

    # The same three failures, without Node.

    @pytest.fixture
    def two_trees(self, tmp_path, addon):
        """Two identical trees."""
        committed, fresh = tmp_path / "committed", tmp_path / "fresh"
        shutil.copytree(addon.templates_dir, committed)
        shutil.copytree(addon.templates_dir, fresh)
        return committed, fresh

    def test_identical_trees_are_reported_clean(self, two_trees):
        committed, fresh = two_trees
        report = dummyaddons.compare_output(committed, fresh)

        assert report
        assert not dummyaddons.is_stale(report)
        assert {status for status, _ in report} == {dummyaddons.OK}

    def test_a_changed_byte_is_STALE(self, two_trees):
        committed, fresh = two_trees
        target = sorted(fresh.glob("*.pt"))[0]
        target.write_text(
            target.read_text(encoding="utf-8") + "<!-- rebuilt -->\n", encoding="utf-8"
        )

        report = dummyaddons.compare_output(committed, fresh)

        assert (dummyaddons.STALE, target.name) in report
        assert dummyaddons.is_stale(report)

    def test_a_built_but_uncommitted_template_is_MISSING(self, two_trees):
        """Built but not committed: it would never ship."""
        committed, fresh = two_trees
        (fresh / "brand_new.pt").write_text("<html></html>\n", encoding="utf-8")

        report = dummyaddons.compare_output(committed, fresh)

        assert (dummyaddons.MISSING, "brand_new.pt") in report
        assert dummyaddons.is_stale(report)

    def test_a_committed_but_no_longer_built_template_is_ORPHAN(self, two_trees):
        """Dead weight nothing regenerates."""
        committed, fresh = two_trees
        target = sorted(fresh.glob("*.pt"))[0]
        target.unlink()

        report = dummyaddons.compare_output(committed, fresh)

        assert (dummyaddons.ORPHAN, target.name) in report
        assert dummyaddons.is_stale(report)


class TestAuthoringLintGate:
    """The authoring lint half of ``bin/check-emails``, over the dummies'
    sources. Run through the CLI, since the exit code is what CI reads."""

    @staticmethod
    def lint(*paths):
        import subprocess
        import sys

        if importlib.util.find_spec("imio.emailkit.lint") is None:
            pytest.skip("imio.emailkit.lint is not available in this checkout")
        # S603: the argument list is this module's own literals plus paths
        # from tests/dummyaddons.py's constants. Nothing here is user input.
        return subprocess.run(  # noqa: S603
            [sys.executable, "-m", "imio.emailkit.lint", *[str(p) for p in paths]],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )

    def test_the_dummy_sources_are_lint_clean(self, addon):
        result = self.lint(addon.emails_dir)

        assert result.returncode == 0, (
            f"{addon.package}'s .vue sources violate the authoring rules -- which "
            "would make them documentation of how to get it wrong:\n"
            f"{result.stdout}\n{result.stderr}"
        )

    def test_the_lint_gate_goes_red_on_a_placeholder_in_a_style_attribute(
        self, tmp_path
    ):
        """A ``${...}`` in a literal ``style`` attribute kills CSS inlining
        for the whole document, with a successful build."""
        source = tmp_path / "broken.vue"
        source.write_text(
            "<template>\n"
            "  <KitMain>\n"
            '    <td style="background-color: ${primary_color}">x</td>\n'
            "  </KitMain>\n"
            "</template>\n",
            encoding="utf-8",
        )

        result = self.lint(source)

        assert result.returncode != 0, (
            "a Chameleon placeholder in a literal style attribute was not "
            f"reported:\n{result.stdout}\n{result.stderr}"
        )


class TestGoldenGate:
    """The golden-file check, shown failing, on a throwaway subclass of the
    shipped base class pointed at a tampered snapshot. ``layer_fixture =
    None``: the Plone site is already up through this module's own fixture.
    """

    ADDON = dummyaddons.COMPLETE
    TEMPLATE = "convocation"
    LANGUAGE = "fr"
    HTML = ("html", 0)

    @pytest.fixture
    def harness(self, tmp_path):
        """-> a base-class subclass on a tampered snapshot dir."""
        from imio.emailkit.golden import GoldenTemplateTests

        golden = tmp_path / "golden"
        shutil.copytree(self.ADDON.golden_dir, golden)
        addon, suffix = self.ADDON, self.HTML[0]
        snapshot = golden / f"{self.TEMPLATE}.{self.LANGUAGE}.{suffix}"

        def make(mutate):
            mutate(snapshot)

            class Tampered(GoldenTemplateTests):
                package = addon.package
                templates = (self.TEMPLATE,)
                languages = (self.LANGUAGE,)
                fixtures_dir = addon.fixtures_dir
                golden_dir = golden
                layer_fixture = None

            return Tampered(), snapshot

        return make

    def test_the_gate_goes_red_when_a_snapshot_drifts(self, integration, harness):
        """The first regression: a Tailwind class silently purged."""
        instance, snapshot = harness(
            lambda path: path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "padding: 24px", "padding: 4px"
                ),
                encoding="utf-8",
            )
        )

        with pytest.raises(AssertionError) as exc_info:
            instance.test_matches_golden(self.TEMPLATE, self.LANGUAGE, self.HTML)

        message = str(exc_info.value)
        assert snapshot.name in message
        assert "differs from the committed snapshot" in message
        assert "EMAILKIT_UPDATE_GOLDEN" in message, (
            "the failure does not say how to regenerate deliberately, so the next "
            "person guesses"
        )
        assert "padding: 4px" in message, "the diff does not show the change"

    def test_the_gate_goes_red_when_a_placeholder_stops_resolving(
        self, integration, harness
    ):
        """A ``${}`` that stopped resolving, simulated on the snapshot since
        a real render cannot be broken from a test."""
        instance, _snapshot = harness(
            lambda path: path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Convocation au conseil communal", "${title}"
                ),
                encoding="utf-8",
            )
        )

        with pytest.raises(AssertionError) as exc_info:
            instance.test_matches_golden(self.TEMPLATE, self.LANGUAGE, self.HTML)

        assert "differs from the committed snapshot" in str(exc_info.value)

    def test_a_snapshot_taken_while_the_engine_was_broken_is_rejected(
        self, integration, harness
    ):
        """A broken engine writes a raw placeholder into the snapshot; a
        plain comparison would then pass forever."""
        instance, snapshot = harness(
            lambda path: path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Convocation au conseil communal", "${title}"
                ),
                encoding="utf-8",
            )
        )

        with pytest.raises(AssertionError) as exc_info:
            instance.test_golden_has_no_unresolved_placeholder(
                self.TEMPLATE, self.LANGUAGE, self.HTML
            )

        message = str(exc_info.value)
        assert "unsubstituted Chameleon placeholder" in message
        assert snapshot.name in message

    def test_the_gate_goes_red_when_a_fixture_disappears(self, tmp_path):
        """The contract: "each template ships a fixture and a snapshot"."""
        from imio.emailkit.golden import GoldenTemplateTests

        class NoFixture(GoldenTemplateTests):
            package = dummyaddons.COMPLETE.package
            templates = ("convocation",)
            fixtures_dir = tmp_path / "fixtures"
            golden_dir = dummyaddons.COMPLETE.golden_dir
            layer_fixture = None

        with pytest.raises(AssertionError) as exc_info:
            NoFixture().test_every_template_has_a_fixture("convocation")

        assert "no fixture at" in str(exc_info.value)

    def test_a_missing_snapshot_skips_rather_than_fails(self, integration, tmp_path):
        """No snapshot means nothing to compare against, so this skips
        instead of failing."""
        from imio.emailkit.golden import GoldenTemplateTests

        class NoSnapshot(GoldenTemplateTests):
            package = dummyaddons.COMPLETE.package
            templates = ("convocation",)
            fixtures_dir = dummyaddons.COMPLETE.fixtures_dir
            golden_dir = tmp_path / "empty"
            layer_fixture = None

        # pytest.skip.Exception derives from BaseException, not Exception.
        with pytest.raises(pytest.skip.Exception) as exc_info:
            NoSnapshot().test_matches_golden("convocation", "fr", self.HTML)

        message = str(exc_info.value)
        assert "no golden file at" in message
        assert "EMAILKIT_UPDATE_GOLDEN" in message, (
            "the skip does not say how to create the snapshot"
        )


class TestTheBaseClassIsShipped:
    """The shared test base class must be importable from the egg, from
    ``imio.emailkit.golden``."""

    def test_it_imports_from_the_distribution(self):
        from imio.emailkit.golden import GoldenTemplateTests

        import imio.emailkit

        assert Path(GoldenTemplateTests.__module__.replace(".", "/")).name == "golden"
        assert (Path(imio.emailkit.__file__).parent / "golden.py").is_file(), (
            "imio.emailkit.golden is not a file inside the package"
        )

    def test_the_packaging_ships_it(self):
        """A ``.py`` module in a found package needs no ``package-data``
        entry, unlike a template or a data directory."""
        import imio.emailkit.golden

        module = Path(imio.emailkit.golden.__file__)

        assert module.suffix == ".py"
        assert module.parent.name == "emailkit"

    def test_this_packages_own_harness_is_a_subclass_and_not_a_copy(self):
        """``tests/golden_harness.py`` must stay a binding, not a fork, or
        this package stops exercising the code consumers get."""
        from imio.emailkit.golden import GoldenTemplateTests as Shipped

        import golden_harness

        assert issubclass(golden_harness.GoldenTemplateTests, Shipped)
        for name in (
            "test_matches_golden",
            "test_golden_has_no_unresolved_placeholder",
        ):
            assert getattr(golden_harness.GoldenTemplateTests, name) is getattr(
                Shipped, name
            ), f"tests/golden_harness.py overrides {name}; that is a fork"

    def test_the_shipped_layers_do_not_need_pytest(self):
        """A pytest import here would make ``imio.emailkit.testing``
        unimportable for consumers still on ``zope.testrunner``."""
        import ast
        import imio.emailkit.testing

        tree = ast.parse(
            Path(imio.emailkit.testing.__file__).read_text(encoding="utf-8")
        )
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }

        assert "pytest" not in imported, (
            "imio.emailkit.testing imports pytest, so a consumer on "
            "zope.testrunner can no longer use the shipped layers"
        )
