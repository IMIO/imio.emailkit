"""Render every registered template with its committed fixture, and serve it.

Run through ``make preview-emails``. Renders the committed ``.pt`` files
through ``render()`` inside a real Plone site, not Maizzle's own dev server.

Environment:

``EMAILKIT_PREVIEW_DIR``   output directory (default ``var/preview``)
``EMAILKIT_PREVIEW_PORT``  port to serve on (default 8090); ``0`` to skip serving
``EMAILKIT_PREVIEW_LANGS`` comma-separated languages (default ``fr,nl,en``)
"""

from pathlib import Path

import html as html_module
import os
import sys


REPO = Path(__file__).resolve().parent.parent
# ``tests/`` is not importable as a package.
sys.path.insert(0, str(REPO / "tests"))

import support  # noqa: E402


PREVIEW_DIR = Path(os.getenv("EMAILKIT_PREVIEW_DIR") or (REPO / "var" / "preview"))
PORT = int(os.getenv("EMAILKIT_PREVIEW_PORT") or 8090)
LANGUAGES = [
    part.strip()
    for part in (os.getenv("EMAILKIT_PREVIEW_LANGS") or "fr,nl,en").split(",")
    if part.strip()
]

INDEX_CSS = """
body { font: 15px/1.5 system-ui, sans-serif; margin: 0; color: #111827; }
header { padding: 16px 24px; border-bottom: 1px solid #e5e7eb; }
h1 { font-size: 18px; margin: 0 0 4px 0; }
p.hint { margin: 0; color: #6b7280; font-size: 13px; }
main { padding: 16px 24px; }
table { border-collapse: collapse; }
th, td { text-align: left; padding: 6px 16px 6px 0; vertical-align: top; }
th { font-weight: 600; color: #374151; }
a { color: #005ba1; }
code { background: #f3f4f6; padding: 1px 4px; border-radius: 3px; }
"""


def portal():
    """The single Plone site in the instance."""
    from Products.CMFPlone.Portal import PloneSite

    app = globals()["app"]
    sites = [obj for obj in app.objectValues() if isinstance(obj, PloneSite)]
    if not sites:
        sys.exit("No Plone site in this instance. Run `make create-site` first.")
    return sites[0]


def main():
    from imio.emailkit import render
    from imio.emailkit.discovery import get_templates
    from imio.emailkit.interfaces import IEmailkitLayer
    from zope.component.hooks import setSite
    from zope.interface import alsoProvides

    site = portal()
    setSite(site)
    alsoProvides(site.REQUEST, IEmailkitLayer)

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    templates = get_templates()
    for name in sorted(templates):
        short = name.split(":", 1)[-1]
        write_source(short, templates[name])
        fixture_path = support.fixture_path(short)
        if not fixture_path.exists():
            rows.append((name, None, f"no fixture at tests/fixtures/{short}.py"))
            continue
        context = support.load_fixture(short)
        for language in LANGUAGES:
            try:
                body, text = render(name, context=dict(context), language=language)
            except Exception as exc:
                rows.append((name, language, f"{type(exc).__name__}: {exc}"))
                continue
            (PREVIEW_DIR / f"{short}.{language}.html").write_text(
                body, encoding="utf-8"
            )
            (PREVIEW_DIR / f"{short}.{language}.txt").write_text(text, encoding="utf-8")
            rows.append((name, language, None))

    write_index(rows)
    report(rows)

    if PORT:
        serve()


def write_source(short, template):
    """Copy the committed ``.pt`` in beside the rendered previews, unrendered."""
    from imio.emailkit.render import resolved_path

    path = resolved_path(template.html_path)
    try:
        markup = path.read_text(encoding="utf-8")
    except OSError as exc:
        markup = f"<pre>Could not read {path}: {exc}</pre>"
    (PREVIEW_DIR / f"{short}.pt.html").write_text(markup, encoding="utf-8")


def write_index(rows):
    """A language switcher and a link per part."""
    templates = {}
    for name, language, error in rows:
        templates.setdefault(name.split(":", 1)[-1], []).append((language, error))

    body = [
        "<html><head><meta charset='utf-8'><title>emailkit preview</title>",
        f"<style>{INDEX_CSS}</style></head><body>",
        "<header><h1>imio.emailkit preview</h1>",
        "<p class='hint'>Rendered from the <em>committed</em> "
        "<code>.pt</code> files with the committed fixtures. Run "
        "<code>make build-emails</code> then re-run "
        "<code>make preview-emails</code> after editing a source. The "
        "<code>.pt</code> link is the committed file itself, unrendered -- no "
        "fixture needed, and nothing substituted.</p></header>",
        "<main><table>",
    ]
    for short, entries in sorted(templates.items()):
        cells = []
        for language, error in entries:
            if error:
                cells.append(
                    f"<span title='{html_module.escape(error)}'>"
                    f"{language or '-'} ✗</span>"
                )
            else:
                cells.append(
                    f"<a href='{short}.{language}.html'>{language} html</a> / "
                    f"<a href='{short}.{language}.txt'>txt</a>"
                )
        cells.append(f"<a href='{short}.pt.html'>.pt</a>")
        body.append(
            f"<tr><th>{html_module.escape(short)}</th>"
            f"<td>{' &nbsp;|&nbsp; '.join(cells)}</td></tr>"
        )
    body.append("</table></main></body></html>")
    (PREVIEW_DIR / "index.html").write_text("\n".join(body), encoding="utf-8")


def report(rows):
    failures = [(n, lang, err) for n, lang, err in rows if err]
    ok = len(rows) - len(failures)
    print(f"\nrendered {ok} preview(s) into {PREVIEW_DIR}")
    for name, language, error in failures:
        print(f"  FAILED {name} [{language}]: {error}")
    if failures:
        sys.exit(1)


def serve():
    import functools
    import http.server
    import socketserver

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(PREVIEW_DIR)
    )
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"serving http://127.0.0.1:{PORT}/  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()


main()
