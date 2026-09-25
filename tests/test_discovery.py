"""The template registry: one write path, snapshot/restore for tests.

The registry is populated by the ``emailkit:templates`` ZCML directive (see
``test_zcml_directive.py``); these tests cover the registry surface itself.
"""

from imio.emailkit import discovery
from imio.emailkit.interfaces import TemplateNotFound
from pathlib import Path

import pytest


#: Never opened. The registry stores resolved paths, so tests only need
#: paths that are distinguishable from each other.
FAKE_ROOT = Path("/nowhere")


def make_template(name="pkg.a:welcome", **kw):
    package, _, basename = name.partition(":")
    defaults = {
        "name": name,
        "package": package,
        "basename": basename,
        "html_path": FAKE_ROOT / f"{basename}.pt",
        "text_path": None,
    }
    defaults.update(kw)
    return discovery.Template(**defaults)


@pytest.fixture(autouse=True)
def clean_registry():
    with discovery.overlay():
        discovery.reset()
        yield


def test_register_then_get():
    template = make_template()
    discovery.register_template(template)
    assert discovery.get_template("pkg.a:welcome") is template


def test_register_overwrites_silently():
    # Test layers re-execute the same ZCML; the second write must not fail.
    discovery.register_template(make_template())
    replacement = make_template()
    discovery.register_template(replacement)
    assert discovery.get_template("pkg.a:welcome") is replacement


def test_unknown_name_raises_with_available():
    discovery.register_template(make_template())
    with pytest.raises(TemplateNotFound) as excinfo:
        discovery.get_template("pkg.a:nope")
    assert "pkg.a:welcome" in str(excinfo.value)


def test_available_templates_sorted():
    discovery.register_template(make_template("pkg.b:zulu"))
    discovery.register_template(make_template("pkg.a:alpha"))
    assert discovery.available_templates() == ["pkg.a:alpha", "pkg.b:zulu"]


def test_overlay_restores_registry():
    discovery.register_template(make_template("pkg.a:outside"))
    with discovery.overlay():
        discovery.register_template(make_template("pkg.a:inside"))
        assert "pkg.a:inside" in discovery.available_templates()
    assert discovery.available_templates() == ["pkg.a:outside"]


def test_overlay_restores_registry_on_exception():
    discovery.register_template(make_template("pkg.a:outside"))
    with pytest.raises(ValueError), discovery.overlay():
        discovery.register_template(make_template("pkg.a:inside"))
        raise ValueError("boom")
    assert discovery.available_templates() == ["pkg.a:outside"]


def test_forget_package_removes_its_templates_and_directory():
    discovery.register_template(make_template("pkg.a:one"))
    discovery.register_template(make_template("pkg.b:two"))
    discovery.register_directory("pkg.a", FAKE_ROOT / "a" / "templates")
    discovery.forget_package("pkg.a")
    assert discovery.available_templates() == ["pkg.b:two"]
    assert "pkg.a" not in discovery.registered_directories()


def test_forget_unknown_package_is_a_no_op():
    discovery.register_template(make_template("pkg.a:one"))
    discovery.forget_package("pkg.b")
    assert discovery.available_templates() == ["pkg.a:one"]


def test_load_template_missing_html_returns_none(tmp_path, caplog):
    (tmp_path / "templates").mkdir()
    result = discovery.load_template(
        "pkg.a", tmp_path, "templates", "ghost", subject=None, preheader=None
    )
    assert result is None
    assert "ghost" in caplog.text


def test_load_template_missing_twin_warns(tmp_path, caplog):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "welcome.pt").write_text("<html/>")
    template = discovery.load_template(
        "pkg.a", tmp_path, "templates", "welcome", subject="s", preheader=None
    )
    assert template.text_path is None
    assert template.html_path == templates / "welcome.pt"
    assert "plaintext twin" in caplog.text


def test_load_template_complete(tmp_path):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "welcome.pt").write_text("<html/>")
    (templates / "welcome.txt.pt").write_text("text")
    template = discovery.load_template(
        "pkg.a", tmp_path, "templates", "welcome", subject="s", preheader="p"
    )
    assert template.name == "pkg.a:welcome"
    assert template.subject == "s"
    assert template.preheader == "p"
    assert template.text_path == templates / "welcome.txt.pt"
