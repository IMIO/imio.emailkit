"""``bin/preview-emails`` -- the two-stage dev loop.

    bin/preview-emails [--package NAME] [--watch]

Maizzle's own ``--watch`` shows build-time output: raw ``${item/title}``
placeholders and unexpanded ``tal:repeat``. This script instead watches
the ``.vue`` sources, compiles them, renders the result through Chameleon
(``render()``) with the committed fixtures, and serves it with live
reload and a language switcher.

No ZODB connection is needed: ``render()`` is a pure function of
template, context, and registry state, so a minimal ZCML load (just
``Products.PageTemplates`` and each package's translation catalogs) is
enough for real placeholder substitution and real translations.

Without a site, theme tokens come from :class:`IEmailkitTheme`'s own
defaults, seeded into an in-memory registry. ``--theme token=value``
overrides them. For real branding, use ``@@emailkit-preview`` instead.

``portal_url`` is real, because every image depends on it being
non-empty. This server points ``portal_url`` at itself
(:func:`seed_portal_url`) and answers ``++resource++`` urls out of each
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

#: Where the rendered previews are written when ``--output`` is not
#: given. Under ``var/``, since that is already gitignored and a preview
#: is a throwaway artifact.
DEFAULT_OUTPUT = Path("var") / "preview"

#: Polled by the browser; bumped by every re-render.
VERSION_PATH = "/__emailkit/version"

#: Where the preview server answers the urls the kit shell builds from
#: ``asset_base``. Matches Zope's own traversal spelling, so the
#: rendered html matches what a real site would produce.
RESOURCE_PREFIX = "/++resource++"

WATCH_INTERVAL = 0.6


class NotShipped(str):
    """A row note that is a plain fact rather than a failure.

    An installed egg prunes ``emails/`` and ``tests/``, so no fixture can
    be there. A ``str`` subclass, distinguished by type so :func:`report`
    never mistakes it for a failure.
    """

    #: The same fact, short enough for a sidebar entry.
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
        help="override a theme token, e.g. --theme primary_color=#e6007e.",
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

    ``render()`` injects ``portal_url`` from ``getSite()``, so a preview
    cannot pass one in through the context. This replaces
    ``render_module.portal_url`` instead.

    Without this, every image in the mail is absent, not broken: the kit
    gates each one on ``tal:condition="asset_base"``.

    Uses ``import_module``, not ``from imio.emailkit import render``:
    ``imio/emailkit/__init__.py`` rebinds ``render`` to the render
    function, shadowing the submodule of the same name.
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

    A convention, not a lookup: a package's resource directory is
    registered under its own dotted name.
    """
    found = {}
    for project in projects:
        static = project.package_dir / "browser" / "static"
        if static.is_dir():
            found[project.package] = static
    return found


def _default_output():
    """``./var/preview``, relative to the working directory."""
    return Path.cwd() / DEFAULT_OUTPUT


# ---------------------------------------------------------------------------
# Just enough Zope for render() to be truthful
# ---------------------------------------------------------------------------

_configured = False


def configure(projects):
    """Load the minimum ZCML ``render()`` needs, once per process.

    Without ``Products.PageTemplates``, ``zope.pagetemplate`` falls back
    to ``zope.tal``, where ``${...}`` passes through verbatim with no
    error.
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
        # `plone.registry` is included for its field adapters, needed to
        # seed the theme tokens.
        f"{registry}"
        f"{catalogs}\n"
        "</configure>\n"
    )
    _configured = True


def _packages_with_catalogs(projects):
    """Packages that ship a ``locales/`` directory, plus ``imio.emailkit`` itself.

    ``imio.emailkit`` is always included: its strings appear in every
    consumer's mail.
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
    """Register an in-memory ``plone.app.registry`` holding the theme tokens.

    Without it, ``render()``'s ``get_theme()`` collapses every token to
    an empty string, showing an unbranded shell.
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

    Returns ``(name, language, error)`` rows, ``error`` being ``None`` on
    success. Rescans discovery and the compile cache first, so a rebuilt
    template is picked up.
    """
    from imio.emailkit import discovery
    from imio.emailkit import scan

    # `imio.emailkit.__init__` rebinds `render` to the render function,
    # so it is reachable only through this import form.
    from imio.emailkit.render import invalidate_cache as forget_templates

    # Rescan rather than trust an earlier pass, so a rebuilt template
    # shows up. Safe because templates are self-contained: nothing a
    # template renders looks up another package's registration mid-render.
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
        # Written before the fixture check: it needs no fixture.
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

    The one part that needs no fixture: unsubstituted, with every
    ``tal:condition`` branch shown at once. One file per template, not
    per language.
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
        # The zope.tal fallback passes ${...} through with no error.
        return (
            name,
            language,
            "unsubstituted ${...} in the output: the page-template engine is not "
            "the Chameleon one",
        )
    (output / f"{stem}.html").write_text(html, encoding="utf-8")
    (output / f"{stem}.txt").write_text(text, encoding="utf-8")
    return (name, language, None)


def _no_fixture(project, basename):
    """Why there is no fixture for ``basename``, as a failure or as a fact.

    A package shipping neither ``emails/`` nor ``tests/`` is an installed
    egg; that is a fact, not a failure. In a checkout, it is a real
    omission and still fails.
    """
    wanted = project.tests_dir / "fixtures" / f"{basename}.py"
    if project.emails_dir is None and not project.tests_dir.is_dir():
        return NotShipped(
            f"no fixture, and none possible: {project.package} is installed as an "
            f"egg, whose sdist prunes tests/. Its fixtures live in its "
            f"own checkout. The .pt part below needs none."
        )
    return f"no fixture; expected one at {wanted}"


def find_fixture(project, basename):
    """``<tests>/fixtures/<basename>.py``, or ``None``."""
    candidates = [project.tests_dir / "fixtures" / f"{basename}.py"]
    if project.root is not None:
        candidates.append(project.root / "tests" / "fixtures" / f"{basename}.py")
    candidates.append(project.package_dir / "tests" / "fixtures" / f"{basename}.py")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_fixture(path):
    """The ``CONTEXT`` dict of a fixture module, loaded by path."""
    spec = importlib.util.spec_from_file_location(
        f"_emailkit_fixture_{path.stem}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    context = getattr(module, "CONTEXT", None)
    if not isinstance(context, dict):
        raise ValueError("a fixture module must define a dict named CONTEXT")
    return context


def report(rows, output):
    notes = [row for row in rows if isinstance(row[2], NotShipped)]
    failures = [row for row in rows if row[2] and not isinstance(row[2], NotShipped)]
    rendered = len(rows) - len(failures) - len(notes)
    print(f"\nrendered {rendered} preview(s) into {output}")
    for name, _language, note in notes:
        print(f"  skip   {name}: {note}")
    for name, language, error in failures:
        print(f"  FAILED {name} [{language or '-'}]: {error}", file=sys.stderr)
    # Non-zero on any failure, so it is never reported as a success.
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

    The reload script lives only here, not in the rendered mails.
    """
    templates = {}
    for name, language, error in rows:
        stem = name.replace(":", ".")
        entry = templates.setdefault(stem, {"name": name, "errors": [], "notes": []})
        # A note is not an error: the template is still listed.
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
        "fixtures. This is the mail, not the build output -- except in "
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

    Polling, not inotify: no extra dependency, and the file count is
    tens, not thousands.
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
                # Answer 204 instead of a meaningless 404.
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

            ``log_error`` also routes through here and passes an
            ``HTTPStatus`` instead of a string, so the type is checked
            first.
            """
            first = args[0] if args else ""
            if isinstance(first, str) and VERSION_PATH in first:
                return
            super().log_message(format, *args)

    return functools.partial(PreviewHandler, directory=str(directory))


def read_resource(resources, path):
    """``(bytes, content_type)`` for a ``++resource++`` url, or ``None``.

    Split on the first slash after the prefix: the segment before it is
    the resource name, the rest is the file. The resolved path is then
    checked to stay inside the directory, so a `..` segment cannot
    escape it.
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
