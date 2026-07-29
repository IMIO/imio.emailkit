"""Render every registered template with its committed fixture, and serve it.

The two-stage dev loop of SPEC §5, in its Phase 1 Makefile form (§9's sequencing
note). Run it through ``make preview-emails``, which supplies the Zope
configuration this script needs.

**Why not ``maizzle --watch``.** §5 rejects it outright: Maizzle's dev server
shows *build-time* output -- raw ``${item/title}``, unexpanded ``tal:repeat`` --
which is "a miserable authoring loop". What a developer needs to look at is the
mail a citizen receives, which only exists after ``render()`` has run inside a
Plone site with the real registry and the real translation catalogs. Hence
``zconsole``: this script needs a ZODB connection, not just a filesystem.

**Deferred:** watching the ``.vue`` sources and live-reloading. Re-run the target
after ``make build-emails``. What ships here is compile-free: it renders the
*committed* ``.pt`` files, so it is also a fast way to check what is actually in
git rather than what is in your working tree.

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
# ``tests/`` is not importable as a package, and the fixtures are data files
# loaded by path -- the same loader the golden harness uses, so a preview and a
# golden file can never disagree about what the fixture says.
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
    # The preview must see what a real request sees, jbot overrides included.
    alsoProvides(site.REQUEST, IEmailkitLayer)

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    for name in sorted(get_templates()):
        short = name.split(":", 1)[-1]
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


def write_index(rows):
    """A language switcher and a link per part -- §5's "and a language switcher"."""
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
        "<code>make preview-emails</code> after editing a source.</p></header>",
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
        # Exit non-zero: a preview target that reports success while a template
        # cannot render is the same silent-failure pattern this project keeps
        # tripping over.
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
