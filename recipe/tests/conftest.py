"""Fixtures for `imio.recipe.emailkit`'s own suite.

Node is faked (``fake_node``), so tests run fast and without a network.
Buildout is not faked; only the ``buildout`` mapping is a stub.
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
    """A directory shaped like ``imio/emailkit/kit``, with real files."""
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
    """A consumer addon in the in-package layout: ``emails/`` and
    ``templates/`` as siblings inside the package directory."""
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
    """A checkout whose Maizzle project sits at the root, four levels above."""
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
    """Three executables standing in for ``node``, ``npm`` and ``npx``."""
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
              # why the staleness check snapshots first.
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
    """``fake_node`` prepended to ``PATH``, so it wins over a real Node."""
    binary, logs = fake_node
    monkeypatch.setenv("PATH", os.pathsep.join([str(binary), os.environ["PATH"]]))
    return binary, logs


def invocations(logs, name):
    path = Path(logs) / name
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []
