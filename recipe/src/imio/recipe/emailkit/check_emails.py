"""``bin/check-emails`` (SPEC §5). Two gates in one script. **This is the CI gate.**

    bin/check-emails [--package NAME]

Gate 1 -- *staleness*: "compile each package into a tmpdir and ``diff`` against the
committed ``templates/``; exit 1 with a per-file diff summary if stale."

Gate 2 -- *the authoring lint*: the ``.vue`` sources are checked against SPEC §3's
authoring rules. That lint lives in ``imio.emailkit`` as
``python -m imio.emailkit.lint <paths>`` and **is called, not reimplemented** --
the rules are about the templates, so they belong with the runtime that ships
them, and a second copy here would be a second copy to keep correct.

Why the staleness gate matters more than it looks: the compiled ``.pt`` is the
production artifact, Node never runs in production, and *nothing else in the
system notices* when someone edits a ``.vue`` source and forgets to rebuild. It is
the settled position of this project that the Maizzle exit code carries almost no
information about correctness (``docs/DECISIONS.md``), which leaves this diff and
§7's golden files as the only trustworthy gates.

A note on "into a tmpdir": the build's destination is the consumer's own
``output.path``, and Maizzle has no configurable alternate destination -- it writes
into the package by design. So the direction is inverted, exactly as the Makefile
precursor does it: the *committed* output is snapshotted to a tmpdir, the build
runs in place, the two are compared, and the snapshot is restored on the way out,
unconditionally. A check that leaves your working tree holding a build you did not
ask for is a check people stop running.
"""

from imio.recipe.emailkit import cli
from imio.recipe.emailkit import compile_emails
from imio.recipe.emailkit import kit as kit_module
from imio.recipe.emailkit import node as node_module
from imio.recipe.emailkit import projects as projects_module
from pathlib import Path

import difflib
import os
import subprocess
import sys
import tempfile


DESCRIPTION = (
    "CI gate for email templates: the committed `.pt` output must match a fresh "
    "build, and the `.vue` sources must obey SPEC §3's authoring rules."
)

#: The lint's interface, as agreed with the workstream that owns it. Invoked as a
#: subprocess with this interpreter, so it runs with exactly the script's own
#: ``sys.path`` -- i.e. the part's eggs -- and its exit code is the gate.
LINT_MODULE = "imio.emailkit.lint"

#: Lines of unified diff to show per stale file. Enough to see what changed,
#: little enough that twenty stale files still fit on a screen.
DIFF_LINES = 20

OK, STALE, MISSING, ORPHAN = "ok", "STALE", "MISSING", "ORPHAN"


def parser():
    parsed = cli.base_parser("check-emails", DESCRIPTION)
    parsed.add_argument(
        "--no-lint",
        action="store_true",
        help=(
            f"skip gate 2. Only for an environment where {LINT_MODULE} is not "
            "installed; a skipped gate protects nothing."
        ),
    )
    parsed.add_argument(
        "--lint-only",
        action="store_true",
        help="run gate 2 only. Needs no Node, so it is the cheap half.",
    )
    parsed.add_argument(
        "--diff-lines",
        type=int,
        default=DIFF_LINES,
        metavar="N",
        help=f"lines of diff to print per stale file (default {DIFF_LINES}).",
    )
    return parsed


def main(config=None, argv=None):
    arguments = parser().parse_args(argv)
    cli.configure_logging(arguments.verbose)
    merged = cli.settings(config, arguments)

    try:
        found, kit_dir = cli.discover(arguments, merged)
    except (projects_module.ProjectError, ImportError) as exc:
        return cli.report_error(exc)

    if arguments.list:
        cli.print_discovery(found, kit_dir, merged)
        return 0

    compilable = cli.nothing_to_do(found, "check")
    if not compilable:
        print(
            "Nothing to check. No package in this part's `eggs` ships a Maizzle "
            "project, so there are no sources to compare the committed output "
            "against."
        )
        return 0

    failed = []

    if not arguments.lint_only:
        print("==> gate 1: the committed build output is not stale")
        if staleness_gate(compilable, merged, kit_dir, arguments.diff_lines) != 0:
            failed.append("staleness")

    if not arguments.no_lint:
        print("\n==> gate 2: the authoring lint (SPEC §3 rules)")
        if lint_gate(compilable) != 0:
            failed.append("lint")
    else:
        print(f"\n==> gate 2: SKIPPED by --no-lint. {LINT_MODULE} was not run.")

    if failed:
        sys.stdout.flush()
        print(f"\ncheck-emails FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("\ncheck-emails passed.")
    return 0


# ---------------------------------------------------------------------------
# Gate 1 -- staleness
# ---------------------------------------------------------------------------


def staleness_gate(projects, merged, kit_dir, diff_lines=DIFF_LINES):
    try:
        _node, npm, npx = node_module.resolve(merged["node_bin"])
    except node_module.NodeError as exc:
        return cli.report_error(exc)

    stale = 0
    for project in projects:
        print(f"  {project.package}")
        try:
            stale += check_project(
                project,
                kit_dir=kit_dir,
                kit_mode=merged["kit_mode"],
                npm=npm,
                npx=npx,
                diff_lines=diff_lines,
            )
        except (kit_module.KitError, node_module.NodeError) as exc:
            print(f"    FAILED {exc}", file=sys.stderr)
            stale += 1
    if stale:
        # Flushed first: the per-file report went to stdout, which is buffered
        # whenever it is a pipe, and the summary goes to stderr, which is not.
        # Without this the summary jumps above the report it summarises.
        sys.stdout.flush()
        print(
            "\n  Committed email templates are stale. Run `bin/compile-emails` "
            "and commit the result.",
            file=sys.stderr,
        )
        return 1
    return 0


def check_project(project, kit_dir, kit_mode, npm, npx, diff_lines=DIFF_LINES):
    """Build in place, diff against the snapshot, restore. Return a problem count."""
    with tempfile.TemporaryDirectory(prefix="emailkit-check-") as tmp:
        snapshot = take_snapshot(project.package_dir, Path(tmp))
        try:
            compile_emails.compile_project(
                project, kit_dir=kit_dir, kit_mode=kit_mode, npm=npm, npx=npx
            )
            return report(project, snapshot, diff_lines)
        finally:
            restore_snapshot(project.package_dir, snapshot)


def take_snapshot(package_dir, destination):
    """Copy every committed ``.pt`` under ``package_dir`` into ``destination``.

    Every ``.pt``, not just ``templates/``: the build legitimately writes to more
    than one place -- ``imio.emailkit``'s own project also emits §8's jbot
    overrides under ``browser/overrides/``, addressed by dotted filename rather
    than by name -- and a gate that only watched one directory would have let the
    other go stale silently. Hand-written templates are swept up too, which is
    harmless: they are restored byte-identical, and :func:`report` only looks at
    directories the build actually wrote into.
    """
    package_dir = Path(package_dir)
    snapshot = {}
    for path in sorted(package_dir.rglob("*.pt")):
        if _inside_emails(package_dir, path):
            continue
        relative = path.relative_to(package_dir)
        copy = destination / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(path.read_bytes())
        snapshot[relative] = copy
    return snapshot


def _inside_emails(package_dir, path):
    """Skip the Maizzle project itself, if it happens to live inside the package."""
    return projects_module.EMAILS_DIRNAME in path.relative_to(package_dir).parts


def restore_snapshot(package_dir, snapshot):
    """Put the committed tree back exactly, including deleting what the build added.

    Anything matching ``*.pt`` that is present now and absent from the snapshot
    did not exist before this run, so removing it is what "restore" means. Doing
    it on a ``finally`` is deliberate.
    """
    package_dir = Path(package_dir)
    for relative, copy in snapshot.items():
        target = package_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(copy.read_bytes())
    for path in sorted(package_dir.rglob("*.pt")):
        if _inside_emails(package_dir, path):
            continue
        if path.relative_to(package_dir) not in snapshot:
            path.unlink()


def report(project, snapshot, diff_lines=DIFF_LINES):
    """Compare the fresh build against the snapshot; print per file; count problems."""
    package_dir = project.package_dir
    fresh = {
        path.relative_to(package_dir)
        for path in package_dir.rglob("*.pt")
        if not _inside_emails(package_dir, path)
    }
    built_dirs = _built_dirs(package_dir, snapshot, fresh)
    problems = 0
    checked = 0
    for relative in sorted(fresh | set(snapshot)):
        state, detail = _state(
            package_dir, relative, snapshot, fresh, built_dirs, diff_lines
        )
        if state is None:
            continue
        checked += 1
        if state != OK:
            problems += 1
        print(f"    {state:<9} {relative}")
        if detail:
            print(detail, end="")
    if not problems:
        print(f"    (all {checked} file(s) up to date)")
    return problems


def _built_dirs(package_dir, snapshot, fresh):
    """Directories the build actually wrote into.

    Only these are subject to the ORPHAN check, and only files inside them are
    reported at all. A directory of *hand-written* templates -- a browser view's
    ``.pt``, say -- is nobody's build output, and reporting it as "committed, no
    longer built" would be a false alarm on a file that is perfectly correct. §5's
    lint guidance applies to this gate too: prefer a missed case to a false alarm.
    """
    return {
        relative.parent
        for relative in fresh
        if relative not in snapshot
        or _touched(package_dir / relative, snapshot[relative])
    }


def _touched(current, copy):
    """Was ``current`` rewritten by the build? Compared by mtime, not content.

    A byte-identical rebuild is the *normal* case -- Phase 0 verified the build is
    deterministic -- so content cannot answer "did the build write this file".
    The mtime can: Maizzle empties its output directory and writes every file
    again, so anything it owns is newer than the snapshot copy taken moments
    before.
    """
    try:
        return current.stat().st_mtime_ns > copy.stat().st_mtime_ns
    except OSError:
        return False


def _state(package_dir, relative, snapshot, fresh, built_dirs, diff_lines=DIFF_LINES):
    """``(state, detail)`` for one path, or ``(None, None)`` when it is not ours."""
    committed = snapshot.get(relative)
    if relative not in fresh:
        if committed is None or relative.parent not in built_dirs:
            return None, None
        return ORPHAN, "               (committed, no longer built)\n"
    if relative.parent not in built_dirs:
        return None, None
    current = package_dir / relative
    if committed is None:
        return MISSING, "               (built, never committed)\n"
    if current.read_bytes() == committed.read_bytes():
        return OK, None
    return STALE, _diff(committed, current, diff_lines)


def _diff(committed, current, diff_lines=DIFF_LINES):
    lines = list(
        difflib.unified_diff(
            committed.read_text(encoding="utf-8", errors="replace").splitlines(True),
            current.read_text(encoding="utf-8", errors="replace").splitlines(True),
            fromfile="committed",
            tofile="fresh build",
            n=1,
        )
    )
    shown = "".join(f"      {line}" for line in lines[:diff_lines])
    if len(lines) > diff_lines:
        shown += f"      ... {len(lines) - diff_lines} more diff line(s)\n"
    return shown


# ---------------------------------------------------------------------------
# Gate 2 -- the authoring lint
# ---------------------------------------------------------------------------


def lint_gate(projects, module=LINT_MODULE, executable=None):
    """Run ``python -m imio.emailkit.lint`` over every ``.vue`` source.

    Delegated, not reimplemented. If the module is not importable the gate
    **fails**: SPEC §5 calls this "the CI gate", and a gate that quietly turns
    itself off when its implementation is missing is worse than no gate, because
    it reports success. ``--no-lint`` exists for the one case where that is a
    deliberate, visible choice.
    """
    executable = executable or sys.executable
    sources = []
    for project in projects:
        sources.extend(project.vue_sources())
    if not sources:
        print("  no .vue sources to lint.")
        return 0

    print(f"  linting {len(sources)} source(s) through `python -m {module}`")
    command = [executable, "-m", module, *[str(path) for path in sources]]
    environment = _child_environment()
    sys.stdout.flush()
    try:
        completed = subprocess.run(  # noqa: S603 - argv list
            command, check=False, env=environment
        )
    except OSError as exc:
        print(f"  FAILED could not run {module}: {exc}", file=sys.stderr)
        return 1
    if completed.returncode == 0:
        return 0
    # `python -m` exits 1 with "No module named ..." on stderr. Distinguishing it
    # from a genuine lint failure matters, because the fixes are unrelated.
    if not _module_importable(module, executable, environment):
        print(
            f"\n  {module} is not importable in this environment, so gate 2 could "
            f"not run.\n"
            f"  It ships in `imio.emailkit`; make sure the part's `eggs` resolves a "
            f"version that has it.\n"
            f"  Pass --no-lint to run gate 1 alone, deliberately and visibly.",
            file=sys.stderr,
        )
    return 1


def _child_environment():
    """This process's ``sys.path``, handed to the child through ``PYTHONPATH``.

    Not optional, and the reason is worth stating: a buildout-generated script
    gets its ``sys.path`` from lines *inside the script*, so ``sys.executable`` is
    an interpreter that knows nothing about the part's eggs. Without this, gate 2
    reported "No module named 'imio'" on a perfectly good installation --
    a configuration failure wearing a missing-dependency costume.
    """
    environment = dict(os.environ)
    inherited = environment.get("PYTHONPATH")
    entries = [entry for entry in sys.path if entry]
    if inherited:
        entries.append(inherited)
    environment["PYTHONPATH"] = os.pathsep.join(entries)
    return environment


def _module_importable(module, executable, environment=None):
    probe = subprocess.run(  # noqa: S603 - argv list
        [
            executable,
            "-c",
            "import importlib.util as u, sys; "
            f"sys.exit(0 if u.find_spec({module!r}) else 1)",
        ],
        check=False,
        capture_output=True,
        env=environment or _child_environment(),
    )
    return probe.returncode == 0
