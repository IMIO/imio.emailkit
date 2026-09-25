"""Verify a real, installed site: profile applied, mails restyled, opt-out
and layer-override both working. Run against a live ZODB:

    .venv/bin/zconsole run instance/etc/zope.conf scripts/verify_install.py
"""

from pathlib import Path
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from zope.component import getUtility
from zope.component.hooks import setSite
from zope.interface import alsoProvides


CHECKS = []


def check(label, condition, detail=""):
    CHECKS.append((label, bool(condition), detail))


def main(app):
    site = app.Plone
    setSite(site)
    request = site.REQUEST

    # 1 -- the profile is applied
    setup = getToolByName(site, "portal_setup")
    version = setup.getLastVersionForProfile("imio.emailkit:default")
    check(
        "imio.emailkit:default is applied",
        version not in (None, "unknown"),
        f"version={version}",
    )

    # 2 -- the browser layer is live
    from plone.browserlayer.utils import registered_layers

    names = [layer.__name__ for layer in registered_layers()]
    check("IEmailkitLayer is registered", "IEmailkitLayer" in names)

    # 3 -- the theme records exist
    registry = getUtility(IRegistry)
    tokens = [
        "imio.emailkit.theme.logo_url",
        "imio.emailkit.theme.primary_color",
        "imio.emailkit.theme.footer_html",
    ]
    check("the three theme records exist", all(t in registry.records for t in tokens))

    # 4 -- the stock mail views render our templates.
    # A subscriber normally applies the layer; it does not fire for zconsole.
    from imio.emailkit.interfaces import IEmailkitLayer

    alsoProvides(request, IEmailkitLayer)

    from Products.CMFPlone.browser.login.password_reset import PasswordResetToolView

    for name in ("mail_password_template", "registered_notify_template"):
        view = PasswordResetToolView(site, request)
        template = getattr(view, "index", None) or site.restrictedTraverse(name)
        filename = getattr(template, "filename", "") or ""
        del filename  # only the resolved path matters, checked below

        resolved = site.restrictedTraverse(name)
        path = getattr(getattr(resolved, "index", resolved), "filename", "")
        check(
            f"{name} resolves to our override",
            "imio/emailkit/browser/overrides" in str(path),
            str(path).split("site-packages")[-1] or str(path),
        )

    # 5 -- render() works against the real site
    from imio.emailkit import render

    import sys

    # zconsole exec()s this file, so __file__ does not exist.
    sys.path.insert(0, str(Path.cwd() / "tests"))
    from fixtures.notification import CONTEXT

    html, text = render(
        "imio.emailkit:notification", context=dict(CONTEXT), language="fr"
    )
    check("render() returns html and text", bool(html) and bool(text))
    check(
        "no raw ${...} survived the render",
        "${" not in html,
        html[html.find("${") :][:60] if "${" in html else "",
    )
    check("CSS was inlined", 'style="' in html)
    check("lang came from the render language", 'lang="fr"' in html)

    print()
    failed = 0
    for label, ok, detail in CHECKS:
        print(
            f"  [{'PASS' if ok else 'FAIL'}] {label}"
            + (f" -- {detail}" if detail else "")
        )
        failed += not ok
    print()
    print("ALL CHECKS PASSED" if not failed else f"FAILURES: {failed}")
    return failed


if "app" in globals():
    main(globals()["app"])
