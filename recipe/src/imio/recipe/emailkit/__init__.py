"""``imio.recipe.emailkit`` -- the buildout recipe.

    [emails]
    recipe = imio.recipe.emailkit
    eggs = ${instance:eggs}
    # compile-on-install = false   (default)
    # kit-mode = path | copy       (default: path)
    # node-bin = node

The recipe resolves the part's eggs, finds the packages whose ZCML
registers ``<emailkit:templates>``, resolves the design kit from the
``imio.emailkit`` egg, and generates three scripts.

It never compiles by default. With ``compile-on-install`` false, this
module never imports Node or the consumer's code; it only scans each
dist's ZCML on disk for the emailkit marker.
"""

from imio.recipe.emailkit import projects as projects_module

import logging


__version__ = "1.0.0b3.dev0"

logger = logging.getLogger("imio.recipe.emailkit")

#: The three scripts this recipe generates, as ``(script name, module, callable)``.
SCRIPTS = (
    ("compile-emails", "imio.recipe.emailkit.compile_emails", "main"),
    ("check-emails", "imio.recipe.emailkit.check_emails", "main"),
    ("preview-emails", "imio.recipe.emailkit.preview_emails", "main"),
)

#: An extra requirement, so it lands on the generated scripts' own path.
SELF = "imio.recipe.emailkit"

DEFAULTS = {
    # Spelled out so `.installed.cfg` and `buildout -v` show what is in force.
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
                f"{options['kit-mode']!r}."
            )
        # `eggs` defaults to the part name, which would try to resolve a
        # distribution named after the part. Fail loud instead.
        if not options.get("eggs", "").strip():
            raise user_error(
                f"[{name}] needs an `eggs` option naming the distributions to "
                f"scan for `emailkit:templates` ZCML registrations. "
                f"For example: `eggs = ${{instance:eggs}}`."
            )
        # Imported here so a missing zc.recipe.egg names this part.
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
            # Opt-in only; reached when Node is accepted at deploy time.
            self._compile(found, kit_dir)

        return generated

    # Generating scripts is all this part does, so update reruns install.
    update = install

    # -- pieces -----------------------------------------------------------

    def _record(self, found, kit_dir):
        """Write the discovery record to the log and to ``.installed.cfg``.

        Answers "which packages ship templates" without rerunning anything.
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
                "%s: no distribution in `eggs` registers `<emailkit:templates>` "
                "in its ZCML, so the generated scripts will have nothing to do. "
                "Is `eggs` right?",
                self.name,
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

        Only settings are baked in. A develop checkout changes between
        buildout runs, so the scripts rediscover packages each run.
        """
        config = {
            "kit_mode": self.options["kit-mode"],
            "kit_dir": str(kit_dir),
            "node_bin": self.options["node-bin"],
            "part": self.name,
        }
        return f"config={config!r}"

    def _compile(self, found, kit_dir):
        """``compile-on-install = true``. Opt-in; never the default."""
        # Imported here so a default run never loads the module that spawns npm.
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
            "This is opt-in for a reason; a deployment that cannot "
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

    An unrecognised value is an error, not a silent false.
    """
    value = str(options.get("compile-on-install", "false")).strip().lower()
    if value in ("true", "yes", "on", "1"):
        return True
    if value in ("false", "no", "off", "0", ""):
        return False
    raise user_error(
        f"compile-on-install must be a boolean, not {value!r}. It defaults to "
        f"false, and it must stay false unless a deployment "
        f"deliberately accepts Node at deploy time."
    )


def user_error(message):
    """A configuration mistake, raised as the error buildout prints without a traceback.

    ``zc.buildout`` is imported lazily, since the generated scripts import
    this module too and must not need buildout on their path.
    """
    try:
        from zc.buildout import UserError
    except ImportError:  # pragma: no cover - buildout is a hard dependency
        return RuntimeError(message)
    return UserError(message)
