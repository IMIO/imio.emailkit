"""Fixtures for `imio.recipe.emailkit`'s own suite.

Two design choices worth stating, because they are what keeps this suite fast and
honest at the same time:

**Node is faked, once, here.** ``fake_node`` writes three shell scripts that
record their invocation and, for ``npx maizzle build``, write a predictable file
into the output directory. Every test about *wiring, staleness, restoration and
exit codes* then runs in milliseconds and without a network. The real toolchain is
exercised by the buildout acceptance harness (``make buildout-test``), which is
where "does Maizzle actually produce a `.pt`" belongs -- a unit test that shells
out to npm is a unit test people skip.

**Buildout is not faked.** ``zc.buildout`` and ``zc.recipe.egg`` are hard
dependencies of this distribution and are installed in its test environment, so
the recipe class is exercised against the real ``pkg_resources`` types. Only the
``buildout`` *mapping* is a stub, because it is a mapping.
"""

from pathlib import Path

import os
import pytest
import sys
import textwrap


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


NPM_LOG = "npm.log"
NPX_LOG = "npx.log"


@pytest.fixture
def kit(tmp_path):
    """A directory shaped like ``imio/emailkit/kit`` (SPEC §3), with real files."""
    root = tmp_path / "egg" / "imio" / "emailkit" / "kit"
    (root / "layouts").mkdir(parents=True)
    (root / "components").mkdir(parents=True)
    (root / "maizzle.config.base.js").write_text(
        "export const kitDir = 'x'\nexport function kitBaseConfig() { return {} }\n"
        "export default kitBaseConfig()\n",
        encoding="utf-8",
    )
    (root / "tailwind.css").write_text(
        "@theme { --brand: #e6007e; }\n", encoding="utf-8"
    )
    (root / "strip-comments.js").write_text("export const x = 1\n", encoding="utf-8")
    (root / "layouts" / "Main.vue").write_text(
        "<template><div/></template>\n", encoding="utf-8"
    )
    (root / "components" / "Button.vue").write_text(
        "<template><a/></template>\n", encoding="utf-8"
    )
    return root


@pytest.fixture
def consumer(tmp_path):
    """A consumer addon in SPEC §4's **in-package** layout, with one built ``.pt``.

    ``emails/`` and ``templates/`` are siblings inside the package directory, which
    is what §4 draws. The other layout -- ``emails/`` at the checkout root, which
    ``imio.emailkit`` itself uses -- is covered by ``root_layout_consumer``.
    """
    package_dir = tmp_path / "site-packages" / "acme" / "notifications"
    emails = package_dir / "emails"
    (emails / "src" / "templates").mkdir(parents=True)
    (emails / "twins").mkdir()
    (package_dir / "templates").mkdir()
    (package_dir / "tests" / "fixtures").mkdir(parents=True)
    (package_dir / "tests" / "golden").mkdir()
    (emails / "maizzle.config.js").write_text("export default {}\n", encoding="utf-8")
    (emails / "package.json").write_text('{"name":"acme-emails"}\n', encoding="utf-8")
    (emails / "src" / "templates" / "hello.vue").write_text(
        "<template><div>${title}</div></template>\n", encoding="utf-8"
    )
    return package_dir


@pytest.fixture
def root_layout_consumer(tmp_path):
    """A checkout whose Maizzle project sits at the *root*, four levels above.

    This is ``imio.emailkit``'s own shape (``emails/`` beside ``src/``), and it is
    the reason ``find_emails_dir`` ascends instead of only looking in the package.
    """
    root = tmp_path / "checkout"
    package_dir = root / "src" / "acme" / "roots"
    package_dir.mkdir(parents=True)
    (package_dir / "templates").mkdir()
    emails = root / "emails" / "src" / "templates"
    emails.mkdir(parents=True)
    (root / "emails" / "maizzle.config.js").write_text(
        "export default {}\n", encoding="utf-8"
    )
    (root / "emails" / "package.json").write_text("{}\n", encoding="utf-8")
    (root / "tests").mkdir()
    return package_dir


@pytest.fixture
def project(consumer):
    from imio.recipe.emailkit import projects

    return projects.make_project("acme.notifications", consumer)


@pytest.fixture
def fake_node(tmp_path):
    """Three executables standing in for ``node``, ``npm`` and ``npx``.

    ``npx maizzle build`` writes ``<output>/hello.pt`` with deterministic content,
    which is exactly the property the staleness gate depends on. Where the output
    goes is read from ``EMAILKIT_FAKE_OUTPUT``, so a test can point it at the
    project's ``templates/`` directory the way a real ``maizzle.config.js`` would.
    """
    binary = tmp_path / "fakebin"
    binary.mkdir()

    (binary / "node").write_text("#!/bin/sh\necho fake-node\n", encoding="utf-8")
    (binary / "npm").write_text(
        textwrap.dedent(f"""\
            #!/bin/sh
            echo "$@" >> "$EMAILKIT_FAKE_LOGS/{NPM_LOG}"
            mkdir -p node_modules
            exit 0
            """),
        encoding="utf-8",
    )
    (binary / "npx").write_text(
        textwrap.dedent(f"""\
            #!/bin/sh
            echo "$@" >> "$EMAILKIT_FAKE_LOGS/{NPX_LOG}"
            if [ -n "$EMAILKIT_FAKE_OUTPUT" ]; then
              mkdir -p "$EMAILKIT_FAKE_OUTPUT"
              # `maizzle build` EMPTIES its output directory. Faithfully faked,
              # because that behaviour is why the twins are copied afterwards and
              # why the staleness gate snapshots first.
              rm -f "$EMAILKIT_FAKE_OUTPUT"/*.pt
              printf '<html>built ${{title}}</html>\\n' > "$EMAILKIT_FAKE_OUTPUT/hello.pt"
            fi
            exit "${{EMAILKIT_FAKE_EXIT:-0}}"
            """),
        encoding="utf-8",
    )
    for name in ("node", "npm", "npx"):
        (binary / name).chmod(0o755)
    logs = tmp_path / "logs"
    logs.mkdir()
    os.environ["EMAILKIT_FAKE_LOGS"] = str(logs)
    yield binary, logs
    for key in ("EMAILKIT_FAKE_LOGS", "EMAILKIT_FAKE_OUTPUT", "EMAILKIT_FAKE_EXIT"):
        os.environ.pop(key, None)


@pytest.fixture
def node_on_path(fake_node, monkeypatch):
    """``fake_node`` made discoverable through ``PATH``, as ``node-bin`` expects.

    Prepended rather than substituted: the fakes are shell scripts and need
    ``mkdir``, ``rm`` and ``printf`` to exist. ``shutil.which`` takes the first
    match, so the fakes still win over a real Node.
    """
    binary, logs = fake_node
    monkeypatch.setenv("PATH", os.pathsep.join([str(binary), os.environ["PATH"]]))
    return binary, logs


def invocations(logs, name):
    path = Path(logs) / name
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []
