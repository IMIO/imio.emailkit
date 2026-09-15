"""The only module in this distribution that knows Node exists.

Zero Node.js in production: Node is a developer/CI tool only, and buildout-time
compilation is rejected outright, because it would make Node a production
dependency across ~350 applications.

Consequently: **nothing here is imported at buildout time.** The recipe's
``install()`` imports this module only when ``compile-on-install = true``, which
defaults to false. ``tests/test_no_node.py`` asserts that, and the buildout
acceptance harness proves it by running a whole buildout with ``node`` absent from
``PATH``.
"""

from pathlib import Path

import hashlib
import logging
import os
import shutil
import subprocess
import sys


logger = logging.getLogger("imio.recipe.emailkit")

LOCKFILE = "package-lock.json"
MANIFEST = "package.json"
NODE_MODULES = "node_modules"

#: Written inside ``node_modules`` after a successful install, holding the digest
#: of the lockfile it was installed from. The goal is running ``npm ci`` only if
#: ``node_modules`` is stale vs. lockfile; a digest answers that question
#: exactly, where the mtime comparison the Makefile precursor uses answers it
#: approximately (npm touches ``node_modules`` for unrelated reasons, and a
#: checkout or a rebase can order the two files either way).
STAMP = ".imio-emailkit-lock"


class NodeError(Exception):
    """Node is missing, or a Node command failed."""


def resolve(node_bin="node"):
    """Return ``(node, npm, npx)`` executables for a ``node-bin`` setting.

    Only ``node-bin`` is a named setting; resolution otherwise falls back to
    ``PATH``. ``npm`` and ``npx`` are therefore derived: from the same directory
    when ``node-bin`` is a
    path, from ``PATH`` when it is a bare name. That keeps one option instead of
    three and still works for the case that motivates the option -- a Node
    installed outside ``PATH``, e.g. by nvm or a CI cache.
    """
    node_bin = node_bin or "node"
    if os.sep in node_bin or (os.altsep and os.altsep in node_bin):
        directory = Path(node_bin).parent
        node = Path(node_bin)
        npm, npx = directory / "npm", directory / "npx"
        for executable in (node, npm, npx):
            if not executable.exists():
                raise NodeError(
                    f"node-bin points at {node_bin}, but {executable} is missing. "
                    f"`npm` and `npx` are looked for beside `node`."
                )
        return str(node), str(npm), str(npx)

    found = {name: shutil.which(name) for name in ("node", "npm", "npx")}
    found["node"] = shutil.which(node_bin) or found["node"]
    missing = sorted(name for name, path in found.items() if path is None)
    if missing:
        raise NodeError(
            f"{', '.join(missing)} not found on PATH. Node is required for the "
            f"email build only: installing, testing and running an addon never "
            f"needs it, and buildout never invokes it."
        )
    return found["node"], found["npm"], found["npx"]


def available(node_bin="node"):
    """``True`` when Node can be resolved. For reporting, never for branching."""
    try:
        resolve(node_bin)
    except NodeError:
        return False
    return True


def ensure_dependencies(emails_dir, npm, force=False):
    """``npm ci`` in ``emails_dir``, but only when it is needed.

    Falls back to ``npm install`` while there is no lockfile -- ``npm ci``
    requires one, and the fallback is also what creates it, after which every
    later run takes the reproducible path. Same behaviour as the Makefile
    precursor this generalises.
    """
    emails_dir = Path(emails_dir)
    if not (emails_dir / MANIFEST).is_file():
        raise NodeError(
            f"{emails_dir} has no {MANIFEST}, so its Maizzle toolchain cannot be "
            f"installed. A consumer's `emails/` directory is an npm project."
        )
    lockfile = emails_dir / LOCKFILE
    stamp = emails_dir / NODE_MODULES / STAMP

    if not force and not _stale(lockfile, stamp):
        logger.info("%s: node_modules is up to date", emails_dir)
        return False

    command = [npm, "ci"] if lockfile.is_file() else [npm, "install"]
    if not lockfile.is_file():
        logger.warning(
            "%s has no %s yet; running `npm install` to create it. Commit it -- "
            "every later run is then reproducible.",
            emails_dir,
            LOCKFILE,
        )
    # Deliberately no `npm install` fallback when `npm ci` refuses the lockfile.
    # Falling back resolves a *different* toolchain than the lockfile pins, so the
    # compiled output drifts and the staleness gate downstream reports the
    # committed templates as stale -- blaming the templates for a dependency
    # problem, several steps from the cause.
    #
    # `npm ci` failing with `Missing: ... from lock file` means the lockfile was
    # regenerated on top of an existing node_modules: npm then records that tree
    # rather than a full resolution and drops the optional platform packages.
    # Regenerate with both removed:
    #   cd emails && rm -rf node_modules package-lock.json && npm install
    run(command, cwd=emails_dir)
    if lockfile.is_file():
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(_digest(lockfile), encoding="utf-8")
    return True


def _stale(lockfile, stamp):
    if not stamp.parent.is_dir():
        return True
    if not lockfile.is_file():
        # No lockfile to compare against; an existing node_modules is as good as
        # it gets, so do not reinstall on every run.
        return False
    if not stamp.is_file():
        return True
    return stamp.read_text(encoding="utf-8").strip() != _digest(lockfile)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(emails_dir, npx, watch=False, extra_args=()):
    """Run ``maizzle build`` (or its watcher) in ``emails_dir``.

    ``npx maizzle build`` rather than ``maizzle build``: ``emails/`` is a private
    npm project with a local ``@maizzle/framework``, so the binary lives in
    ``node_modules/.bin`` and only ``npx`` finds it without assuming a global
    install.
    """
    command = [npx, "maizzle", "dev" if watch else "build", *extra_args]
    run(command, cwd=emails_dir)


def run(command, cwd=None, env=None):
    """Run ``command``, streaming its output, and raise on a non-zero exit.

    Output is *not* captured. A Maizzle build's own diagnostics are the only
    warning a developer gets for a whole class of failures, and swallowing them
    into an exception message that nobody prints is how those failures became
    silent in the first place.
    """
    printable = " ".join(str(part) for part in command)
    logger.info("$ %s%s", printable, f"   (in {cwd})" if cwd else "")
    # The child writes straight to fd 1/2 while our own `print` output sits in a
    # Python buffer whenever stdout is a pipe -- which is every CI log. Without
    # this flush the report reads in the wrong order, which is how a passing gate
    # gets mistaken for a failing one.
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        completed = subprocess.run(  # noqa: S603 - argv list, never a shell
            [str(part) for part in command],
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
        )
    except OSError as exc:
        raise NodeError(f"could not run `{printable}`: {exc}") from exc
    if completed.returncode != 0:
        raise NodeError(f"`{printable}` exited {completed.returncode}")
    return completed.returncode
