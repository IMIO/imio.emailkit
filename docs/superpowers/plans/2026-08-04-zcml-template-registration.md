# ZCML Template Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `imio.emailkit.templates` entry-point + dict registration with an `<emailkit:templates>` ZCML directive, and give the build tooling a permissive-`ConfigurationMachine` scan instead of entry-point metadata.

**Architecture:** A `meta:complexDirective` in `imio.emailkit` registers templates into a module-level registry in `discovery.py` through configuration actions (conflict detection + overrides for free). Build tooling (`imio.recipe.emailkit` and the generated `bin/` scripts) executes consumer ZCML through a `ConfigurationMachine` subclass that no-ops unknown directives, so registration has exactly one parser and one code path. Clean cut: the entry point is deleted everywhere, including the two dummy test add-ons.

**Tech Stack:** zope.configuration (verified against the installed 3.12 copy), zope.schema, pytest, zc.buildout recipe. Spec: `docs/superpowers/specs/2026-08-04-zcml-template-registration-design.md`.

**Conventions that bind every task:**
- New/edited code comments must NOT cite SPEC §-numbers or phase numbers — state the reasoning itself (repo rule).
- Comment density/tone: match the existing files (they are heavily documented; keep that).
- Run tests with `bin/pytest` from the repo root (`make test` runs the same). Recipe tests: `cd recipe && ../bin/pytest tests/` (check `recipe/pyproject.toml` for its own runner if that fails — recipe has its own test env in CI).
- Commit after each task with a conventional-commit message ending in the Claude trailer.

**Verified upstream facts the code below relies on (do not re-derive):**
- `ConfigurationAdapterRegistry.factory(context, name)` raises `ConfigurationError("Unknown directive", ns, n)` for unregistered directives; every nested lookup funnels through the machine's `factory` (config.py:666-679, RootStackItem.contained config.py:936-946).
- A directive factory is called `factory(context, data, info)` and must return an `IStackItem`-shaped object: `.contained(name, data, info)` + `.finish()`.
- `meta:complexDirective` handler protocol: `Handler(context, **schema_kwargs)` at open, one method per subdirective called as `method(context, **subschema_kwargs)`, `__call__(self)` at close (config.py:1139+).
- `MessageID.fromUnicode` supports `"[msgid] Default text"`: msgid `msgid`, default `Default text`, domain from the enclosing `i18n_domain` (fields.py:549-567). So the existing `.po` msgids (`email_subject_notification` etc.) stay valid.
- `xmlconfig.include(machine, file=..., package=...)` / `xmlconfig.includeOverrides(...)` can be called directly with the machine as context — that is exactly what `site.zcml` processing does, and the configure-then-includeOverrides shape is the stock Zope overrides mechanism.
- `include` dedupes via `context.processFile(path)` — including `meta.zcml` twice in one machine is a no-op.
- `defineSimpleDirective(machine, "include", IInclude, handler, namespace="*")` re-registers (overwrites) the common `include` directive.
- `i18ndude rebuild-pot` (used by `python -m imio.emailkit.locales`) extracts from `.py` and `.pt` only, never ZCML → msgids moving to ZCML need a Python extraction shim (`msgids.py`).

---

### Task 1: Registry core — rewrite `discovery.py`

The entry-point scan/cache becomes a plain module-level registry with a single write path. Public read API (`get_template`, `get_templates`, `available_templates`, `Template`, `HTML_SUFFIX`, `TEXT_SUFFIX`) keeps its names so `render.py`, `vocabularies/`, `browser/preview.py`, `golden.py` need no import changes.

**Files:**
- Rewrite: `src/imio/emailkit/discovery.py`
- Rewrite: `tests/test_discovery.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/test_discovery.py` wholesale. These tests need no Plone layer — plain pytest:

```python
"""The template registry: one write path, snapshot/restore for tests.

The registry is populated by the ``emailkit:templates`` ZCML directive (see
``test_zcml_directive.py``); these tests cover the registry surface itself.
"""

from imio.emailkit import discovery
from imio.emailkit.interfaces import TemplateNotFound
from pathlib import Path

import pytest


def make_template(name="pkg.a:welcome", **kw):
    package, _, basename = name.partition(":")
    defaults = dict(
        name=name,
        package=package,
        basename=basename,
        html_path=Path(f"/tmp/{basename}.pt"),
        text_path=None,
    )
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


def test_forget_package_removes_its_templates_and_directory():
    discovery.register_template(make_template("pkg.a:one"))
    discovery.register_template(make_template("pkg.b:two"))
    discovery.register_directory("pkg.a", Path("/tmp/a/templates"))
    discovery.forget_package("pkg.a")
    assert discovery.available_templates() == ["pkg.b:two"]
    assert "pkg.a" not in discovery.registered_directories()


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
```

- [ ] **Step 2: Run to verify failure**

Run: `bin/pytest tests/test_discovery.py -x -q`
Expected: FAIL — `discovery` has no `overlay`/`reset`/`register_template`.

- [ ] **Step 3: Rewrite `src/imio/emailkit/discovery.py`**

Keep the `Template` dataclass and the suffix constants verbatim; replace everything else:

```python
"""The registry of email templates the ``emailkit:templates`` directive fills.

A consumer addon declares its templates in ZCML (see ``meta.zcml`` and
``zcml.py``); each ``<emailkit:template>`` becomes a configuration action whose
callable resolves the ``.pt`` / ``.txt.pt`` files on disk and writes one
:class:`Template` here. Lookup stays namespaced: ``"<package>:<basename>"``.

There is no scan and no cache: ZCML execution *is* the startup scan, so the
"missing plaintext twin" warning lands in the startup log by construction, and
duplicate registrations are a ``ConfigurationConflictError`` instead of a
silent overwrite. Re-executing the same ZCML (test layers stack it) simply
rewrites the same values, which is why :func:`register_template` overwrites
without complaint -- within one configuration run the action discriminator
already guarantees uniqueness.

:func:`overlay` is the test seam: it snapshots the registry so a block can
register throwaway addons (the dummies) and leave no trace.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from imio.emailkit.interfaces import TemplateNotFound
from pathlib import Path

import logging


logger = logging.getLogger("imio.emailkit.discovery")

#: Suffixes of the two compiled artifacts a template ships.
HTML_SUFFIX = ".pt"
TEXT_SUFFIX = ".txt.pt"

#: ``directory`` attribute of ``<emailkit:templates>``, when the addon omits it.
DEFAULT_DIRECTORY = "templates"


@dataclass(frozen=True)
class Template:
    """One registered template, resolved to files on disk."""

    #: Namespaced lookup name, ``"<package>:<basename>"``.
    name: str
    #: The package whose ZCML registered it, i.e. the namespace part of :attr:`name`.
    package: str
    #: The file stem, i.e. the part after the colon in :attr:`name`.
    basename: str
    #: The compiled HTML template. Always present -- a template whose ``.pt``
    #: is missing is not registered at all.
    html_path: Path
    #: The plaintext twin, or ``None`` when the addon ships none; ``render()``
    #: then falls back to naive text extraction and logs a deprecation.
    text_path: Path | None
    #: i18n msgid of the subject, from the registration.
    subject: object = None
    #: Optional i18n msgid of the hidden inbox-preview line.
    preheader: object = None


_templates = {}
#: ``package -> templates directory``; what the build tooling reads to know
#: where compiled output lands, even for a package whose first build has not
#: run yet (its directory holds no ``.pt`` to derive the answer from).
_directories = {}


def register_template(template):
    """The single write path into the registry."""
    _templates[template.name] = template


def register_directory(package, templates_dir):
    """Record where ``package``'s compiled templates live (build-tool query)."""
    _directories[package] = Path(templates_dir)


def registered_directories():
    return dict(_directories)


def get_templates():
    """The full ``name -> Template`` mapping, as a copy."""
    return dict(_templates)


def get_template(name):
    """Return the :class:`Template` registered as ``name``.

    :raises TemplateNotFound: when nothing is registered under that name.
    """
    try:
        return _templates[name]
    except KeyError:
        raise TemplateNotFound(name, available=dict(_templates)) from None


def available_templates():
    """Every registered template name, sorted."""
    return sorted(_templates)


def reset():
    """Empty the registry. For rescans (preview) and test isolation."""
    _templates.clear()
    _directories.clear()


def forget_package(package):
    """Drop one package's templates and directory record."""
    for name in [n for n, t in _templates.items() if t.package == package]:
        del _templates[name]
    _directories.pop(package, None)


@contextmanager
def overlay():
    """Snapshot the registry, restore it on exit. The test seam."""
    saved_templates = dict(_templates)
    saved_directories = dict(_directories)
    try:
        yield
    finally:
        _templates.clear()
        _templates.update(saved_templates)
        _directories.clear()
        _directories.update(saved_directories)


def load_template(package, package_dir, directory, basename, subject, preheader):
    """Resolve one registration to files on disk, or ``None`` plus a warning.

    Called when configuration actions execute -- at instance startup, or at the
    end of a build-tool scan -- so every warning below lands where someone
    deploying can see it, not in the log of whoever sends the first mail.
    """
    directory_path = (Path(package_dir) / directory).resolve()
    html_path = directory_path / f"{basename}{HTML_SUFFIX}"
    if not html_path.is_file():
        logger.warning(
            "%s registers the template %r but %s is missing; skipping it. "
            "The compiled output is committed, so this is a build or "
            "packaging problem, not a runtime one.",
            package,
            basename,
            html_path,
        )
        return None
    text_path = directory_path / f"{basename}{TEXT_SUFFIX}"
    if not text_path.is_file():
        logger.warning(
            "%s:%s ships no %s plaintext twin. render() will fall back to "
            "naive text extraction, which is deprecated -- ship a twin.",
            package,
            basename,
            TEXT_SUFFIX,
        )
        text_path = None
    return Template(
        name=f"{package}:{basename}",
        package=package,
        basename=basename,
        html_path=html_path,
        text_path=text_path,
        subject=subject,
        preheader=preheader,
    )
```

- [ ] **Step 4: Run the new tests**

Run: `bin/pytest tests/test_discovery.py -q`
Expected: PASS. (The wider suite is red until Task 5 — that is expected and tracked there.)

- [ ] **Step 5: Commit**

```bash
git add src/imio/emailkit/discovery.py tests/test_discovery.py
git commit -m "feat: replace the entry-point scan with a plain template registry"
```

---

### Task 2: The `emailkit:templates` directive

**Files:**
- Create: `src/imio/emailkit/zcml.py`
- Create: `src/imio/emailkit/meta.zcml`
- Create: `tests/scanfixtures/__init__.py` (empty), `tests/scanfixtures/fixture/__init__.py` (empty), `tests/scanfixtures/fixture/basic/` (fixture package, below)
- Create: `tests/test_zcml_directive.py`

- [ ] **Step 1: Create the `fixture.basic` package**

`tests/scanfixtures/` is a `sys.path` root holding fixture packages for directive/scan tests (the dummies under `tests/dummies/` stay the full consumer-shaped living documentation; these are minimal single-purpose fixtures). `fixture/__init__.py` and `scanfixtures/__init__.py` are empty files; `scanfixtures/__init__.py` is actually NOT needed (it is a path root, not a package) — create only `tests/scanfixtures/fixture/__init__.py`.

`tests/scanfixtures/fixture/basic/__init__.py`: empty.
`tests/scanfixtures/fixture/basic/templates/welcome.pt`: `<html><body>welcome</body></html>`
`tests/scanfixtures/fixture/basic/templates/welcome.txt.pt`: `welcome`
`tests/scanfixtures/fixture/basic/templates/plain.pt`: `<html><body>plain</body></html>`
(no `plain.txt.pt` — exercises the missing-twin warning)

`tests/scanfixtures/fixture/basic/configure.zcml`:

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="fixture.basic"
    >

  <include package="imio.emailkit" file="meta.zcml" />

  <emailkit:templates directory="templates">
    <emailkit:template
        name="welcome"
        subject="[fixture_subject_welcome] Welcome"
        preheader="[fixture_preheader_welcome] Hello there."
        />
    <emailkit:template
        name="plain"
        subject="[fixture_subject_plain] Plain"
        />
  </emailkit:templates>

</configure>
```

`tests/scanfixtures/conftest.py`:

```python
"""Make the fixture packages importable for this directory's tests."""

from pathlib import Path

import sys


HERE = str(Path(__file__).parent)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
```

Note: the *tests* live in `tests/`, not in `tests/scanfixtures/`, so put the `sys.path` insertion in a shared helper instead — add to `tests/test_zcml_directive.py` (and later `tests/test_scan.py`) the import-time block:

```python
SCANFIXTURES = Path(__file__).parent / "scanfixtures"
if str(SCANFIXTURES) not in sys.path:
    sys.path.insert(0, str(SCANFIXTURES))
```

and do NOT create `tests/scanfixtures/conftest.py` or `tests/scanfixtures/__init__.py` after all (pytest must not collect the fixture dirs: add `norecursedirs`-style exclusion only if pytest picks them up — check `pyproject.toml` `[tool.pytest.ini_options]` and extend `testpaths`/`norecursedirs` if needed).

- [ ] **Step 2: Write the failing tests**

`tests/test_zcml_directive.py`:

```python
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


def test_executing_the_fixture_configure_zcml_end_to_end():
    machine = ConfigurationMachine()
    xmlconfig.registerCommonDirectives(machine)
    xmlconfig.include(machine, file="configure.zcml", package=fixture.basic)
    machine.execute_actions()
    assert "fixture.basic:welcome" in discovery.available_templates()
    assert "fixture.basic:plain" in discovery.available_templates()
```

- [ ] **Step 3: Run to verify failure**

Run: `bin/pytest tests/test_zcml_directive.py -x -q`
Expected: FAIL — `meta.zcml` does not exist.

- [ ] **Step 4: Create `src/imio/emailkit/meta.zcml`**

```xml
<configure xmlns:meta="http://namespaces.zope.org/meta">

  <meta:directives namespace="http://namespaces.imio.be/emailkit">

    <meta:complexDirective
        name="templates"
        schema=".zcml.ITemplatesDirective"
        handler=".zcml.TemplatesDirective"
        >
      <meta:subdirective
          name="template"
          schema=".zcml.ITemplateDirective"
          />
    </meta:complexDirective>

  </meta:directives>

</configure>
```

- [ ] **Step 5: Create `src/imio/emailkit/zcml.py`**

```python
"""The ``<emailkit:templates>`` / ``<emailkit:template>`` directives.

Registration is ZCML rather than Python so it inherits the machinery every
other Zope registration has: duplicate names are a ``ConfigurationConflictError``
at startup instead of a silent overwrite, ``overrides.zcml`` can replace a
registration, ``zcml:condition`` gates one, and the msgid domain of ``subject``
/ ``preheader`` comes from the enclosing ``i18n_domain`` instead of a hand-wired
``MessageFactory``.

The handler only *emits actions*; the file checks live in
``discovery.load_template`` and run when actions execute. That keeps the
warnings at startup (action execution time) and lets conflict resolution see
every registration before any of them takes effect.
"""

from imio.emailkit import discovery
from pathlib import Path
from zope.configuration.exceptions import ConfigurationError
from zope.configuration.fields import MessageID
from zope.interface import Interface
from zope.schema import TextLine


class ITemplatesDirective(Interface):
    """``<emailkit:templates>`` -- one block per package."""

    directory = TextLine(
        title="Directory holding the compiled templates",
        description=(
            "Relative to the package the ZCML file belongs to. "
            "Defaults to `templates`."
        ),
        required=False,
    )


class ITemplateDirective(Interface):
    """``<emailkit:template>`` -- one registered template."""

    name = TextLine(
        title="Template basename",
        description="Resolves to `<directory>/<name>.pt` and `<name>.txt.pt`.",
        required=True,
    )

    subject = MessageID(
        title="Subject msgid",
        description=(
            "Translated per recipient language at send time. Use "
            "`[msgid] Default text` to pick the msgid explicitly."
        ),
        required=True,
    )

    preheader = MessageID(
        title="Preheader msgid",
        description=(
            "The hidden inbox-preview line next to the subject. Omitted, the "
            "layout's preview div collapses to nothing."
        ),
        required=False,
    )


class TemplatesDirective:
    """Handler for one ``<emailkit:templates>`` block.

    The namespace of every contained template is the package the ZCML file
    belongs to -- never spelled out by the consumer, so it cannot lie.
    """

    def __init__(self, context, directory=None):
        package = getattr(context, "package", None)
        if package is None:
            raise ConfigurationError(
                "emailkit:templates must be used in a package's ZCML: the "
                "package is the template namespace and the base the directory "
                "resolves against."
            )
        self.context = context
        self.package = package.__name__
        self.package_dir = Path(package.__file__).parent
        self.directory = directory or discovery.DEFAULT_DIRECTORY
        # One directory record per package: a second block with a different
        # directory in the same package conflicts here, which is deliberate --
        # the build tooling needs a single answer to "where does output land".
        context.action(
            discriminator=("emailkit:templates", self.package),
            callable=discovery.register_directory,
            args=(self.package, (self.package_dir / self.directory).resolve()),
        )

    def template(self, context, name, subject, preheader=None):
        full_name = f"{self.package}:{name}"
        context.action(
            discriminator=("emailkit:template", full_name),
            callable=_load_and_register,
            args=(
                self.package,
                self.package_dir,
                self.directory,
                name,
                subject,
                preheader,
            ),
        )

    def __call__(self):
        return ()


def _load_and_register(package, package_dir, directory, basename, subject, preheader):
    template = discovery.load_template(
        package, package_dir, directory, basename, subject, preheader
    )
    if template is not None:
        discovery.register_template(template)
```

- [ ] **Step 6: Run the tests**

Run: `bin/pytest tests/test_zcml_directive.py -q`
Expected: PASS. If `machine.package = package` proves insufficient for `xmlconfig.string` (context attribute lookup), wrap with `GroupingContextDecorator(machine)` carrying `package` — adjust the `execute()` helper, not the directive.

- [ ] **Step 7: Commit**

```bash
git add src/imio/emailkit/zcml.py src/imio/emailkit/meta.zcml tests/test_zcml_directive.py tests/scanfixtures
git commit -m "feat: emailkit:templates ZCML directive feeding the registry"
```

---

### Task 3: Wire `imio.emailkit` itself through the directive

**Files:**
- Modify: `src/imio/emailkit/configure.zcml`
- Modify: `src/imio/emailkit/__init__.py` (delete the `emailkit` dict, lines 17-74)
- Modify: `pyproject.toml` (delete the entry-point block, lines ~52-55)
- Create: `src/imio/emailkit/msgids.py`
- Create: `tests/test_msgids.py`
- Modify: `src/imio/emailkit/vocabularies/__init__.py` (docstring only)

- [ ] **Step 1: Edit `configure.zcml`**

Add the emailkit namespace, include `meta.zcml` first, replace the warm-cache subscriber with the package's own registration block:

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    xmlns:i18n="http://namespaces.zope.org/i18n"
    i18n_domain="imio.emailkit"
    >

  <include file="meta.zcml" />

  <i18n:registerTranslations directory="locales" />

  <include file="dependencies.zcml" />
  <include file="profiles.zcml" />
  <include file="adapters.zcml" />

  <include package=".browser" />

  <!-- The content-rule action, and the discovery-backed vocabulary its
       edit form offers. The vocabulary is included first because the action's
       schema names it. -->
  <include package=".vocabularies" />
  <include package=".contentrules" />

  <!-- imio.emailkit is its own first consumer: its templates register through
       exactly the directive external addons use. Two of the three restyled
       Plone default mails (mail_password_template, registered_notify_template)
       are deliberately NOT here: a stock Plone view renders them, their bodies
       speak that view's dialect, and a registration would resolve to a template
       render() can never render. get_username IS here because this package owns
       that view and renders it through render(). See docs/DECISIONS.md. -->
  <emailkit:templates directory="templates">
    <emailkit:template
        name="notification"
        subject="[email_subject_notification] Notification"
        preheader="[email_preheader_notification] You have a new notification."
        />
    <emailkit:template
        name="get_username"
        subject="[email_subject_get_username] Your username"
        preheader="[email_preheader_get_username] Here is the username you asked for."
        />
  </emailkit:templates>

  <!-- -*- extra stuff goes here -*- -->

</configure>
```

(The `warm_cache` subscriber is gone: directive actions execute when ZCML loads, so the missing-twin warning already lands at startup.)

- [ ] **Step 2: Trim `__init__.py`**

Delete the `emailkit = {...}` dict AND its long lead comment (`src/imio/emailkit/__init__.py:17-74`). The DECISIONS.md-worthy content of that comment moved to `configure.zcml` (condensed) in Step 1; verify `docs/DECISIONS.md` still carries the full mail_password/registered_notify rationale (it does — grep `DECISIONS.md` for `mail_password`; if the only copy was the deleted comment, append it to DECISIONS.md). Keep `_`, `PACKAGE_NAME`, `logger`, `__version__` and the tail imports untouched.

- [ ] **Step 3: Remove the entry point from `pyproject.toml`**

Delete:

```toml
# imio.emailkit is its own first consumer (SPEC §4): it registers its own
# templates through exactly the mechanism external addons use.
[project.entry-points."imio.emailkit.templates"]
"imio.emailkit" = "imio.emailkit:emailkit"
```

Keep `[project.entry-points."z3c.autoinclude.plugin"]` — it is what makes Plone auto-load the package's ZCML (including `meta.zcml`) in production.

- [ ] **Step 4: Create `src/imio/emailkit/msgids.py`**

```python
"""Extraction shim: restate the ZCML msgids where i18ndude can see them.

``python -m imio.emailkit.locales`` rebuilds the ``.pot`` with ``i18ndude
rebuild-pot``, which extracts from Python and page templates but never from
ZCML. The subject/preheader msgids live in ``configure.zcml`` since the
``emailkit:templates`` directive replaced the registration dict, so without
this module a locales rebuild would drop them from the catalog.

``tests/test_msgids.py`` fails when this file and ``configure.zcml`` drift.
"""

from imio.emailkit import _


_("email_subject_notification", default="Notification")
_("email_preheader_notification", default="You have a new notification.")
_("email_subject_get_username", default="Your username")
_("email_preheader_get_username", default="Here is the username you asked for.")
```

- [ ] **Step 5: Create `tests/test_msgids.py`**

```python
"""configure.zcml msgids and the msgids.py extraction shim must not drift."""

from pathlib import Path
from xml.etree import ElementTree

import re


PACKAGE = Path(__file__).parent.parent / "src" / "imio" / "emailkit"
EMAILKIT_NS = "{http://namespaces.imio.be/emailkit}"


def zcml_msgids():
    tree = ElementTree.parse(PACKAGE / "configure.zcml")
    msgids = set()
    for element in tree.iter(f"{EMAILKIT_NS}template"):
        for attribute in ("subject", "preheader"):
            value = element.get(attribute)
            if value and value.startswith("["):
                msgids.add(value[1 : value.index("]")])
    return msgids


def shim_msgids():
    source = (PACKAGE / "msgids.py").read_text()
    return set(re.findall(r'_\(\s*"([^"]+)"', source))


def test_every_zcml_msgid_is_extractable():
    assert zcml_msgids() <= shim_msgids()


def test_shim_carries_no_dead_msgids():
    assert shim_msgids() <= zcml_msgids()
```

- [ ] **Step 6: Update the vocabulary docstring**

In `src/imio/emailkit/vocabularies/__init__.py`, rewrite the module docstring paragraphs that describe "entry-point discovery" and the "Not cached here / invalidate_cache" rationale to describe the ZCML-directive registry instead (the registry has no cache to invalidate; the vocabulary reads it live). Code is untouched.

- [ ] **Step 7: Run the affected suites**

Run: `bin/pytest tests/test_msgids.py tests/test_zcml_directive.py tests/test_discovery.py tests/test_render.py tests/test_subject.py tests/test_i18n.py -q`
Expected: PASS — the Plone layers load `configure.zcml`, which now registers `imio.emailkit:notification` / `imio.emailkit:get_username` through the directive. Suites that use the dummies are still red until Task 5.

- [ ] **Step 8: Commit**

```bash
git add -A src/imio/emailkit pyproject.toml tests/test_msgids.py
git commit -m "feat: register imio.emailkit's own templates through the directive"
```

---

### Task 4: The build-tool scan — `scan.py` and the permissive machine

**Files:**
- Create: `src/imio/emailkit/scan.py`
- Create: fixture packages `tests/scanfixtures/fixture/foreign/`, `fixture/includes/`, `fixture/conditions/`, and `tests/scanfixtures/other/`
- Create: `tests/test_scan.py`

- [ ] **Step 1: Create the fixture packages**

`fixture/foreign/` — proves unknown directives are swallowed *without importing their handlers or classes*:
- `__init__.py`: empty
- `broken.py`: `raise ImportError("scan must never import what foreign directives point at")`
- `templates/welcome.pt`: `<html/>`, `templates/welcome.txt.pt`: `w`
- `configure.zcml`:

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:browser="http://namespaces.zope.org/browser"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="fixture.foreign"
    >
  <include package="imio.emailkit" file="meta.zcml" />
  <browser:page
      name="boom"
      for="*"
      class="fixture.foreign.broken.Boom"
      permission="zope.Public"
      />
  <emailkit:templates>
    <emailkit:template name="welcome" subject="[s] W" />
  </emailkit:templates>
</configure>
```

`fixture/includes/` — the include graph:
- `__init__.py`, `sub/__init__.py`: empty
- `templates/main.pt`, `templates/filed.pt`, `templates/subbed.pt`, `templates/orphan.pt`, `templates/overridden.pt` (+ `.txt.pt` twins for each): trivial one-line files
- `configure.zcml`:

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="fixture.includes"
    >
  <include package="imio.emailkit" file="meta.zcml" />
  <include file="emails.zcml" />
  <include package=".sub" />
  <include package="other.addon" />
  <emailkit:templates>
    <emailkit:template name="main" subject="[s_main] Main" />
    <emailkit:template name="overridden" subject="[s_original] Original" />
  </emailkit:templates>
</configure>
```

- `emails.zcml` (included by file): registers `filed` inside its own `<emailkit:templates>` block — **NOTE**: a second `emailkit:templates` block in the same package conflicts on the directory discriminator. So `emails.zcml` must NOT redeclare a block; instead give `fixture/includes` its templates in ONE block and make `emails.zcml` exercise something else. Correction — structure it this way instead:
  - `configure.zcml` holds the single `<emailkit:templates>` block with `main` and `overridden`, plus the three `<include>` lines.
  - `emails.zcml` registers **nothing emailkit** — delete it from the fixture; the file-include edge is exercised in `fixture/conditions` (below) where the included file holds the package's only block.
  - `sub/configure.zcml` holds `.sub`'s own block (different package → different discriminator, no conflict):

```xml
<configure
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="fixture.includes"
    >
  <emailkit:templates directory="../templates">
    <emailkit:template name="subbed" subject="[s_subbed] Subbed" />
  </emailkit:templates>
</configure>
```

  (namespace is `fixture.includes.sub`; `directory="../templates"` points at the parent's files — also exercises a non-default directory.)
- `orphan.zcml` (never included from any root — must stay invisible):

```xml
<configure xmlns:emailkit="http://namespaces.imio.be/emailkit" i18n_domain="fixture.includes">
  <emailkit:templates>
    <emailkit:template name="orphan" subject="[s_orphan] Orphan" />
  </emailkit:templates>
</configure>
```

- `overrides.zcml` (root two — must win the conflict on `overridden`):

```xml
<configure xmlns:emailkit="http://namespaces.imio.be/emailkit" i18n_domain="fixture.includes">
  <emailkit:templates>
    <emailkit:template name="overridden" subject="[s_overridden] Overridden" />
  </emailkit:templates>
</configure>
```

  **Conflict caveat:** `overrides.zcml` redeclares the `emailkit:templates` block → directory-record discriminator `("emailkit:templates", "fixture.includes")` appears in both configure and overrides — `includeOverrides` resolves that in overrides' favor, same as the template override. Both records carry the same directory value, so semantics are unchanged either way.

`tests/scanfixtures/other/addon/` — the cross-package include target (path root `tests/scanfixtures/other`? No — one path root only: put it at `tests/scanfixtures/other/`... **keep it simple**: `tests/scanfixtures/other_addon/` with `__init__.py`, `configure.zcml` registering template `foreign_side` plus `templates/foreign_side.pt`. Then `fixture/includes/configure.zcml` says `<include package="other_addon" />`. The scan must skip it (not in `fixture.includes` namespace); the test asserts `other_addon:foreign_side` was NOT registered by scanning `fixture.includes`.

`fixture/conditions/`:
- `__init__.py`; `templates/` with `always.pt`, `installed_yes.pt`, `installed_no.pt`, `featured.pt`, `filed.pt` (+ twins optional)
- `configure.zcml`:

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:zcml="http://namespaces.zope.org/zcml"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="fixture.conditions"
    >
  <include package="imio.emailkit" file="meta.zcml" />
  <include file="emails.zcml" />
</configure>
```

- `emails.zcml` (exercises the file-include edge AND conditions inside one block):

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:zcml="http://namespaces.zope.org/zcml"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="fixture.conditions"
    >
  <emailkit:templates>
    <emailkit:template name="filed" subject="[s_filed] Filed" />
    <emailkit:template name="installed_yes" subject="[s_yes] Yes"
        zcml:condition="installed imio.emailkit" />
    <emailkit:template name="installed_no" subject="[s_no] No"
        zcml:condition="installed no.such.package" />
    <emailkit:template name="featured" subject="[s_feat] Feat"
        zcml:condition="have some-feature" />
  </emailkit:templates>
</configure>
```

- [ ] **Step 2: Write the failing tests**

`tests/test_scan.py`:

```python
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
    assert "fixture.includes.sub:subbed" in names          # <include package=".sub">
    assert "fixture.includes:orphan" not in names          # orphan.zcml never included


def test_cross_package_include_is_skipped():
    scan.scan_package("fixture.includes")
    assert not [n for n in discovery.available_templates() if n.startswith("other_addon:")]


def test_overrides_zcml_wins():
    scan.scan_package("fixture.includes")
    assert discovery.get_template("fixture.includes:overridden").subject == "s_overridden"


def test_file_include_and_conditions():
    scan.scan_package("fixture.conditions")
    names = discovery.available_templates()
    assert "fixture.conditions:filed" in names             # <include file=...>
    assert "fixture.conditions:installed_yes" in names     # installed <real pkg>
    assert "fixture.conditions:installed_no" not in names  # installed <missing pkg>
    # Documented divergence: no feature provider loads at build time, so
    # `have <feature>` reads false.
    assert "fixture.conditions:featured" not in names


def test_scan_registers_same_as_runtime_execution():
    # The scan and a real zope.configuration run share the directive handlers,
    # so the registry contents must be identical for the same package.
    from zope.configuration import xmlconfig
    from zope.configuration.config import ConfigurationMachine

    import fixture.basic
    import imio.emailkit

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
        "import sys; sys.path[:0] = %r; "
        "from imio.emailkit import scan, discovery; "
        "scan.scan_package('fixture.basic'); "
        "assert 'fixture.basic:welcome' in discovery.available_templates()"
    ) % ([str(SCANFIXTURES)],)
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 3: Run to verify failure**

Run: `bin/pytest tests/test_scan.py -x -q`
Expected: FAIL — no module `imio.emailkit.scan`.

- [ ] **Step 4: Create `src/imio/emailkit/scan.py`**

```python
"""Execute a package's ZCML with only the emailkit directives live.

The build tooling (the buildout recipe's generated scripts, the preview server)
needs to know what a consumer package registers without booting a Zope
instance. Parsing the ZCML by hand would mean re-implementing includes,
conditions and overrides; loading it for real would mean importing every
directive handler in Plone. This module does neither: it runs the real
``zope.configuration`` machinery through a :class:`ConfigurationMachine`
subclass whose unknown-directive answer is "swallow it" instead of "crash".

Only ``imio.emailkit``'s ``meta.zcml`` is loaded, so ``emailkit:*`` executes
for real -- through the same handler, into the same registry, as at instance
startup -- while ``browser:page`` and friends are ignored *without their
handlers or classes ever being imported* (an unknown directive never resolves
its schema or handler; only ``<include package>`` imports anything, namely the
included package itself, to locate its files).

Includes are scoped to the scanned package: every egg is scanned from its own
roots, so following ``<include package="some.other.addon">`` would only
double-count. Known divergence from a full instance, accepted and documented:
feature flags (``zcml:condition="have plone-x"``) read false here, because
nothing loads the ZCML that provides features.
"""

from imio.emailkit import discovery  # noqa: F401  (re-exported for callers)
from importlib import import_module
from pathlib import Path
from zope.configuration import xmlconfig
from zope.configuration.config import ConfigurationMachine
from zope.configuration.config import defineSimpleDirective
from zope.configuration.exceptions import ConfigurationError

import imio.emailkit
import logging


logger = logging.getLogger("imio.emailkit.scan")

#: Substring that marks a ZCML file as (possibly) carrying emailkit directives.
#: The cheap pre-filter the build tooling runs before spending a real scan.
MARKER = "namespaces.imio.be/emailkit"


class _Swallowed:
    """Stack item standing in for a directive whose meta is not loaded.

    Accepts arbitrary nested directives (returning itself) and emits no
    configuration actions. One shared instance is enough: it is stateless.
    """

    def contained(self, name, data, info):
        return self

    def finish(self):
        pass


_SWALLOWED = _Swallowed()


def _swallow(context, data, info):
    return _SWALLOWED


class PermissiveConfigurationMachine(ConfigurationMachine):
    """A configuration machine that ignores what it does not know."""

    def factory(self, context, name):
        try:
            return super().factory(context, name)
        except ConfigurationError:
            logger.debug("Swallowing unknown directive %s", name)
            return _swallow


def scan_package(package):
    """Register the emailkit templates ``package``'s ZCML declares.

    Executes ``configure.zcml`` and then ``overrides.zcml`` (each only when
    present) from the package root -- the same two roots Zope's autoinclude
    loads -- and runs the resulting actions against the discovery registry.

    :param package: a dotted name or an imported package.
    :raises zope.configuration errors: a genuinely broken emailkit directive
        (bad attribute, duplicate name) raises exactly as it would at instance
        startup; the *caller* decides whether that stops a build.
    """
    if isinstance(package, str):
        package = import_module(package)
    machine = PermissiveConfigurationMachine()
    xmlconfig.registerCommonDirectives(machine)
    xmlconfig.include(machine, file="meta.zcml", package=imio.emailkit)
    _scope_includes(machine, package.__name__)
    package_dir = Path(package.__file__).parent
    if (package_dir / "configure.zcml").is_file():
        xmlconfig.include(machine, file="configure.zcml", package=package)
    if (package_dir / "overrides.zcml").is_file():
        xmlconfig.includeOverrides(machine, file="overrides.zcml", package=package)
    machine.execute_actions()


def _scope_includes(machine, root):
    """Confine ``<include>``/``<includeOverrides>`` to ``root``'s namespace.

    ``<include file=...>`` (package=None) always passes: it stays inside the
    package by construction. ``<include package=...>`` of anything outside
    ``root`` is dropped -- that package gets its own scan from its own roots.
    """

    def scoped(handler):
        def scoped_handler(_context, file=None, package=None, files=None):
            if package is not None:
                name = package.__name__
                if name != root and not name.startswith(root + "."):
                    logger.debug(
                        "Skipping <include package=%r> while scanning %s",
                        name,
                        root,
                    )
                    return
            handler(_context, file=file, package=package, files=files)

        return scoped_handler

    defineSimpleDirective(
        machine, "include", xmlconfig.IInclude, scoped(xmlconfig.include),
        namespace="*",
    )
    defineSimpleDirective(
        machine, "includeOverrides", xmlconfig.IInclude,
        scoped(xmlconfig.includeOverrides), namespace="*",
    )


def has_marker(package_dir):
    """Cheap pre-filter: does any ZCML under ``package_dir`` mention us?"""
    for zcml in Path(package_dir).rglob("*.zcml"):
        try:
            if MARKER in zcml.read_text(encoding="utf-8", errors="ignore"):
                return True
        except OSError:
            continue
    return False
```

- [ ] **Step 5: Run the tests**

Run: `bin/pytest tests/test_scan.py tests/test_zcml_directive.py -q`
Expected: PASS. Two likely adjustment points if not: (a) the overrides conflict — if `test_overrides_zcml_wins` raises `ConfigurationConflictError`, the includepath munging needs the configure root loaded via the same nesting depth; fix by loading `configure.zcml` through the *scoped* include handler path instead of the direct call (mirror how site.zcml does it) and re-run. (b) `defineSimpleDirective` ordering — scope AFTER the meta include (as written) so meta loading is unrestricted.

- [ ] **Step 6: Commit**

```bash
git add src/imio/emailkit/scan.py tests/test_scan.py tests/scanfixtures
git commit -m "feat: permissive-machine ZCML scan for the build tooling"
```

---

### Task 5: Convert the dummy add-ons; suite back to green

**Files:**
- Create: `tests/dummies/dummy/complete/configure.zcml`, `tests/dummies/dummy/minimal/configure.zcml`
- Delete: `tests/dummies/dummy_complete-1.0.dist-info/`, `tests/dummies/dummy_minimal-1.0.dist-info/`
- Modify: `tests/dummies/dummy/complete/__init__.py`, `tests/dummies/dummy/minimal/__init__.py` (remove `emailkit` dicts + MessageFactory if now unused; update docstrings to show the ZCML registration instead of the entry point)
- Modify: `tests/dummyaddons.py`
- Rewrite: `tests/test_discovery_dummies.py`
- Modify: `tests/dummies/README.md`
- Sweep: `tests/conftest.py`, `tests/test_dummy_isolation.py`, `tests/test_golden.py`, `tests/test_preview.py`, `tests/test_contentrules.py`, `tests/test_consumer_ci.py` — every `dummyaddons.registration()` / `invalidate_cache` / entry-point-wording caller

- [ ] **Step 1: Write the dummies' ZCML**

`tests/dummies/dummy/complete/configure.zcml` — port the existing dict verbatim (msgids and defaults from the current `__init__.py`; read it before deleting):

```xml
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="dummy.complete"
    >

  <include package="imio.emailkit" file="meta.zcml" />

  <!-- `directory` is also the default; stated so the reader of the
       registration sees where the build output lands without opening the
       Maizzle config. -->
  <emailkit:templates directory="templates">
    <!-- msgid defaults ported 1:1 from the old registration dict -->
    <emailkit:template
        name="convocation"
        subject="[email_subject_convocation] ...port the existing default..."
        preheader="[email_preheader_convocation] ...port..."
        />
    <emailkit:template
        name="notification"
        subject="[email_subject_notification_complete] ...port..."
        preheader="[email_preheader_notification_complete] ...port..."
        />
  </emailkit:templates>

</configure>
```

**Port the actual msgids/defaults from the current dicts — the strings above are placeholders for THIS plan step only; the executor must copy the real ones out of `tests/dummies/dummy/complete/__init__.py` and `dummy/minimal/__init__.py` before deleting them.** Same for `dummy.minimal` (one template, no twin, no explicit directory — minimal stays minimal: omit the `directory` attribute).

- [ ] **Step 2: Rewrite the installation seam in `tests/dummyaddons.py`**

Delete `_refresh_metadata_caches` and the dist-info prose in the module docstring (replace with a short "Registering through ZCML, and why the scan is the real code path" section). Replace `installed()` / `uninstalled()`:

```python
@contextmanager
def installed():
    """Register both dummy add-ons for the duration of the block, only.

    ``sys.path`` still gains ``tests/dummies`` (the packages must be importable
    -- the scan resolves them, fixtures import from them), and the registry is
    snapshotted so the block leaves no trace. Registration runs through
    ``imio.emailkit.scan``, i.e. the exact code path the build tooling uses on
    a real consumer.
    """
    from imio.emailkit import discovery
    from imio.emailkit import scan

    _drop_from_sys_path()
    sys.path.insert(0, str(DUMMIES_DIR))
    importlib.invalidate_caches()
    try:
        with discovery.overlay():
            for addon in ADDONS:
                scan.scan_package(addon.package)
            yield ADDONS
    finally:
        _drop_from_sys_path()


@contextmanager
def uninstalled():
    """Take them away again inside a block that has them installed.

    The negative control: without it, "the dummy templates are found" could be
    true for a reason that has nothing to do with the registration.
    """
    from imio.emailkit import discovery

    with discovery.overlay():
        for addon in ADDONS:
            discovery.forget_package(addon.package)
        yield
```

Update `DummyAddon.registration()`: delete it (it read the dict). Grep its callers first (`grep -rn "\.registration()" tests/`) and port each to read `discovery.get_template(addon.qualified(name))` instead.

- [ ] **Step 3: Rewrite `tests/test_discovery_dummies.py`**

Keep every behavioral assertion that still applies (namespacing, twins, negative control outside the fixture, subjects as msgids with the dummy's domain) but drive them through `installed()`/the registry instead of entry-point machinery. Drop tests that asserted entry-point mechanics (cache invalidation, dist-info visibility). Add one new test: `dummy.complete`'s subject msgid domain is `dummy.complete` (proves `i18n_domain` flows from the dummy's own ZCML).

- [ ] **Step 4: Sweep the dummy consumers**

`grep -rn "invalidate_cache\|entry.point\|entry_points\|dist.info\|registration()" tests/ --include="*.py"` — fix every hit to the new seam. `tests/test_dummy_isolation.py` guards the "leaves no trace" property; it must now assert on the registry before/after `installed()` instead of `sys.path`+cache state (keep the sys.path assertion too — it still matters for imports).

- [ ] **Step 5: Delete the dist-info directories**

```bash
git rm -r tests/dummies/dummy_complete-1.0.dist-info tests/dummies/dummy_minimal-1.0.dist-info
```

Update `tests/dummies/README.md`: the "Faking an entry point" section becomes "Registering through ZCML" — the dummies now carry a `configure.zcml` exactly like a real consumer, and `installed()` runs the real build-tool scan over them.

- [ ] **Step 6: Full main-suite checkpoint**

Run: `bin/pytest -q`
Expected: **everything green.** This is the checkpoint where the runtime cut is complete. Budget real time here: `test_golden.py`, `test_preview.py`, `test_contentrules.py`, `test_consumer_ci.py` all lean on the dummies and will surface any seam the sweep missed.

- [ ] **Step 7: Commit**

```bash
git add -A tests
git commit -m "feat: dummy addons register through ZCML; suite green on the directive"
```

---

### Task 6: The recipe — marker scan at install time, real scan in the scripts

**Files:**
- Modify: `recipe/src/imio/recipe/emailkit/projects.py`
- Modify: `recipe/src/imio/recipe/emailkit/__init__.py` (docstring + `_record` warning + eggs-option error message)
- Modify: `recipe/src/imio/recipe/emailkit/cli.py` (`--package` help)
- Modify: `recipe/src/imio/recipe/emailkit/preview_emails.py` (`render_all` re-scan)
- Modify: `recipe/tests/test_projects.py` (+ sweep other recipe tests for entry-point fixtures)

- [ ] **Step 1: Rewrite the collectors in `projects.py`**

Delete `ENTRY_POINT_GROUP` and `_resolve_by_import`. Keep `Project`, `make_project`, `find_emails_dir`, `locate_package`, `kit_dir_from_working_set`, `kit_dir_from_environment`, `select` untouched. Add:

```python
#: Substring that marks a ZCML file as carrying emailkit directives. Duplicated
#: from ``imio.emailkit.scan.MARKER`` on purpose: this module runs inside
#: buildout, where importing imio.emailkit would pull the Plone runtime into
#: the build system. ``tests/test_projects.py::test_marker_matches_the_runtime``
#: fails if the two ever drift.
MARKER = "namespaces.imio.be/emailkit"

#: Directories never worth descending into while looking for ZCML.
PRUNE_DIRS = {"node_modules", "__pycache__", ".git", "emails"}


def iter_marker_packages(dist):
    """``(dotted_name, package_dir)`` for each package of ``dist`` whose ZCML
    mentions the emailkit namespace.

    Filesystem-only, import-free: safe inside buildout. The dotted name is the
    path of the directory holding the marked ZCML file, relative to the
    ``sys.path`` root -- which is exactly the namespace the directive gives its
    templates at runtime (the package the ZCML file belongs to).
    """
    location = Path(getattr(dist, "location", "") or "")
    for root in (location, location / "src"):
        if not root.is_dir():
            continue
        for top in _top_level_names(dist, root):
            top_dir = root / top
            if not top_dir.is_dir():
                continue
            for zcml in sorted(top_dir.rglob("*.zcml")):
                if PRUNE_DIRS.intersection(zcml.parts):
                    continue
                try:
                    text = zcml.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if MARKER not in text:
                    continue
                package_dir = zcml.parent
                if not (package_dir / "__init__.py").is_file():
                    logger.warning(
                        "%s mentions the emailkit namespace but %s is not a "
                        "package directory; skipping it.",
                        zcml,
                        package_dir,
                    )
                    continue
                yield ".".join(package_dir.relative_to(root).parts), package_dir


def _top_level_names(dist, root):
    """The distribution's top-level package names, from metadata when it has
    any, from the filesystem when it does not (develop eggs, mainly).

    Restricting the walk to the dist's own top-level packages is what keeps a
    shared ``site-packages`` location from being rglobbed once per installed
    distribution.
    """
    try:
        names = [line for line in dist.get_metadata_lines("top_level.txt") if line]
    except (KeyError, OSError, AttributeError):
        names = []
    if names:
        return names
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and (p / "__init__.py").is_file()
    )
```

Replace `from_working_set`:

```python
def from_working_set(working_set):
    """Collect the projects of every dist whose ZCML carries the marker.

    Imports nothing, executes nothing -- a buildout run stays a buildout run.
    The directive's ``directory`` attribute is therefore *not* read;
    :data:`DEFAULT_DIRECTORY` is assumed, which is what the spec's example and
    every registration in this repository use. The generated scripts resolve it
    for real (:func:`from_environment`), so a package that overrides it still
    builds correctly -- only buildout's log line would name the default.
    """
    resolved = {}
    for dist in sorted(working_set, key=str):
        for dotted, package_dir in iter_marker_packages(dist):
            resolved.setdefault(dotted, make_project(dotted, package_dir))
    return [resolved[name] for name in sorted(resolved)]
```

Replace `from_environment`:

```python
def from_environment():
    """Collect the projects visible from ``sys.path``, resolved for real.

    Used by the generated scripts, which run with the part's ``eggs`` on their
    path -- so ``imio.emailkit`` is importable and each candidate's ZCML is
    *executed* (permissively) rather than pattern-matched: the ``directory``
    attribute, includes, conditions and overrides all behave exactly as at
    instance startup. Side effect, relied on by ``preview-emails``: the
    discovery registry is populated.
    """
    from imio.emailkit import discovery
    from imio.emailkit import scan

    import pkg_resources

    projects = []
    seen = set()
    for dist in sorted(pkg_resources.working_set, key=str):
        for dotted, package_dir in iter_marker_packages(dist):
            if dotted in seen:
                continue
            seen.add(dotted)
            try:
                scan.scan_package(dotted)
            except Exception as exc:
                logger.warning(
                    "Could not scan the emailkit registration of %r (%s: %s); "
                    "skipping it.",
                    dotted,
                    type(exc).__name__,
                    exc,
                )
                continue
            templates_dir = discovery.registered_directories().get(dotted)
            if templates_dir is None:
                # Marker present but no block survived (all conditioned away,
                # say). Nothing to build.
                continue
            directory = str(templates_dir.relative_to(package_dir))
            projects.append(make_project(dotted, package_dir, directory))
    return projects
```

Update the module docstring's "Two collectors" section accordingly.

- [ ] **Step 2: Update the recipe's wording**

- `recipe/src/imio/recipe/emailkit/__init__.py`: module docstring ("collects the distributions that expose the entry point" → "collects the packages whose ZCML registers `<emailkit:templates>`"); the `eggs`-missing `user_error` (drop `projects_module.ENTRY_POINT_GROUP`, say "to scan for `emailkit:templates` ZCML registrations"); the `_record` no-packages warning ("no distribution in `eggs` registers `<emailkit:templates>` in its ZCML, so the generated scripts will have nothing to do").
- `recipe/src/imio/recipe/emailkit/cli.py:48-56`: `--package` help → `"act on this package only, as named by its <emailkit:templates> ZCML registration. Default: every registered package."`

- [ ] **Step 3: Fix `render_all` in `preview_emails.py`**

Replace lines 333-341 (the two invalidations):

```python
    from imio.emailkit import discovery
    from imio.emailkit import scan

    # `imio.emailkit.__init__` rebinds the name `render` on the package to the
    # *function*, so `import imio.emailkit.render` yields the function too. The
    # module is only reachable through a `from ... import <name>`.
    from imio.emailkit.render import invalidate_cache as forget_templates

    # Rescan rather than trust an earlier pass: a template added or rebuilt
    # since then must show up, and the scan is cheap.
    discovery.reset()
    for project in projects:
        try:
            scan.scan_package(project.package)
        except Exception as exc:
            logger.warning("rescan of %s failed: %s", project.package, exc)
    forget_templates()
```

- [ ] **Step 4: Rewrite the recipe's discovery tests**

`recipe/tests/test_projects.py`: replace entry-point fixtures with on-disk ones. Representative tests (adapt to the existing conftest's fixture style — read it first):

```python
def make_dist_dir(tmp_path, dotted="acme.mail", marker=True, src_layout=False):
    root = tmp_path / "dist"
    base = root / "src" if src_layout else root
    package_dir = base.joinpath(*dotted.split("."))
    package_dir.mkdir(parents=True)
    for part in range(1, len(dotted.split("."))):
        (base.joinpath(*dotted.split(".")[:part]) / "__init__.py").write_text("")
    (package_dir / "__init__.py").write_text("")
    body = "namespaces.imio.be/emailkit" if marker else "namespaces.zope.org"
    (package_dir / "configure.zcml").write_text(f"<configure><!-- {body} --></configure>")
    return root, package_dir


class FakeDist:
    def __init__(self, location, top_level=()):
        self.location = str(location)
        self._top = list(top_level)

    def get_metadata_lines(self, name):
        if name == "top_level.txt" and self._top:
            return list(self._top)
        raise KeyError(name)


def test_marker_package_found(tmp_path):
    root, _dir = make_dist_dir(tmp_path)
    found = list(projects.iter_marker_packages(FakeDist(root, ["acme"])))
    assert [dotted for dotted, _ in found] == ["acme.mail"]


def test_unmarked_package_ignored(tmp_path):
    root, _dir = make_dist_dir(tmp_path, marker=False)
    assert list(projects.iter_marker_packages(FakeDist(root, ["acme"]))) == []


def test_src_layout_found(tmp_path):
    root, _dir = make_dist_dir(tmp_path, src_layout=True)
    found = list(projects.iter_marker_packages(FakeDist(root, ["acme"])))
    assert [dotted for dotted, _ in found] == ["acme.mail"]


def test_no_top_level_metadata_falls_back_to_filesystem(tmp_path):
    root, _dir = make_dist_dir(tmp_path)
    found = list(projects.iter_marker_packages(FakeDist(root)))
    assert [dotted for dotted, _ in found] == ["acme.mail"]


def test_marker_matches_the_runtime():
    imio_emailkit_scan = pytest.importorskip("imio.emailkit.scan")
    assert projects.MARKER == imio_emailkit_scan.MARKER
```

Also update/keep `from_working_set` tests against a fake working set of `FakeDist`s, and sweep `recipe/tests/` for other entry-point fixtures: `grep -rn "entry_point\|entry-points\|ENTRY_POINT" recipe/ --include="*.py" --include="*.toml" --include="*.md"` — the `recipe/tests/consumer/` fixture package's `pyproject.toml`/`setup.py` declare the old entry point: convert that fixture to a `configure.zcml` registration too.

- [ ] **Step 5: Run the recipe suite**

Run: `cd recipe && ../bin/pytest tests/ -q` (adjust to the recipe's actual runner if different — check `.github/workflows/` for how CI runs it).
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A recipe
git commit -m "feat: recipe discovers consumers by ZCML marker + permissive scan"
```

---

### Task 7: Documentation and the final sweep

**Files:**
- Modify: `SPEC.md` (§4 registration subsection, §5 step 1, the §4 row of the phase table at line ~347)
- Modify: `README.md`, `SKILL.md` (line ~305 registration example, plus the frontmatter description's "entry point" mention)
- Modify: `docs/DECISIONS.md` (append a dated decision entry)
- Create: `news/+zcml-directive.feature.md`
- Sweep: every remaining stale mention

- [ ] **Step 1: Rewrite SPEC.md §4's "Registration: entry point"**

New subsection "Registration: ZCML directive" — the consumer example becomes:

```xml
<!-- imio/pm/notifications/configure.zcml -->
<configure
    xmlns="http://namespaces.zope.org/zope"
    xmlns:emailkit="http://namespaces.imio.be/emailkit"
    i18n_domain="imio.pm.notifications"
    >

  <include package="imio.emailkit" file="meta.zcml" />

  <emailkit:templates directory="templates">
    <emailkit:template
        name="item_published"
        subject="[email_subject_item_published] An item was published"
        preheader="[email_preheader_item_published] ..."
        />
    <emailkit:template
        name="meeting_convocation"
        subject="[email_subject_meeting_convocation] Convocation"
        />
  </emailkit:templates>

</configure>
```

Bullet updates: namespacing derived from the ZCML file's package; subject/preheader are `MessageID`s in the file's `i18n_domain` (`[msgid] Default` syntax); duplicate names are a `ConfigurationConflictError`; `overrides.zcml` replaces registrations; the i18n caveat (i18ndude does not extract from ZCML — restate msgids in a `msgids.py`, as `imio.emailkit` itself does); failure modes otherwise unchanged (missing `.pt` → skipped + warning, missing twin → warning + fallback).

- [ ] **Step 2: Rewrite SPEC.md §5 step 1**

"Resolves all eggs, collects the packages whose ZCML mentions the emailkit namespace (filesystem marker scan — buildout imports nothing), and records `(package, emails_dir, templates_dir)` tuples. The generated scripts re-resolve at run time by *executing* each candidate's ZCML through a permissive configuration machine (only the emailkit directives are live; unknown directives are swallowed unimported), so `directory`, includes, conditions and `overrides.zcml` behave exactly as at instance startup. Known divergence: feature-flag conditions (`have x`) read false at build time." Also fix the §4 phase-table row (line ~347) naming the entry point.

- [ ] **Step 3: README.md + SKILL.md + DECISIONS.md + news**

- `README.md:42` area: replace the entry-point mention in "Some entry points worth naming" (check context; likely rename the section item to the ZCML registration).
- `SKILL.md:305-310`: the registration example → the ZCML block; `SKILL.md:3` description: "an `imio.emailkit.templates` entry point" → "an `<emailkit:templates>` ZCML registration".
- `docs/DECISIONS.md`: append an entry (match the file's existing format) recording: ZCML directive replaces entry point + dict; why (conflict detection, overrides, i18n_domain, one registration idiom); the permissive-machine scan and its one divergence; the i18ndude/msgids.py shim; clean cut, no deprecation window. Also update the `docs/DECISIONS.md:1397` mention of the entry-point group.
- `news/+zcml-directive.feature.md`:

```markdown
Templates from consumer add-ons are now registered with the
`<emailkit:templates>` ZCML directive instead of the
`imio.emailkit.templates` entry point + dict. Duplicate names become
configuration conflicts, `overrides.zcml` works, and the subject/preheader
msgid domain comes from the ZCML file's `i18n_domain`. The buildout recipe
and the `bin/` scripts discover consumers by executing their ZCML through a
permissive configuration machine — no entry point, no hand-rolled parsing.
```

- [ ] **Step 4: The final sweep**

```bash
grep -rn "imio.emailkit.templates\|entry.point\|entry_points\|iter_entry_points\|invalidate_cache\|warm_cache" \
  src tests recipe docs SPEC.md README.md SKILL.md Makefile --include="*" \
  | grep -v "z3c.autoinclude\|\.mo\b\|node_modules\|vocabularies.*TEMPLATES\|\.dist-info"
```

Fix every remaining hit that refers to the *old registration mechanism* (docstrings in `render.py`, `golden.py`, `email.py`, `browser/preview.py`, `testing.py`, `tests/support.py`, `tests/conftest.py` are the likely stragglers). Leave alone: the vocabulary utility name `"imio.emailkit.templates"` (it names a vocabulary, not the entry-point group — but fix its docstring if it says "entry-point"), the `z3c.autoinclude.plugin` entry point, and generic uses of the word.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "docs: SPEC/README/SKILL/DECISIONS describe the ZCML registration"
```

---

### Task 8: Full verification

- [ ] **Step 1: Both suites, cold**

```bash
bin/pytest -q                     # main package
cd recipe && ../bin/pytest tests/ -q && cd ..
```

Expected: all green.

- [ ] **Step 2: The linters CI runs**

Check `.github/workflows/` for the lint jobs (ruff etc. — `pyproject.toml` has ruff config) and run the same commands locally, e.g. `bin/ruff check src tests recipe` and `bin/ruff format --check` if configured. Fix findings.

- [ ] **Step 3: The buildout smoke test, if cheap**

`test-buildout.cfg` exercises the recipe end-to-end. If `bin/buildout -c test-buildout.cfg` is part of CI (check the workflows), run it; otherwise skip — CI will.

- [ ] **Step 4: Sanity-run the locales tool's extraction assumption**

Run: `bin/pytest tests/test_msgids.py -q` (already green from Task 3; this is the drift guard, cheap to re-run).

- [ ] **Step 5: Final commit if anything moved**

```bash
git status --short   # expect clean; commit any lint fixes with "chore: lint"
```

---

## Self-review notes (already applied)

- **Spec coverage:** directive+registry (Tasks 1-3), permissive scan with all fixture semantics incl. the feature-flag divergence and the no-instance subprocess test (Task 4), same-code-path parity test (Task 4), dummies via the real scan (Task 5), recipe split install-time-marker / script-time-scan + preview rescan (Task 6), SPEC/README/SKILL/DECISIONS/news + i18n caveat via msgids.py (Tasks 3, 7). Clean cut: entry point deleted in Tasks 3 (own), 5 (dummies), 6 (recipe + consumer fixture).
- **Known judgment calls the executor may hit:** (a) `xmlconfig.string` context-package plumbing in the Task 2 test helper; (b) overrides-conflict resolution shape in Task 4 Step 5 — both have explicit fallback instructions inline. Neither changes the public design.
- **Type consistency:** `scan_package(str|module)`, `discovery.load_template(package, package_dir, directory, basename, subject, preheader)`, `iter_marker_packages(dist) -> (dotted, Path)`, `make_project(package, package_dir, directory=None)` — used consistently across tasks.
