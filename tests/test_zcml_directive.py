"""The ``<emailkit:templates>`` directive registers into the discovery registry.

Executed here through plain ``zope.configuration`` -- no Plone, no layers --
which is the same machinery a real instance uses and the same machinery the
build-tool scan drives.
"""

from imio.emailkit import discovery
from pathlib import Path
from zope.configuration import xmlconfig
from zope.configuration.config import ConfigurationConflictError
from zope.configuration.config import ConfigurationMachine

import imio.emailkit
import pytest
import sys


#: ``tests/scanfixtures`` is a ``sys.path`` root, not a package, so the
#: fixture addons import by their own dotted names, like a real consumer
#: egg, and the directive sees a package with a real ``__name__``.
SCANFIXTURES = Path(__file__).parent / "scanfixtures"
if str(SCANFIXTURES) not in sys.path:
    sys.path.insert(0, str(SCANFIXTURES))

import fixture.basic  # noqa: E402


ZCML_TEMPLATE = """\
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="fixture.basic">
  {body}
</configure>
"""


def execute(body, package=fixture.basic):
    """Runs ``body`` as the content of a ZCML file belonging to ``package``.

    Sets ``machine.package``, since the directive reads
    ``context.package`` to derive the template namespace and the base
    the ``directory`` attribute resolves against.
    """
    machine = ConfigurationMachine()
    xmlconfig.registerCommonDirectives(machine)
    xmlconfig.include(machine, file="meta.zcml", package=imio.emailkit)
    machine.package = package
    xmlconfig.string(ZCML_TEMPLATE.format(body=body), context=machine)
    return machine


@pytest.fixture(autouse=True)
def clean_registry():
    with discovery.overlay():
        discovery.reset()
        yield


def test_registers_namespaced_templates():
    execute(
        '<emailkit:templates directory="templates">'
        '  <emailkit:template name="welcome" subject="[s_welcome] Welcome"'
        '                     preheader="[p_welcome] Hi." />'
        "</emailkit:templates>"
    )
    template = discovery.get_template("fixture.basic:welcome")
    assert template.package == "fixture.basic"
    assert template.html_path.name == "welcome.pt"
    assert template.text_path.name == "welcome.txt.pt"


def test_subject_is_a_message_id_in_the_zcml_domain():
    execute(
        "<emailkit:templates>"
        '  <emailkit:template name="welcome" subject="[s_welcome] Welcome" />'
        "</emailkit:templates>"
    )
    subject = discovery.get_template("fixture.basic:welcome").subject
    assert subject == "s_welcome"
    assert subject.domain == "fixture.basic"
    assert subject.default == "Welcome"


def test_directory_defaults_to_templates():
    execute(
        "<emailkit:templates>"
        '  <emailkit:template name="welcome" subject="[s] W" />'
        "</emailkit:templates>"
    )
    assert "fixture.basic:welcome" in discovery.available_templates()
    directories = discovery.registered_directories()
    assert directories["fixture.basic"].name == "templates"


def test_missing_pt_is_skipped_with_warning(caplog):
    execute(
        "<emailkit:templates>"
        '  <emailkit:template name="ghost" subject="[s] G" />'
        "</emailkit:templates>"
    )
    assert "fixture.basic:ghost" not in discovery.available_templates()
    assert "ghost" in caplog.text


def test_missing_twin_registers_with_warning(caplog):
    execute(
        "<emailkit:templates>"
        '  <emailkit:template name="plain" subject="[s] P" />'
        "</emailkit:templates>"
    )
    assert discovery.get_template("fixture.basic:plain").text_path is None
    assert "plaintext twin" in caplog.text


def test_duplicate_name_is_a_configuration_conflict():
    with pytest.raises(ConfigurationConflictError):
        execute(
            "<emailkit:templates>"
            '  <emailkit:template name="welcome" subject="[a] A" />'
            '  <emailkit:template name="welcome" subject="[b] B" />'
            "</emailkit:templates>"
        )


def test_second_templates_block_in_one_package_conflicts():
    with pytest.raises(ConfigurationConflictError):
        execute(
            "<emailkit:templates>"
            '  <emailkit:template name="welcome" subject="[a] A" />'
            "</emailkit:templates>"
            "<emailkit:templates>"
            '  <emailkit:template name="plain" subject="[b] B" />'
            "</emailkit:templates>"
        )


def test_absolute_directory_is_refused():
    from zope.configuration.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError):
        execute(
            '<emailkit:templates directory="/etc">'
            '  <emailkit:template name="welcome" subject="[a] A" />'
            "</emailkit:templates>"
        )


def test_executing_the_fixture_configure_zcml_end_to_end():
    machine = ConfigurationMachine()
    xmlconfig.registerCommonDirectives(machine)
    xmlconfig.include(machine, file="configure.zcml", package=fixture.basic)
    machine.execute_actions()
    assert "fixture.basic:welcome" in discovery.available_templates()
    assert "fixture.basic:plain" in discovery.available_templates()
