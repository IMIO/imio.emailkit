"""The permissive-machine scan: real ZCML semantics, no booted instance.

Each test scans a fixture package under ``tests/scanfixtures/`` and asserts on
the discovery registry afterwards.
"""

from imio.emailkit import discovery
from imio.emailkit import scan
from pathlib import Path

import os
import pytest
import subprocess
import sys


#: ``tests/scanfixtures`` is a ``sys.path`` root, not a package -- the same
#: pattern ``tests/test_zcml_directive.py`` uses, so the fixture addons are
#: importable by the dotted names their ZCML namespaces itself with.
SCANFIXTURES = Path(__file__).parent / "scanfixtures"
if str(SCANFIXTURES) not in sys.path:
    sys.path.insert(0, str(SCANFIXTURES))


@pytest.fixture(autouse=True)
def clean_registry():
    with discovery.overlay():
        discovery.reset()
        yield


def test_basic_package_registers():
    scan.scan_package("fixture.basic")
    assert "fixture.basic:welcome" in discovery.available_templates()


def test_foreign_directives_swallowed_without_importing_handlers():
    # fixture.foreign declares a browser:page whose class raises on import.
    # An unknown directive must never resolve what it points at.
    scan.scan_package("fixture.foreign")
    assert "fixture.foreign:welcome" in discovery.available_templates()
    assert "fixture.foreign.broken" not in sys.modules


def test_include_graph_followed_and_orphan_invisible():
    scan.scan_package("fixture.includes")
    names = discovery.available_templates()
    assert "fixture.includes:main" in names
    assert "fixture.includes.sub:subbed" in names  # <include package=".sub">
    assert "fixture.includes:orphan" not in names  # orphan.zcml never included


def test_cross_package_include_is_skipped():
    scan.scan_package("fixture.includes")
    assert not [
        n for n in discovery.available_templates() if n.startswith("other_addon:")
    ]


def test_overrides_zcml_wins():
    scan.scan_package("fixture.includes")
    assert discovery.get_template("fixture.includes:overridden").subject == (
        "s_overridden"
    )


def test_file_include_and_conditions():
    scan.scan_package("fixture.conditions")
    names = discovery.available_templates()
    assert "fixture.conditions:filed" in names  # <include file=...>
    assert "fixture.conditions:installed_yes" in names  # installed <real pkg>
    assert "fixture.conditions:installed_no" not in names  # installed <missing>
    # Documented divergence: no feature provider loads at build time, so
    # `have <feature>` reads false.
    assert "fixture.conditions:featured" not in names


def test_scan_registers_same_as_runtime_execution():
    # The scan and a real zope.configuration run share the directive handlers,
    # so the registry contents must be identical for the same package.
    from zope.configuration import xmlconfig
    from zope.configuration.config import ConfigurationMachine

    import fixture.basic

    scan.scan_package("fixture.basic")
    via_scan = discovery.get_templates()
    discovery.reset()
    machine = ConfigurationMachine()
    xmlconfig.registerCommonDirectives(machine)
    xmlconfig.include(machine, file="configure.zcml", package=fixture.basic)
    machine.execute_actions()
    assert discovery.get_templates() == via_scan


def test_scan_runs_without_a_booted_instance():
    # A bare subprocess: instance eggs importable, no Zope app, no site.
    code = (
        f"import sys; sys.path[:0] = {[str(SCANFIXTURES)]!r}; "
        "from imio.emailkit import scan, discovery; "
        "scan.scan_package('fixture.basic'); "
        "assert 'fixture.basic:welcome' in discovery.available_templates()"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)},
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
