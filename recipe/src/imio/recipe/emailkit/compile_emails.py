"""``bin/compile-emails``.

    bin/compile-emails [--package NAME] [--watch] [--new NAME]

For each package: wire the kit, run ``npm ci`` if ``node_modules`` is
stale, run ``npx maizzle build``, then copy the hand-authored twins back
in. Exits non-zero on any build failure.

Maizzle writes ``.pt`` directly into ``templates/``, so no rename step
is needed. Twins are copied back because the build empties its output
directory.

``--watch`` delegates to Maizzle's dev server, which shows raw,
unrendered placeholders. Use ``bin/preview-emails --watch`` instead.
"""

from imio.recipe.emailkit import cli
from imio.recipe.emailkit import kit as kit_module
from imio.recipe.emailkit import node as node_module
from imio.recipe.emailkit import projects as projects_module
from imio.recipe.emailkit import scaffold as scaffold_module

import shutil
import sys


DESCRIPTION = (
    "Compile a package's Maizzle sources into the committed `.pt` templates that "
    "production renders. Node is a developer tool: this script is the only thing "
    "that invokes it, and buildout never runs this script by default."
)


def parser():
    parsed = cli.base_parser("compile-emails", DESCRIPTION)
    parsed.add_argument(
        "--watch",
        action="store_true",
        help=(
            "delegate to Maizzle's dev server. Shows BUILD-TIME output -- raw "
            "${...} placeholders and unexpanded tal:repeat. Use "
            "`preview-emails --watch` for the loop that renders through render()."
        ),
    )
    parsed.add_argument(
        "--new",
        metavar="NAME",
        default=None,
        help=(
            "scaffold a new template (a .vue skeleton, a fixture, a golden "
            "placeholder and a registration stub) instead of building."
        ),
    )
    parsed.add_argument(
        "--force",
        action="store_true",
        help="with --new, overwrite files that already exist.",
    )
    parsed.add_argument(
        "--reinstall",
        action="store_true",
        help="run `npm ci` even when node_modules matches the lockfile.",
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

    if arguments.new:
        return scaffold(found, arguments)

    compilable = cli.nothing_to_do(found, "compile")
    if not compilable:
        print(
            "Nothing to compile. No package in this part's `eggs` ships a Maizzle "
            "project."
        )
        return 0

    if arguments.watch and len(compilable) > 1:
        return cli.report_error(
            "--watch runs one dev server, so it needs --package NAME. "
            f"Candidates: {', '.join(p.package for p in compilable)}."
        )

    try:
        _node, npm, npx = node_module.resolve(merged["node_bin"])
    except node_module.NodeError as exc:
        return cli.report_error(exc)

    failures = []
    for project in compilable:
        print(f"==> {project.package}")
        try:
            compile_project(
                project,
                kit_dir=kit_dir,
                kit_mode=merged["kit_mode"],
                npm=npm,
                npx=npx,
                watch=arguments.watch,
                reinstall=arguments.reinstall,
            )
        except (kit_module.KitError, node_module.NodeError) as exc:
            print(f"  FAILED {project.package}: {exc}", file=sys.stderr)
            failures.append(project.package)

    if failures:
        # Every package is attempted first, so one failure does not hide others.
        print(
            f"\ncompile-emails failed for: {', '.join(failures)}",
            file=sys.stderr,
        )
        return 1
    print("\nDone. Commit the `.pt` files -- they are what production renders.")
    return 0


def compile_project(project, kit_dir, kit_mode, npm, npx, watch=False, reinstall=False):
    """Wire, install, build, and copy the twins back in. In that order."""
    kit_module.wire(project, kit_dir, kit_mode)
    node_module.ensure_dependencies(project.emails_dir, npm, force=reinstall)
    project.templates_dir.mkdir(parents=True, exist_ok=True)
    node_module.build(project.emails_dir, npx, watch=watch)
    if not watch:
        copy_twins(project)


def copy_twins(project):
    """Copy ``emails/twins/*.txt.pt`` into the templates directory.

    ``maizzle build`` empties its output directory, so twins live outside
    the build's reach and are copied back in after every build.
    """
    twins = project.twins_dir
    if twins is None or not twins.is_dir():
        return []
    copied = []
    for twin in sorted(twins.glob("*.txt.pt")):
        shutil.copy2(twin, project.templates_dir / twin.name)
        copied.append(twin.name)
    if copied:
        print(f"  twins     copied {len(copied)}: {', '.join(copied)}")
    return copied


def scaffold(found, arguments):
    """``--new NAME``. Needs exactly one package to put the files in."""
    if len(found) > 1:
        return cli.report_error(
            "--new writes into one package, so it needs --package NAME. "
            f"Candidates: {', '.join(project.package for project in found)}."
        )
    project = found[0]
    try:
        paths = scaffold_module.new_template(
            project, arguments.new, force=arguments.force
        )
    except scaffold_module.ScaffoldError as exc:
        return cli.report_error(exc)
    print(scaffold_module.next_steps(project, arguments.new, paths))
    print("--- registration stub (also written beside the .vue source) ---")
    print(scaffold_module.registration_stub(project, arguments.new))
    return 0
