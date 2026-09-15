"""``bin/preview-emails`` (SPEC §5) -- the two-stage dev loop.

    bin/preview-emails [--package NAME] [--watch]

§5, verbatim: "The two-stage dev loop -- the flagship DX feature. Maizzle's own
``--watch`` shows *build-time* output: raw ``${item/title}`` placeholders and
unexpanded ``tal:repeat`` -- a miserable authoring loop. This script watches the
``.vue`` sources, compiles, pipes the result through Chameleon (``render()``)
**with the committed fixtures (§7)**, and serves the result with live reload and a
language switcher."

This is ``scripts/preview_emails.py`` generalised, per §9's sequencing note: same
steps, no hardcoded paths, and one thing the precursor could not do.

**The precursor needed a ZODB connection, and this does not.** That was recorded as
the reason live reload was deferred ("wiring a watcher to a process that has to
hold a ZODB connection open is the part with real design in it"). Measured while
building this: ``render()`` is a pure function of (template, context, registry
state) exactly as §6.1 claims, so a minimal ZCML load -- ``Products.PageTemplates``
for the ``IPageTemplateEngine`` utility, plus each package's translation catalogs
-- is enough to render with real placeholder substitution and real FR/NL/DE
translations. No ``zope.conf``, no database, no site. The watcher is therefore an
ordinary polling loop, and live reload is ~30 lines.

What is *not* real without a site, stated plainly rather than left to be
discovered: the §3 theme tokens come from :class:`IEmailkitTheme`'s own defaults
(seeded into an in-memory registry) rather than from a site's
``plone.app.registry``. ``--theme token=value`` overrides them, which is the §6.3
token panel in its command-line form. For a preview against a *real* site's
branding, use ``@@emailkit-preview`` (§6.3) -- that is what it is for.

``portal_url`` **is** real, and has to be. It is what the kit shell builds
``asset_base`` from, and every image in the design is gated on that being
non-empty -- the header logo, the status pill's icon, the footer mark, and the
Quicksand stylesheet. Left to its site-less default the preview rendered all four
as *nothing at all*: not broken images, no markup, no warning, just a design
missing the parts that make it recognisable. So this server points ``portal_url``
at itself (:func:`seed_portal_url`) and answers ``++resource++`` urls out of each
package's ``browser/static`` (:func:`read_resource`).
"""

from imio.recipe.emailkit import cli
from imio.recipe.emailkit import compile_emails
from imio.recipe.emailkit import kit as kit_module
from imio.recipe.emailkit import node as node_module
from imio.recipe.emailkit import projects as projects_module
from pathlib import Path

import functools
import html as html_module
import importlib.util
import json
import logging
import sys
import threading


logger = logging.getLogger("imio.recipe.emailkit")

DESCRIPTION = (
    "Render every registered template with its committed fixture and serve the "
    "result, with a language switcher and live reload. What you look at is what "
    "render() produces, not what Maizzle emits."
)

DEFAULT_LANGUAGES = ("fr", "nl", "en")
DEFAULT_PORT = 8090
DEFAULT_HOST = "127.0.0.1"

#: Where the rendered previews are written when ``--output`` is not given. Under
#: the checkout's ``var/`` because that is already gitignored everywhere in this
#: ecosystem, and because a preview is a throwaway artifact.
DEFAULT_OUTPUT = Path("var") / "preview"

#: Polled by the browser; bumped by every re-render.
VERSION_PATH = "/__emailkit/version"

#: Where the preview server answers the urls the kit shell builds from
#: ``asset_base``. Matches Zope's own traversal spelling, so the rendered html is
#: byte-identical to what a site would produce apart from the host.
RESOURCE_PREFIX = "/++resource++"

WATCH_INTERVAL = 0.6


class NotShipped(str):
    """A row note that is a plain fact rather than a failure.

    An installed egg prunes both ``emails/`` and ``tests/`` (SPEC §4's
    ``MANIFEST.in``), so the fixture §7 asks for cannot be there and no consumer
    buildout could put it there: it lives in that package's own checkout.
    ``@@emailkit-preview`` already reports that absence as a fact rather than an
    error (§6.3); this is the same judgement in the command line's vocabulary.

    A ``str`` subclass so every consumer of a row keeps working unchanged, and
    distinguished by *type* rather than by matching the message, so
    :func:`report` can never mistake one for the other.
    """

    #: The same fact in the few words a sidebar entry has room for. The full
    #: string is the terminal line, where there is room to say where the fixture
    #: does live and why it is not here.
    short = "no fixture (installed egg) -- the .pt part still opens"


def parser():
    parsed = cli.base_parser("preview-emails", DESCRIPTION)
    parsed.add_argument(
        "--watch",
        action="store_true",
        help="recompile and re-render whenever a source or a fixture changes.",
    )
    parsed.add_argument(
        "--no-compile",
        action="store_true",
        help=(
            "render the committed `.pt` as they are, without running Maizzle. "
            "Needs no Node, and shows exactly what is in git."
        ),
    )
    parsed.add_argument(
        "--languages",
        metavar="fr,nl,en",
        default=",".join(DEFAULT_LANGUAGES),
        help="comma-separated languages to render.",
    )
    parsed.add_argument("--port", type=int, default=DEFAULT_PORT)
    parsed.add_argument("--host", default=DEFAULT_HOST)
    parsed.add_argument(
        "--no-serve",
        action="store_true",
        help="write the previews and exit. For CI, which wants the exit code only.",
    )
    parsed.add_argument(
        "--output",
        metavar="DIR",
        default=None,
        help=f"where to write the previews (default: <checkout>/{DEFAULT_OUTPUT}).",
    )
    parsed.add_argument(
        "--theme",
        metavar="TOKEN=VALUE",
        action="append",
        default=[],
        help="override a §3 theme token, e.g. --theme primary_color=#e6007e.",
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

    languages = [
        part.strip() for part in arguments.languages.split(",") if part.strip()
    ]
    output = Path(arguments.output) if arguments.output else _default_output()
    output.mkdir(parents=True, exist_ok=True)

    base_url = f"http://{arguments.host}:{arguments.port}"
    try:
        configure(found)
        seed_theme(_theme_overrides(arguments.theme))
        seed_portal_url(base_url)
    except Exception as exc:
        return cli.report_error(f"{type(exc).__name__}: {exc}")

    state = {"generation": 0, "resources": resource_dirs(found)}

    def pass_once():
        if not arguments.no_compile and compile_all(found, kit_dir, merged) != 0:
            return 1
        rows = render_all(found, languages, output)
        state["generation"] += 1
        write_index(rows, output, languages, state["generation"], watch=arguments.watch)
        return report(rows, output)

    status = pass_once()

    if arguments.no_serve:
        return status

    stop = threading.Event()
    if arguments.watch:
        threading.Thread(
            target=watch_loop,
            args=(found, pass_once, stop),
            daemon=True,
        ).start()
    try:
        serve(output, arguments.host, arguments.port, state)
    finally:
        stop.set()
    return status


def seed_portal_url(base_url):
    """Make ``render()`` build ``asset_base`` against this server.

    ``render()`` injects ``portal_url`` itself, from ``getSite()`` and a REQUEST,
    and an injected name beats anything the caller puts in the context -- so a
    preview cannot supply one by passing it in. It stands in for the site here the
    same way :func:`seed_theme` stands in for ``plone.app.registry``: by replacing
    the function the render reads.

    Without this every image in the mail is *absent*, not broken. The kit gates
    each one on ``tal:condition="asset_base"`` precisely so a render with no
    request degrades to no image rather than to a broken-image icon -- correct for
    a golden file, and the wrong thing entirely for the tool whose whole job is
    showing you what the mail looks like. The header logo, the status pill's icon,
    the footer mark and the Quicksand stylesheet all hang off it, which is most of
    what makes the design recognisable.

    Paired with :func:`resource_dirs` and the handler's ``++resource++`` route,
    which is what actually serves the bytes.

    ``import_module`` and not ``from imio.emailkit import render``: §6.1 spells the
    public API as the latter, so ``imio/emailkit/__init__.py`` rebinds the name to
    the ``render`` FUNCTION and shadows the submodule of the same name. Written the
    obvious way this assigns an unused attribute to a function object, patches
    nothing, and the preview goes on silently dropping every image -- which is how
    it was found.
    """
    try:
        render_module = importlib.import_module("imio.emailkit.render")
    except ImportError as exc:
        logger.warning(
            "Not seeding portal_url (%s). Images and web fonts will be missing "
            "from the preview.",
            exc,
        )
        return None
    render_module.portal_url = lambda: base_url
    return base_url


def resource_dirs(projects):
    """``{resource_name: directory}`` for every project shipping ``browser/static``.

    The convention, and it is a convention rather than a lookup: a package's
    ``browser:resourceDirectory`` is registered under the package's own dotted
    name, so ``imio.emailkit`` serves at ``++resource++imio.emailkit``. Reading the
    real name would mean parsing each package's ZCML for a directive this tool has
    no other reason to care about; a consumer that names its directory something
    else gets no images in the *preview* and is otherwise unaffected.
    """
    found = {}
    for project in projects:
        static = project.package_dir / "browser" / "static"
        if static.is_dir():
            found[project.package] = static
    return found


def _default_output():
    """``./var/preview``.

    The working directory, not any package's own tree: a preview belongs to the
    person running the script, not to whichever addon happened to sort first. Run
    from a buildout root -- which is where ``bin/preview-emails`` lives -- that is
    the ``var/`` every iMio checkout already gitignores.
    """
    return Path.cwd() / DEFAULT_OUTPUT


# ---------------------------------------------------------------------------
# Just enough Zope for render() to be truthful
# ---------------------------------------------------------------------------

_configured = False


def configure(projects):
    """Load the minimum ZCML ``render()`` needs, once per process.

    ``Products.PageTemplates`` is not optional and not a detail. It registers the
    ``IPageTemplateEngine`` utility; without it ``zope.pagetemplate`` falls back to
    ``zope.tal``, where ``${...}`` passes through **verbatim and with no error**
    (``docs/DECISIONS.md``). A preview built on that fallback would render raw
    placeholders and look like a template bug. :func:`render_all` asserts on the
    output for the same reason.
    """
    global _configured
    if _configured:
        return
    from zope.configuration import xmlconfig

    catalogs = "\n".join(
        f'  <configure package="{package}">'
        f'<i18n:registerTranslations directory="locales" /></configure>'
        for package in sorted(_packages_with_catalogs(projects))
    )
    registry = (
        '  <include package="plone.registry" />\n'
        if _importable("plone.registry")
        else ""
    )
    xmlconfig.string(
        '<configure xmlns="http://namespaces.zope.org/zope"\n'
        '           xmlns:i18n="http://namespaces.zope.org/i18n">\n'
        '  <include package="Products.PageTemplates" />\n'
        '  <include package="zope.i18n" file="meta.zcml" />\n'
        # `plone.registry` is included for its *field* adapters: without them
        # `Registry.registerInterface` raises "There is no persistent field
        # equivalent for the field ...", so the theme tokens could not be seeded
        # and the preview would render an unbranded shell.
        f"{registry}"
        f"{catalogs}\n"
        "</configure>\n"
    )
    _configured = True


def _packages_with_catalogs(projects):
    """Packages that ship a ``locales/`` directory, plus ``imio.emailkit`` itself.

    ``imio.emailkit`` is always included because the kit layout's own strings --
    the footer, the logo ``alt``, ``email_regards`` -- are in its domain and appear
    in *every* consumer's mail.
    """
    packages = {"imio.emailkit"}
    for project in projects:
        if (project.package_dir / "locales").is_dir():
            packages.add(project.package)
    return {package for package in packages if _importable(package)}


def _importable(package):
    try:
        return importlib.util.find_spec(package) is not None
    except (ImportError, ValueError):
        return False


def seed_theme(overrides):
    """Register an in-memory ``plone.app.registry`` holding the §3 theme tokens.

    Without a registry, ``render()``'s ``get_theme()`` collapses every token to the
    empty string, so a preview would show an unbranded shell and an empty
    ``primary_color`` where a colour belongs. Seeding from
    :class:`IEmailkitTheme`'s own field defaults is exactly what
    ``profiles/base/registry/main.xml`` does at install time, so the preview shows
    the same thing a freshly installed site would.
    """
    try:
        from imio.emailkit.interfaces import IEmailkitTheme
        from imio.emailkit.interfaces import THEME_REGISTRY_PREFIX
        from plone.registry import Registry
        from plone.registry.interfaces import IRegistry
        from zope.component import provideUtility
    except ImportError as exc:
        logger.warning(
            "Not seeding the theme tokens (%s). The preview will render with empty "
            "branding values.",
            exc,
        )
        return None
    registry = Registry()
    registry.registerInterface(IEmailkitTheme, prefix=THEME_REGISTRY_PREFIX)
    for token, value in overrides.items():
        record = f"{THEME_REGISTRY_PREFIX}.{token}"
        if record not in registry.records:
            raise ValueError(
                f"{token!r} is not a theme token. Known: "
                f"{', '.join(sorted(IEmailkitTheme.names()))}."
            )
        registry[record] = value
    provideUtility(registry, IRegistry)
    return registry


def _theme_overrides(pairs):
    overrides = {}
    for pair in pairs:
        token, _, value = pair.partition("=")
        if not _:
            raise SystemExit(f"--theme expects TOKEN=VALUE, got {pair!r}")
        overrides[token.strip()] = value
    return overrides


# ---------------------------------------------------------------------------
# Compile, then render
# ---------------------------------------------------------------------------


def compile_all(projects, kit_dir, merged):
    compilable = [project for project in projects if project.compilable]
    if not compilable:
        logger.info("nothing to compile; rendering the committed templates.")
        return 0
    try:
        _node, npm, npx = node_module.resolve(merged["node_bin"])
    except node_module.NodeError as exc:
        return cli.report_error(exc)
    for project in compilable:
        try:
            compile_emails.compile_project(
                project,
                kit_dir=kit_dir,
                kit_mode=merged["kit_mode"],
                npm=npm,
                npx=npx,
            )
        except (kit_module.KitError, node_module.NodeError) as exc:
            return cli.report_error(exc)
    return 0


def render_all(projects, languages, output):
    """Render every registered template of ``projects`` in every language.

    Returns a list of ``(name, language, error)`` rows, ``error`` being ``None`` on
    success. Discovery is rescanned and the compiled-template cache invalidated
    first, so a template added or rebuilt since the last pass is picked up.
    """
    from imio.emailkit import discovery
    from imio.emailkit import scan

    # `imio.emailkit.__init__` rebinds the name `render` on the package to the
    # *function*, so `import imio.emailkit.render` yields the function too. The
    # module is only reachable through a `from ... import <name>`.
    from imio.emailkit.render import invalidate_cache as forget_templates

    # Rescan rather than trust an earlier pass: a template added or rebuilt
    # since then must show up, and the scan is cheap. `forget_templates()` is
    # render()'s own Chameleon compile cache -- unrelated to discovery, and
    # still needed so a rebuilt .pt is recompiled rather than served stale.
    #
    # The global `discovery.reset()` followed by a rescan scoped to `projects`
    # is only safe because templates are self-contained: nothing a template
    # renders ever looks up another package's registration mid-render. If a
    # future feature needs cross-package template lookups, this reset has to
    # be revisited -- it would blow away another package's registrations for
    # the duration of this pass.
    discovery.reset()
    for project in projects:
        try:
            scan.scan_package(project.package)
        except Exception as exc:
            logger.warning("rescan of %s failed: %s", project.package, exc)
    forget_templates()

    wanted = {project.package: project for project in projects}
    rows = []
    for name, template in sorted(discovery.get_templates().items()):
        project = wanted.get(template.package)
        if project is None:
            continue
        # Before the fixture check, deliberately: this is the one artifact that
        # cannot fail for lack of one, and a template whose fixture is missing is
        # exactly the template you want it for.
        _write_source(name, template, output)
        fixture = find_fixture(project, template.basename)
        if fixture is None:
            rows.append((name, None, _no_fixture(project, template.basename)))
            continue
        try:
            context = load_fixture(fixture)
        except Exception as exc:
            rows.append((name, None, f"{fixture}: {type(exc).__name__}: {exc}"))
            continue
        for language in languages:
            rows.append(_render_one(name, dict(context), language, output))
    return rows


def _write_source(name, template, output):
    """Copy the compiled ``.pt`` in beside the rendered mails, as ``<stem>.pt.html``.

    The third part the page offers, and the only one that needs no fixture,
    because it is the file itself. Nothing is substituted: ``${item/title}``
    stands where its value would be and every ``tal:condition`` branch shows at
    once.

    **This is the build-time output §5 threw out, and that is deliberate.** §5's
    objection to ``maizzle --watch`` is to an authoring loop whose *only* output
    is unsubstituted markup -- one you can work in all day without ever learning
    that ``${item/created}`` renders nothing. Here it is one labelled part of
    three, next to the two that do render, and it is never substituted for them:
    a template with no fixture still reports FAILED and still exits non-zero. It
    answers "what does this layout look like"; the parts beside it answer "does
    this template render", which is the question §5 is protecting.

    One file per template rather than one per language: there is no render, so
    there is nothing for a language to change.
    """
    from imio.emailkit.render import resolved_path

    stem = name.replace(":", ".")
    path = resolved_path(template.html_path)
    try:
        markup = path.read_text(encoding="utf-8")
    except OSError as exc:
        markup = f"<pre>Could not read {html_module.escape(str(path))}: {exc}</pre>"
    (output / f"{stem}.pt.html").write_text(markup, encoding="utf-8")


def _render_one(name, context, language, output):
    from imio.emailkit import render as render_function

    stem = f"{name.replace(':', '.')}.{language}"
    try:
        html, text = render_function(name, context=context, language=language)
    except Exception as exc:
        return (name, language, f"{type(exc).__name__}: {exc}")
    if "${" in html:
        # The zope.tal fallback engine passes ${...} through verbatim and raises
        # nothing, so a preview that did not check this would quietly show a
        # template bug that is really a configuration bug.
        return (
            name,
            language,
            "unsubstituted ${...} in the output: the page-template engine is not "
            "the Chameleon one (see docs/DECISIONS.md)",
        )
    (output / f"{stem}.html").write_text(html, encoding="utf-8")
    (output / f"{stem}.txt").write_text(text, encoding="utf-8")
    return (name, language, None)


def _no_fixture(project, basename):
    """Why there is no fixture for ``basename``, as a failure or as a fact.

    A package that ships neither ``emails/`` nor ``tests/`` is an installed egg
    whose sdist pruned both (§4). Its fixtures are in its own checkout and
    nothing here can conjure them, so reporting FAILED would be telling the
    person running the preview to fix something that is not theirs -- and would
    exit non-zero on a buildout that is working exactly as intended.

    Anywhere else -- any checkout, which is where this script is meant to run --
    a missing fixture is the omission §7 wants caught, and still fails.
    """
    wanted = project.tests_dir / "fixtures" / f"{basename}.py"
    if project.emails_dir is None and not project.tests_dir.is_dir():
        return NotShipped(
            f"no fixture, and none possible: {project.package} is installed as an "
            f"egg, whose sdist prunes tests/ (SPEC §4). Its fixtures live in its "
            f"own checkout. The .pt part below needs none."
        )
    return f"no fixture; SPEC §7 wants one at {wanted}"


def find_fixture(project, basename):
    """``<tests>/fixtures/<basename>.py``, per SPEC §7, or ``None``."""
    candidates = [project.tests_dir / "fixtures" / f"{basename}.py"]
    if project.root is not None:
        candidates.append(project.root / "tests" / "fixtures" / f"{basename}.py")
    candidates.append(project.package_dir / "tests" / "fixtures" / f"{basename}.py")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_fixture(path):
    """The ``CONTEXT`` dict of a fixture module, loaded **by path**.

    By path rather than by import, so ``tests/fixtures/`` stays a directory of data
    files -- which is what §7 describes -- and so the preview and the golden test
    can never disagree about what the fixture says.
    """
    spec = importlib.util.spec_from_file_location(
        f"_emailkit_fixture_{path.stem}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = getattr(module, "CONTEXT", None)
    if not isinstance(context, dict):
        raise ValueError("a fixture module must define a dict named CONTEXT (SPEC §7)")
    return context


def report(rows, output):
    notes = [row for row in rows if isinstance(row[2], NotShipped)]
    failures = [row for row in rows if row[2] and not isinstance(row[2], NotShipped)]
    rendered = len(rows) - len(failures) - len(notes)
    print(f"\nrendered {rendered} preview(s) into {output}")
    # Reported on stdout and never silently: a template the preview could not
    # render is worth a line even when nobody is at fault for it.
    for name, _language, note in notes:
        print(f"  skip   {name}: {note}")
    for name, language, error in failures:
        print(f"  FAILED {name} [{language or '-'}]: {error}", file=sys.stderr)
    # Non-zero on any failure: a preview that reports success while a template
    # cannot render is the silent-failure pattern this project keeps tripping over.
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

INDEX_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.5 system-ui, sans-serif; display: flex; height: 100vh; }
aside { width: 300px; flex: 0 0 300px; overflow: auto; border-right: 1px solid #d1d5db;
        padding: 12px 14px; }
h1 { font-size: 14px; margin: 0 0 2px; }
p.hint { margin: 0 0 14px; font-size: 12px; opacity: .7; }
ul { list-style: none; margin: 0; padding: 0; }
li { margin-bottom: 4px; }
button { font: inherit; cursor: pointer; border: 1px solid #d1d5db; background: none;
         border-radius: 4px; padding: 3px 8px; }
button[aria-pressed=true] { background: #005ba1; color: #fff; border-color: #005ba1; }
button.tpl { display: block; width: 100%; text-align: left; }
.langs { display: flex; gap: 6px; margin-bottom: 10px; }
main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
nav { padding: 8px 12px; border-bottom: 1px solid #d1d5db; display: flex; gap: 10px;
      align-items: center; font-size: 12px; }
iframe { flex: 1; width: 100%; border: 0; background: #fff; }
code { font-size: 12px; opacity: .75; }
.err { color: #b91c1c; font-size: 12px; }
.note { font-size: 12px; opacity: .7; }
"""

INDEX_JS = """
const state = { template: TEMPLATES[0] && TEMPLATES[0].stem, language: LANGUAGES[0],
                part: 'html' };
function paint() {
  document.querySelectorAll('button.tpl').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.stem === state.template)));
  document.querySelectorAll('button.lang').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.lang === state.language)));
  document.querySelectorAll('button.part').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.part === state.part)));
  // The .pt part is one file per template, not one per language: nothing is
  // rendered in it, so there is nothing for a language to change.
  const name = state.part === 'pt'
    ? state.template + '.pt.html'
    : state.template + '.' + state.language + '.' + state.part;
  const src = name + '?g=' + window.__generation;
  document.getElementById('frame').src = src;
  document.getElementById('current').textContent = src;
}
document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  if (button.dataset.stem) state.template = button.dataset.stem;
  if (button.dataset.lang) state.language = button.dataset.lang;
  if (button.dataset.part) state.part = button.dataset.part;
  paint();
});
paint();
if (WATCHING) {
  setInterval(async () => {
    try {
      const response = await fetch(VERSION_PATH, { cache: 'no-store' });
      const generation = (await response.text()).trim();
      if (generation !== String(window.__generation)) location.reload();
    } catch (error) { /* server gone; keep polling */ }
  }, 1000);
}
"""


def write_index(rows, output, languages, generation, watch=False):
    """One page: a template list, a language switcher, an iframe.

    The reload script lives here and nowhere else. Injecting it into the rendered
    mails would change the bytes you came to inspect, which is the one thing a
    preview must not do.
    """
    templates = {}
    for name, language, error in rows:
        stem = name.replace(":", ".")
        entry = templates.setdefault(stem, {"name": name, "errors": [], "notes": []})
        # A note is not an error and must not be painted as one: the template is
        # still listed, and its .pt part -- which needs no fixture -- still opens.
        if isinstance(error, NotShipped):
            entry["notes"].append(error.short)
        elif error:
            entry["errors"].append(f"{language or '-'}: {error}")

    listing = "\n".join(
        f'<li><button class="tpl" data-stem="{html_module.escape(stem)}">'
        f"{html_module.escape(entry['name'])}</button>"
        + (
            f'<div class="err">{html_module.escape("; ".join(entry["errors"]))}</div>'
            if entry["errors"]
            else ""
        )
        + (
            f'<div class="note">{html_module.escape("; ".join(entry["notes"]))}</div>'
            if entry["notes"]
            else ""
        )
        + "</li>"
        for stem, entry in sorted(templates.items())
    )
    language_buttons = "".join(
        f'<button class="lang" data-lang="{html_module.escape(language)}">'
        f"{html_module.escape(language)}</button>"
        for language in languages
    )
    data = (
        f"const TEMPLATES = {_json([{'stem': stem} for stem in sorted(templates)])};\n"
        f"const LANGUAGES = {_json(languages)};\n"
        f"const VERSION_PATH = {_json(VERSION_PATH)};\n"
        f"const WATCHING = {'true' if watch else 'false'};\n"
        f"window.__generation = {generation};\n"
    )
    (output / "index.html").write_text(
        "<!DOCTYPE html>\n<html lang='en'><head><meta charset='utf-8'>"
        "<title>emailkit preview</title>"
        f"<style>{INDEX_CSS}</style></head><body>"
        "<aside><h1>imio.emailkit preview</h1>"
        "<p class='hint'>Rendered through <code>render()</code> with the committed "
        "fixtures (SPEC §7). This is the mail, not the build output -- except in "
        "the <code>.pt</code> part, which is the committed file itself, needs no "
        "fixture and substitutes nothing."
        + ("<br>Watching sources; the page reloads itself." if watch else "")
        + "</p>"
        f"<div class='langs'>{language_buttons}</div>"
        f"<ul>{listing}</ul></aside>"
        "<main><nav>"
        "<button class='part' data-part='html'>html</button>"
        "<button class='part' data-part='txt'>text</button>"
        "<button class='part' data-part='pt' "
        "title='The committed .pt, unrendered: no fixture, no substitution'>"
        ".pt</button>"
        "<code id='current'></code></nav>"
        "<iframe id='frame' title='rendered mail'></iframe></main>"
        f"<script>{data}{INDEX_JS}</script></body></html>",
        encoding="utf-8",
    )


def _json(value):
    return json.dumps(value)


# ---------------------------------------------------------------------------
# Watch and serve
# ---------------------------------------------------------------------------


def watched_paths(projects):
    """Sources and fixtures. Not the compiled output: that is what we produce."""
    paths = []
    for project in projects:
        paths.extend(project.vue_sources())
        fixtures = project.tests_dir / "fixtures"
        if fixtures.is_dir():
            paths.extend(sorted(fixtures.glob("*.py")))
        if project.twins_dir is not None and project.twins_dir.is_dir():
            paths.extend(sorted(project.twins_dir.glob("*.txt.pt")))
    return paths


def _fingerprint(projects):
    return {
        str(path): path.stat().st_mtime_ns
        for path in watched_paths(projects)
        if path.exists()
    }


def watch_loop(projects, pass_once, stop, interval=WATCH_INTERVAL):
    """Poll mtimes; re-run a pass when anything changed.

    Polling rather than inotify: no dependency, works on every platform, and the
    file count here is tens, not thousands. §5 asks for the loop, not for a
    filesystem-event framework.
    """
    previous = _fingerprint(projects)
    while not stop.wait(interval):
        current = _fingerprint(projects)
        if current == previous:
            continue
        changed = sorted(
            Path(path).name
            for path in set(current) | set(previous)
            if current.get(path) != previous.get(path)
        )
        print(f"\n==> changed: {', '.join(changed) or 'sources'}; rebuilding")
        try:
            pass_once()
        except Exception as exc:
            print(f"  FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
        previous = _fingerprint(projects)


def _handler_class(directory, state):
    import http.server

    class PreviewHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path == VERSION_PATH:
                body = str(state["generation"]).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if path.startswith(RESOURCE_PREFIX):
                self.serve_resource(path)
                return
            if path == "/favicon.ico":
                # Every browser asks for it on every page load and the preview
                # directory holds rendered mails, nothing else. Answering 204
                # rather than letting it 404 keeps a dev tool's console free of
                # an error that means nothing.
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            super().do_GET()

        def serve_resource(self, path):
            """Answer one ``++resource++`` url; see :func:`read_resource`."""
            found = read_resource(state["resources"], path)
            if found is None:
                self.send_error(404)
                return
            body, content_type = found
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # A preview rebuilds on save and an asset may be replaced with it.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002 - stdlib signature
            """Quieten the live-reload poll, and nothing else.

            ``args[0]`` is the request line for an access log, but ``log_error``
            routes through here too and passes an ``HTTPStatus`` -- so the
            membership test has to check the type first. Without the guard a
            plain 404 raises ``TypeError: argument of type 'HTTPStatus' is not
            iterable`` inside the handler thread and prints a traceback far more
            alarming than the missing file that caused it.
            """
            first = args[0] if args else ""
            if isinstance(first, str) and VERSION_PATH in first:
                return
            super().log_message(format, *args)

    return functools.partial(PreviewHandler, directory=str(directory))


def read_resource(resources, path):
    """``(bytes, content_type)`` for a ``++resource++`` url, or ``None``.

    The shell writes image and stylesheet urls as ``${asset_base}/<file>``, where
    ``asset_base`` is ``<portal_url>/++resource++<package>``.
    :func:`seed_portal_url` points that at this server; this is the other half,
    and it is what makes the preview show the header logo, the pill icon, the
    footer mark and Quicksand instead of silently dropping all four.

    The url is split on the FIRST slash after the prefix, so the segment before it
    is the resource name and the rest is the file. The result is resolved and then
    checked to be inside the directory: a resource url is attacker-controlled in no
    meaningful sense here, since this binds to 127.0.0.1 and serves a developer's
    own checkout, but `..` reaching an ``open()`` is the kind of thing that gets
    copied somewhere it does matter.
    """
    import mimetypes

    name, _, relative = path[len(RESOURCE_PREFIX) :].partition("/")
    directory = resources.get(name)
    if directory is None or not relative:
        return None
    root = Path(directory).resolve()
    target = (root / relative).resolve()
    if root not in target.parents:
        return None
    try:
        body = target.read_bytes()
    except OSError:
        return None
    content_type, _ = mimetypes.guess_type(target.name)
    return body, content_type or "application/octet-stream"


def serve(output, host, port, state):
    import socketserver

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with Server((host, port), _handler_class(output, state)) as httpd:
        print(f"\nserving http://{host}:{port}/   (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
