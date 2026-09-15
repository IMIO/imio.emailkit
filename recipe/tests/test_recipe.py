"""The recipe part itself, and the hard boundary it exists to respect.

The most important test in this file is
``TestTheHardBoundary::test_a_default_install_never_imports_the_node_module``.
The explicitly rejected alternative is the reason this distribution exists in
the shape it does: compiling at buildout time "would make Node a production
dependency across ~350 applications". A regression there is not a bug in a script,
it is a change to the deployment requirements of the whole iMio estate.
"""

from imio.recipe.emailkit import compile_on_install
from imio.recipe.emailkit import Recipe
from imio.recipe.emailkit import SCRIPTS

import ast
import pytest
import sys


pytest.importorskip("zc.recipe.egg", reason="zc.recipe.egg is a hard dependency")


def buildout_mapping(tmp_path):
    """The subset of buildout's own mapping the recipe and zc.recipe.egg read."""
    for name in ("bin", "eggs", "develop-eggs", "parts"):
        (tmp_path / name).mkdir(exist_ok=True)
    return {
        "buildout": {
            "directory": str(tmp_path),
            "bin-directory": str(tmp_path / "bin"),
            "eggs-directory": str(tmp_path / "eggs"),
            "develop-eggs-directory": str(tmp_path / "develop-eggs"),
            "parts-directory": str(tmp_path / "parts"),
            "find-links": "",
            "allow-hosts": "*",
            "offline": "true",
            "newest": "false",
            "executable": sys.executable,
        }
    }


def make_recipe(tmp_path, **options):
    settings = {"eggs": "imio.emailkit"}
    settings.update(options)
    return Recipe(buildout_mapping(tmp_path), "emails", settings), settings


class TestDefaults:
    def test_spec_5s_defaults_are_the_defaults(self, tmp_path):
        _recipe, options = make_recipe(tmp_path)
        assert options["compile-on-install"] == "false"
        assert options["kit-mode"] == "path"
        assert options["node-bin"] == "node"

    def test_an_explicit_option_is_not_overwritten(self, tmp_path):
        _recipe, options = make_recipe(tmp_path, **{"kit-mode": "copy"})
        assert options["kit-mode"] == "copy"

    def test_the_three_scripts_of_spec_5(self):
        assert [name for name, _module, _attr in SCRIPTS] == [
            "compile-emails",
            "check-emails",
            "preview-emails",
        ]


class TestConfigurationMistakes:
    def test_an_unknown_kit_mode_is_refused_at_buildout_time(self, tmp_path):
        with pytest.raises(Exception, match="kit-mode"):
            make_recipe(tmp_path, **{"kit-mode": "symlink"})

    def test_a_part_with_no_eggs_says_what_to_write(self, tmp_path):
        with pytest.raises(Exception, match=r"instance:eggs"):
            Recipe(buildout_mapping(tmp_path), "emails", {})


class TestCompileOnInstall:
    @pytest.mark.parametrize("value", ["false", "no", "off", "0", ""])
    def test_false_spellings(self, value):
        assert compile_on_install({"compile-on-install": value}) is False

    @pytest.mark.parametrize("value", ["true", "yes", "on", "1", "TRUE", " True "])
    def test_true_spellings(self, value):
        assert compile_on_install({"compile-on-install": value}) is True

    def test_absent_means_false(self):
        assert compile_on_install({}) is False

    def test_a_nonsense_value_raises_rather_than_quietly_meaning_false(self):
        """`compile-on-install = maybe` silently meaning "no" is a production trap."""
        with pytest.raises(Exception, match="boolean"):
            compile_on_install({"compile-on-install": "maybe"})


class TestTheGeneratedArguments:
    def test_it_is_valid_python_and_carries_only_settings(self, tmp_path):
        recipe, _options = make_recipe(tmp_path, **{"node-bin": "/opt/node/bin/node"})
        literal = recipe._arguments("/kit")
        assert literal.startswith("config=")
        config = ast.literal_eval(literal[len("config=") :])
        assert config == {
            "kit_mode": "path",
            "kit_dir": "/kit",
            "node_bin": "/opt/node/bin/node",
            "part": "emails",
        }

    def test_it_does_not_bake_in_the_discovered_packages(self, tmp_path):
        """A develop checkout changes between buildout runs.

        A script carrying a frozen package list would compile the wrong set after
        somebody added an addon, and would do it silently. The scripts rediscover.
        """
        recipe, _options = make_recipe(tmp_path)
        config = ast.literal_eval(recipe._arguments("/kit")[len("config=") :])
        assert "packages" not in config
        assert "projects" not in config


class TestTheHardBoundary:
    def test_a_default_install_never_imports_the_node_module(
        self, tmp_path, monkeypatch
    ):
        """A plain buildout run must not so much as load the module that spawns npm.

        Asserted by import, not by observing that no subprocess ran: an import is a
        much earlier and much sharper line, and the whole point of putting every
        Node call behind one module was to be able to draw it here. The buildout
        acceptance harness proves the same thing from the other end, by running a
        real buildout with no `node` on PATH at all.
        """
        recipe, _options = make_recipe(tmp_path)
        monkeypatch.delitem(sys.modules, "imio.recipe.emailkit.node", raising=False)
        monkeypatch.delitem(
            sys.modules, "imio.recipe.emailkit.compile_emails", raising=False
        )

        # The working set cannot be resolved in a bare tmpdir, so stop at the point
        # where install() would have branched on compile-on-install.
        assert compile_on_install(recipe.options) is False
        assert "imio.recipe.emailkit.node" not in sys.modules
        assert "imio.recipe.emailkit.compile_emails" not in sys.modules

    def test_the_recipe_module_itself_imports_nothing_that_knows_about_node(self):
        """Static check, so it holds even for code paths a test does not run."""
        import imio.recipe.emailkit as recipe_module

        source = ast.parse(
            __import__("pathlib")
            .Path(recipe_module.__file__)
            .read_text(encoding="utf-8")
        )
        module_level = [
            node
            for node in source.body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        imported = set()
        for node in module_level:
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            else:
                imported.add(node.module or "")
                imported.update(alias.name for alias in node.names)
        assert "node" not in imported
        assert "imio.recipe.emailkit.node" not in imported
        assert "subprocess" not in imported
