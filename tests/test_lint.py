"""The authoring lint.

Each rule has a fixture that violates it and one that expresses the same
intent correctly (``fixtures/lint/violating|clean/<rule>.vue``): a rule
that fires on correct markup gets disabled. The lint is pure text
processing, with no Plone or Node dependency.
"""

from imio.emailkit import lint
from pathlib import Path

import pytest
import subprocess
import sys


HERE = Path(__file__).parent
REPO = HERE.parent
FIXTURES = HERE / "fixtures" / "lint"
VIOLATING = FIXTURES / "violating"
CLEAN = FIXTURES / "clean"

# The `.vue` sources this repository ships: its own templates and the kit.
# `bin/check-emails` lints exactly these.
OWN_SOURCES = (
    REPO / "emails" / "src" / "templates",
    REPO / "src" / "imio" / "emailkit" / "kit",
)

# Every rule id, paired with its fixture basename. Listed here, not derived
# from `lint.RULES`, so a rule added without a fixture fails immediately.
RULE_FIXTURES = {
    "tal-on-component": "tal_on_component",
    "runtime-class": "runtime_class",
    "style-placeholder": "style_placeholder",
    "class-placeholder": "class_placeholder",
    "missing-alt": "missing_alt",
    "comment-double-dash": "comment_double_dash",
    "raw-in-comment": "raw_in_comment",
    "path-call": "path_call",
}

# Violations allowed in this repository's own sources, by (path, line, rule
# id). Keep this empty: an entry here is a visible, deliberate exception. A
# growing set means the lint is being worked around instead of the source
# being fixed.
KNOWN = set()


def own_violations():
    """Every violation in this repository's own ``.vue`` sources, repo-relative."""
    files, missing = lint.collect([str(path) for path in OWN_SOURCES])
    assert not missing, f"the repo moved its email sources: {missing}"
    assert files, "no .vue sources found -- a silent pass is worse than no gate"
    return {
        (str(Path(v.path).relative_to(REPO)), v.line, v.rule.rule_id)
        for path in files
        for v in lint.check_file(path)
    }


def ids_in(path):
    return [v.rule.rule_id for v in lint.check_file(path)]


# ---------------------------------------------------------------------------
# One violating fixture per rule, each caught
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("rule_id", "basename"), sorted(RULE_FIXTURES.items()))
def test_the_violating_fixture_trips_its_rule(rule_id, basename):
    """The fixture must trip its own rule, and only that rule."""
    found = ids_in(VIOLATING / f"{basename}.vue")
    assert found, f"{basename}.vue tripped nothing"
    assert set(found) == {rule_id}, (
        f"{basename}.vue should exercise only {rule_id}, got {sorted(set(found))}"
    )


@pytest.mark.parametrize(("rule_id", "basename"), sorted(RULE_FIXTURES.items()))
def test_the_clean_fixture_stays_silent(rule_id, basename):
    """The same intent, written correctly, reports nothing at all."""
    violations = lint.check_file(CLEAN / f"{basename}.vue")
    assert violations == [], "\n".join(str(v) for v in violations)


def test_every_rule_has_a_fixture_pair():
    """Every rule must have both a violating and a clean fixture."""
    assert set(lint.RULES) == set(RULE_FIXTURES)
    for basename in RULE_FIXTURES.values():
        assert (VIOLATING / f"{basename}.vue").is_file()
        assert (CLEAN / f"{basename}.vue").is_file()


def test_violations_carry_a_file_and_a_line():
    """A violation must report a file and a line, not just a rule name."""
    violations = lint.check_file(VIOLATING / "style_placeholder.vue")
    assert len(violations) == 1
    (violation,) = violations
    assert violation.path.endswith("style_placeholder.vue")
    source = (VIOLATING / "style_placeholder.vue").read_text(encoding="utf-8")
    offending = source.splitlines()[violation.line - 1]
    assert "${theme/primary_color}" in offending, (
        "the reported line is not the offending one"
    )


def test_the_report_explains_the_consequence_and_the_escape_hatch():
    """The report must explain the consequence and the fix, not just the
    rule id, since the failure is invisible at build time."""
    (violation,) = lint.check_file(VIOLATING / "style_placeholder.vue")
    text = str(violation)
    assert "style-placeholder" in text
    assert "inlining" in text, "the consequence is not stated"
    assert "tal:attributes" in text, "the fix is not stated"
    assert lint.IGNORE_HINT in text, "the escape hatch is not mentioned"


# ---------------------------------------------------------------------------
# Rules with more in them than a single pattern
# ---------------------------------------------------------------------------


def test_conditional_comments_are_not_double_dash_violations():
    """Outlook conditional comments use hyphen runs and must not trip
    `comment-double-dash`."""
    source = (CLEAN / "comment_double_dash.vue").read_text(encoding="utf-8")
    assert "<!--[if mso]>" in source and "<!--[if !mso]><!-->" in source
    assert lint.check_source(source) == []


def test_a_double_dash_in_a_script_comment_is_not_reported():
    """`<script>` content never reaches the email, so `--` in it is safe."""
    source = "<script setup>\n/** a -- b */\n</script>\n<template><p>x</p></template>\n"
    assert lint.check_source(source) == []


def test_a_build_time_class_binding_is_not_a_runtime_class():
    """`runtime-class` must only catch a name assembled at runtime, not a
    build-time literal Tailwind's scanner already sees."""
    picks = '<template><table :class="toneClass"><tr><td>x</td></tr></table></template>'
    builds = "<template><table :class=\"'bg-' + tone\"><tr><td>x</td></tr></table></template>"
    assert lint.check_source(picks) == []
    assert [v.rule.rule_id for v in lint.check_source(builds)] == ["runtime-class"]


def test_the_sanctioned_theme_token_form_is_not_a_style_placeholder():
    """`tal:attributes="style string:..."` is the correct form for a theme
    token, not a violation."""
    good = (
        '<template><td tal:attributes="style string:background-color: '
        '${theme/primary_color}">x</td></template>'
    )
    bad = '<template><td style="background-color: ${theme/primary_color}">x</td></template>'
    assert lint.check_source(good) == []
    assert [v.rule.rule_id for v in lint.check_source(bad)] == ["style-placeholder"]


def test_bgcolor_may_carry_a_placeholder():
    """`bgcolor` is never parsed as CSS, so a placeholder in it is safe."""
    assert (
        lint.check_source('<template><td bgcolor="${primary_color}">x</td></template>')
        == []
    )


def test_a_javascript_template_literal_is_not_a_tal_path_call():
    """`${config.x}` in `<script>` is a JavaScript template literal, not a
    Chameleon path call."""
    source = (
        "<script setup>\nconst css = `@import \"${resolve('kit.css')}\";`\n</script>\n"
        "<template><p>x</p></template>\n"
    )
    assert lint.check_source(source) == []


def test_a_vue_bound_attribute_is_not_scanned_for_tal_calls():
    """A Vue expression is evaluated at build time; a call in one is legal."""
    source = '<template><a :href="`${base()}/x`">y</a></template>'
    assert [v.rule.rule_id for v in lint.check_source(source)] == []


def test_a_component_name_mentioned_in_an_attribute_value_is_not_an_attribute():
    """Names are scanned with quoted values blanked, so prose cannot fake one."""
    source = (
        '<template><KitPanel title="see the tal:content docs">x</KitPanel></template>'
    )
    assert lint.check_source(source) == []


def test_an_empty_alt_is_a_deliberate_alt():
    """`alt=""` is the correct spelling for a decorative image, not a missing alt."""
    assert lint.check_source('<template><Img src="a" alt="" /></template>') == []
    assert [
        v.rule.rule_id
        for v in lint.check_source('<template><Img src="a" /></template>')
    ] == ["missing-alt"]


# ---------------------------------------------------------------------------
# The escape hatch
# ---------------------------------------------------------------------------


def test_the_opt_out_fixture_reports_nothing():
    """Four marker placements, four suppressed violations."""
    violations = lint.check_file(FIXTURES / "ignored" / "opt_out.vue")
    assert violations == [], "\n".join(str(v) for v in violations)


def test_the_opt_out_is_per_rule_not_a_blanket():
    """Waiving one rule must not waive the one next to it."""
    source = (
        "<template>\n"
        '  <p class="m-0 ${a}" style="color: ${b}">x</p>'
        "<!-- emailkit-lint: ignore=class-placeholder -->\n"
        "</template>\n"
    )
    assert [v.rule.rule_id for v in lint.check_source(source)] == ["style-placeholder"]


def test_the_opt_out_reaches_into_a_multi_line_tag():
    """An HTML comment cannot go inside a tag, so it counts from above the tag."""
    source = (
        "<template>\n"
        "  <!-- emailkit-lint: ignore=tal-on-component -->\n"
        "  <KitPanel\n"
        '    tal:condition="warning"\n'
        "  >x</KitPanel>\n"
        "</template>\n"
    )
    assert lint.check_source(source) == []


def test_ignore_all_waives_every_rule_on_the_line():
    source = (
        "<template>\n"
        '  <p class="${a}" style="color: ${b}">${f(x)}</p>'
        "<!-- emailkit-lint: ignore=all -->\n"
        "</template>\n"
    )
    assert lint.check_source(source) == []


def test_an_unrelated_marker_does_not_suppress():
    """A typo in the rule id must not silently disable the check."""
    source = (
        "<template>\n"
        '  <p style="color: ${b}">x</p><!-- emailkit-lint: ignore=styleplaceholder -->\n'
        "</template>\n"
    )
    assert [v.rule.rule_id for v in lint.check_source(source)] == ["style-placeholder"]


# ---------------------------------------------------------------------------
# This repository's own sources -- the lint has to be usable on real files
# ---------------------------------------------------------------------------


def test_no_unknown_violations_in_the_repos_own_sources():
    """The repo's own `.vue` files must report nothing outside `KNOWN`."""
    unexpected = own_violations() - KNOWN
    assert unexpected == set(), (
        "unexpected violations in this repository's own email sources: "
        f"{sorted(unexpected)}"
    )


def test_the_repos_own_sources_are_fully_clean():
    """The repo's own sources must have no violations at all."""
    assert own_violations() == set()


def test_the_known_ledger_is_not_stale():
    """Every entry in `KNOWN` must still be a real finding."""
    found = own_violations()
    assert found >= KNOWN or not KNOWN, (
        f"KNOWN lists violations that no longer occur: {sorted(KNOWN - found)}"
    )


# ---------------------------------------------------------------------------
# The command line -- what the Makefile and `bin/check-emails` actually call
# ---------------------------------------------------------------------------


def test_exit_code_is_zero_when_clean(capsys):
    assert lint.main([str(CLEAN)]) == 0
    assert "no violations" in capsys.readouterr().out


def test_exit_code_is_one_when_something_fired(capsys):
    assert lint.main([str(VIOLATING)]) == 1
    out = capsys.readouterr().out
    assert "style-placeholder" in out
    assert lint.IGNORE_HINT in out


def test_a_path_that_does_not_exist_is_an_error_not_a_pass(capsys):
    assert lint.main(["nope/nowhere"]) == 2
    assert "no such file" in capsys.readouterr().err


def test_a_directory_with_no_vue_files_is_an_error_not_a_pass(tmp_path, capsys):
    """A gate that passes because it looked at nothing is the worst outcome."""
    assert lint.main([str(tmp_path)]) == 2
    assert "nothing was checked" in capsys.readouterr().err


def test_no_paths_is_a_usage_error():
    with pytest.raises(SystemExit) as raised:
        lint.main([])
    assert raised.value.code == 2


def test_list_rules_explains_every_rule(capsys):
    assert lint.main(["--list-rules"]) == 0
    out = capsys.readouterr().out
    for rule_id in lint.RULES:
        assert rule_id in out


def test_node_modules_is_not_walked():
    """Pointing the lint at `emails/` must not lint Maizzle's own components."""
    files, _ = lint.collect([str(REPO / "emails")])
    assert files, "emails/ has .vue sources"
    assert not [path for path in files if "node_modules" in path.parts]


def test_the_module_entry_point_runs():
    """`python -m imio.emailkit.lint` is what the Makefile and the recipe
    call, so the `__main__` guard must work."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "imio.emailkit.lint", str(VIOLATING / "path_call.vue")],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert result.returncode == 1, result.stderr
    assert "path-call" in result.stdout
