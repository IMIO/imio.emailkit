"""``imio.recipe.emailkit`` -- the buildout recipe of SPEC §5.

    [emails]
    recipe = imio.recipe.emailkit
    eggs = ${instance:eggs}
    # compile-on-install = false   (default)
    # kit-mode = path | copy       (default: path)
    # node-bin = node

What it does, per §5: resolves the part's eggs, collects the distributions that
expose the ``imio.emailkit.templates`` entry point, records
``(package, emails_dir, templates_dir)`` for each, resolves the design kit from the
``imio.emailkit`` egg, and generates three scripts.

**What it does not do, and must never do by default: compile.** §5's "Explicitly
rejected" section is unambiguous -- "compiling at buildout time by default ... would
make Node a production dependency across ~350 applications and couple deployments
to npm availability". So ``compile-on-install`` defaults to false, and with that
default this module imports nothing that knows Node exists, touches no ``emails/``
directory, and runs no subprocess. It does not even *import* the consumer's code:
discovery at install time reads ``pkg_resources`` metadata and the filesystem only,
so a buildout run stays a buildout run.
"""

from imio.recipe.emailkit import projects as projects_module

import logging


__version__ = "1.0.0a0"

logger = logging.getLogger("imio.recipe.emailkit")

#: The three scripts of §5, as ``(script name, module, callable)``.
SCRIPTS = (
    ("compile-emails", "imio.recipe.emailkit.compile_emails", "main"),
    ("check-emails", "imio.recipe.emailkit.check_emails", "main"),
    ("preview-emails", "imio.recipe.emailkit.preview_emails", "main"),
)

#: This distribution has to be on the generated scripts' own path: they *are* its
#: entry points. Requested as an extra requirement rather than assumed to be in
#: the part's ``eggs``, which a consumer's ``${instance:eggs}`` has no reason to
#: mention.
SELF = "imio.recipe.emailkit"

DEFAULTS = {
    # SPEC §5's defaults, spelled out so `.installed.cfg` records them and a
    # `buildout -v` run shows what is in force.
    "compile-on-install": "false",
    "kit-mode": "path",
    "node-bin": "node",
}


class Recipe:
    """The ``imio.recipe.emailkit`` part."""

    def __init__(self, buildout, name, options):
        self.buildout = buildout
        self.name = name
        self.options = options
        for key, value in DEFAULTS.items():
            options.setdefault(key, value)
        if options["kit-mode"] not in ("path", "copy"):
            raise user_error(
                f"[{name}] kit-mode must be `path` or `copy`, not "
                f"{options['kit-mode']!r} (SPEC §5)."
            )
        # `eggs` defaults to the part name in zc.recipe.egg, which for a part
        # called `emails` would try to resolve a distribution named `emails`. An
        # empty default and an explicit error is a much better failure.
        if not options.get("eggs", "").strip():
            raise user_error(
                f"[{name}] needs an `eggs` option naming the distributions to "
                f"scan for the {projects_module.ENTRY_POINT_GROUP} entry point. "
                f"SPEC §5's example is `eggs = ${{instance:eggs}}`."
            )
        # Imported here rather than at module scope so that the import error, if
        # zc.recipe.egg is somehow absent, names this part.
        import zc.recipe.egg

        self.egg = zc.recipe.egg.Egg(buildout, name, options)

    def install(self):
        requirements, working_set = self.egg.working_set([SELF])
        del requirements

        found = projects_module.from_working_set(working_set)
        kit_dir = projects_module.kit_dir_from_working_set(working_set)
        self._record(found, kit_dir)

        generated = list(self._scripts(working_set, kit_dir))

        if compile_on_install(self.options):
            # Opt-in, never the default (§5 step 3). Reached only when the
            # deployment has explicitly said it accepts Node at deploy time.
            self._compile(found, kit_dir)

        return generated

    # A part that only generates scripts has nothing to migrate, and the paths it
    # writes are derived from options buildout has already compared. Rerunning
    # install on update keeps the scripts in step with a changed `eggs` list.
    update = install

    # -- pieces -----------------------------------------------------------

    def _record(self, found, kit_dir):
        """SPEC §5 step 1's record, in the log and in ``.installed.cfg``.

        Written into the options so ``.installed.cfg`` carries it: when a mail
        turns out to be missing in production, "which packages did this buildout
        think ship templates" is the first question, and it should be answerable
        without rerunning anything.
        """
        self.options["kit-directory"] = str(kit_dir)
        self.options["packages"] = "\n".join(project.package for project in found)
        self.options["templates-directories"] = "\n".join(
            f"{project.package} = {project.templates_dir}" for project in found
        )
        self.options["emails-directories"] = "\n".join(
            f"{project.package} = {project.emails_dir}"
            for project in found
            if project.compilable
        )
        logger.info(
            "%s: kit at %s (kit-mode = %s)",
            self.name,
            kit_dir,
            self.options["kit-mode"],
        )
        if not found:
            logger.warning(
                "%s: no distribution in `eggs` exposes the %s entry point, so the "
                "generated scripts will have nothing to do. Is `eggs` right?",
                self.name,
                projects_module.ENTRY_POINT_GROUP,
            )
        for project in found:
            logger.info("%s:   %s", self.name, project.describe())

    def _scripts(self, working_set, kit_dir):
        """Generate the three scripts, each with the part's settings baked in."""
        import sys
        import zc.buildout.easy_install

        arguments = self._arguments(kit_dir)
        for script, module, attribute in SCRIPTS:
            yield from zc.buildout.easy_install.scripts(
                [(script, module, attribute)],
                working_set,
                sys.executable,
                self.buildout["buildout"]["bin-directory"],
                arguments=arguments,
                initialization=self.options.get("initialization", ""),
                extra_paths=getattr(self.egg, "extra_paths", ()),
            )

    def _arguments(self, kit_dir):
        """The ``config=`` literal the generated scripts are called with.

        Only *settings* are baked in, never the discovered package list: a develop
        checkout changes between buildout runs, so the scripts rediscover at run
        time. Baking in a stale list would be wrong in exactly the way nobody
        notices.
        """
        config = {
            "kit_mode": self.options["kit-mode"],
            "kit_dir": str(kit_dir),
            "node_bin": self.options["node-bin"],
            "part": self.name,
        }
        return f"config={config!r}"

    def _compile(self, found, kit_dir):
        """``compile-on-install = true``. Opt-in; §5 makes it never the default."""
        # Imported *here*, inside the opt-in branch, so that a default buildout
        # run never even loads the module that knows how to spawn npm.
        from imio.recipe.emailkit import compile_emails
        from imio.recipe.emailkit import node as node_module

        compilable = [project for project in found if project.compilable]
        if not compilable:
            logger.info(
                "%s: compile-on-install is true but no package ships an `emails/` "
                "directory, so there is nothing to compile.",
                self.name,
            )
            return
        logger.warning(
            "%s: compile-on-install = true, so buildout is about to run Node. "
            "SPEC §5 makes this opt-in for a reason; a deployment that cannot "
            "guarantee npm availability should leave it false.",
            self.name,
        )
        _node, npm, npx = node_module.resolve(self.options["node-bin"])
        for project in compilable:
            compile_emails.compile_project(
                project,
                kit_dir=kit_dir,
                kit_mode=self.options["kit-mode"],
                npm=npm,
                npx=npx,
            )


def compile_on_install(options):
    """Read ``compile-on-install`` the way buildout reads a boolean.

    Anything but a recognised true value is false, and an unrecognised value is an
    error rather than a silent false: "compile-on-install = yes" quietly meaning
    "no" is the kind of thing that gets discovered in production.
    """
    value = str(options.get("compile-on-install", "false")).strip().lower()
    if value in ("true", "yes", "on", "1"):
        return True
    if value in ("false", "no", "off", "0", ""):
        return False
    raise user_error(
        f"compile-on-install must be a boolean, not {value!r}. It defaults to "
        f"false, and SPEC §5 requires that it stay false unless a deployment "
        f"deliberately accepts Node at deploy time."
    )


def user_error(message):
    """A configuration mistake, raised as the error buildout prints tracebackless.

    ``zc.buildout`` is imported lazily so that this module -- which the three
    generated scripts import on their way to their own entry points -- does not
    drag buildout onto *their* import path. They run in the part's ``eggs``, not
    in the buildout interpreter, and a build tool has no business needing the
    build system.
    """
    try:
        from zc.buildout import UserError
    except ImportError:  # pragma: no cover - buildout is a hard dependency
        return RuntimeError(message)
    return UserError(message)
