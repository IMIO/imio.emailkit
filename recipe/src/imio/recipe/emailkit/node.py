"""The only module in this distribution that knows Node exists.

Node is a developer and CI tool only. Buildout-time compilation is
rejected by default, so Node never becomes a production dependency.

Nothing here is imported at buildout time. The recipe's ``install()``
imports this module only when ``compile-on-install = true``, which
defaults to false.
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

#: Holds the digest of the lockfile last installed, so staleness can be
#: checked exactly instead of by comparing mtimes.
STAMP = ".imio-emailkit-lock"


class NodeError(Exception):
    """Node is missing, or a Node command failed."""


def resolve(node_bin="node"):
    """Return ``(node, npm, npx)`` executables for a ``node-bin`` setting.

    ``npm`` and ``npx`` are derived: from the same directory when
    ``node-bin`` is a path, from ``PATH`` when it is a bare name.
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

    Falls back to ``npm install`` while there is no lockfile, since
    ``npm ci`` requires one and this fallback creates it.
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
    # No `npm install` fallback when `npm ci` refuses the lockfile: that
    # would resolve a different toolchain than the lockfile pins.
    #
    # "Missing: ... from lock file" means the lockfile was regenerated on
    # top of an existing node_modules. Fix it with:
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
        # No lockfile to compare against, so treat existing node_modules as good.
        return False
    if not stamp.is_file():
        return True
    return stamp.read_text(encoding="utf-8").strip() != _digest(lockfile)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(emails_dir, npx, watch=False, extra_args=()):
    """Run ``maizzle build`` (or its watcher) in ``emails_dir``.

    Uses ``npx``: the binary lives in ``node_modules/.bin``, and only
    ``npx`` finds it without a global install.
    """
    command = [npx, "maizzle", "dev" if watch else "build", *extra_args]
    run(command, cwd=emails_dir)


def run(command, cwd=None, env=None):
    """Run ``command``, streaming its output, and raise on a non-zero exit."""
    printable = " ".join(str(part) for part in command)
    logger.info("$ %s%s", printable, f"   (in {cwd})" if cwd else "")
    # Flush first: our own buffered output would otherwise print after
    # the child's, which writes straight to fd 1/2.
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
