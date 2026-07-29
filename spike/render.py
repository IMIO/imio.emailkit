"""Render a Maizzle-compiled `.pt` through Chameleon with the spike fixture.

Phase 0 assumption (a): the build output survives as a Chameleon template.
Throwaway harness -- SPEC §6.1's `render()` is a Phase 1 deliverable.

Renders through Zope's page-template machinery (`Products.PageTemplates`), not
bare Chameleon -- see the note by the xmlconfig calls for why that is forced.
Runs outside a Zope instance: no site, no request, no database.

Usage:  .venv/bin/python render.py [template.pt ...]
"""

import re
import sys

from pathlib import Path

import Products.PageTemplates
import zope.traversing

from Products.PageTemplates.PageTemplateFile import PageTemplateFile

from zope.component import provideUtility
from zope.configuration import xmlconfig
from zope.i18n.interfaces import ITranslationDomain
from zope.i18n.simpletranslationdomain import SimpleTranslationDomain

from fixture import CONTEXT


HERE = Path(__file__).parent

# Registers the `IPageTemplateEngine` utility that swaps zope.tal for Chameleon.
# Without it, zope.pagetemplate silently falls back to zope.tal, where `${...}`
# passes through VERBATIM and no error is raised -- a green render that ships
# raw placeholders. `tal:repeat` works either way, so the fallback is easy to
# miss. Plone reaches this ZCML only via `plone.z3cform`.
#
# Standalone `chameleon.PageTemplateFile` is NOT usable here: it has no TAL path
# expressions, so `${member/fullname}` raises `NameError: fullname`. Together
# with the jbot finding that only `Products.PageTemplates.PageTemplateFile` and
# `Products.Five...ViewPageTemplateFile` are patched by z3c.jbot, this pins
# SPEC §6.1's `render()` to the Zope page-template machinery, not bare Chameleon.
xmlconfig.file("configure.zcml", Products.PageTemplates)

# Registers the default traversable adapters, so TAL paths can walk plain Python
# objects (`${member/fullname}`) and not just mappings. Plone provides these in a
# real site; the spike needs them explicitly because it runs outside Zope.
xmlconfig.file("configure.zcml", zope.traversing)


# A real translation domain, so the spike proves i18n:translate SUBSTITUTES
# rather than merely proving it does not crash. Without a registered domain --
# and without an `i18n:domain` declaration in the template -- zope.i18n silently
# returns the untranslated default, which looks identical to success.
MESSAGES = {
    ("fr", "email_intro_default"): "Vous avez recu une convocation.",
    ("fr", "email_greeting"): "Bonjour ${fullname}",
    ("fr", "col_title"): "Intitule",
    ("fr", "col_status"): "Statut",
}

provideUtility(
    SimpleTranslationDomain("imio.emailkit", MESSAGES),
    ITranslationDomain,
    name="imio.emailkit",
)


def render(path):
    template = PageTemplateFile(str(path))
    namespace = dict(CONTEXT)
    # No request in the spike, so the render language must be stated explicitly.
    namespace["target_language"] = namespace.get("lang", "fr")
    # `extra_context` lands in the template namespace as top-level names, so the
    # template's Plone-idiomatic `${member/fullname}` paths resolve directly.
    return template.pt_render(extra_context=namespace)


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))
    return bool(condition)


def main(argv):
    paths = [Path(a) for a in argv[1:]] or [HERE / "build" / "spike.pt"]
    failures = 0

    for path in paths:
        print(f"\n=== {path} ===")
        try:
            out = render(path)
        except Exception as exc:  # noqa: BLE001 - we want the class name shown
            print(f"  [FAIL] Chameleon could not render: "
                  f"{type(exc).__name__}: {exc}")
            failures += 1
            continue

        outdir = HERE / "rendered"
        outdir.mkdir(exist_ok=True)
        target = outdir / (path.stem + ".fr.html")
        target.write_text(out)
        print(f"  rendered -> {target.relative_to(HERE)} ({len(out)} bytes)")

        ok = True
        # No placeholder may survive a successful render, EXCEPT the one the
        # template deliberately escapes as `$${...}` to reach the inbox literal.
        expected_literal = "${not/evaluated}"
        leftovers = [m for m in re.findall(r"\$\{[^}]*\}", out)
                     if m != expected_literal]
        ok &= check("no unresolved ${...} placeholders", not leftovers,
                    f"found {leftovers[:5]}" if leftovers else "")
        # No TAL/i18n ATTRIBUTE may survive either. Anchored on the leading
        # whitespace and trailing `=` so prose mentioning `tal:attributes` in
        # visible text is not a false positive.
        residue = re.findall(r"\s(?:tal|i18n|metal):[a-z]+=", out)
        ok &= check("no leftover tal:/i18n:/metal: attributes", not residue,
                    f"found {sorted(set(residue))}" if residue else "")

        if path.name.startswith("spike"):
            ok &= check("tal:repeat produced one row per fixture item",
                        out.count("Approbation du PV") == 1
                        and out.count("Budget 2026") >= 1
                        and out.count("Marche public - voirie") == 1)
            ok &= check("${...} in a text node substituted",
                        "Antoine Dupont" in out)
            ok &= check("${...} in an href substituted",
                        "/points/budget-2026" in out)
            ok &= check("theme token via tal:attributes substituted",
                        "background-color: #005ba1" in out)
            ok &= check("i18n:translate='' actually translated the msgid",
                        "Vous avez recu une convocation." in out
                        and "email_intro_default" not in out)
            ok &= check("i18n:translate + i18n:name interpolated the name",
                        "Bonjour Antoine Dupont" in out)
            ok &= check("i18n:translate translated table headers",
                        "Intitule" in out and "Statut" in out)
            ok &= check("structure body_html injected unescaped",
                        "<strong>Corps HTML injecte</strong>" in out)
            ok &= check("tal:condition kept the URGENT block",
                        "URGENT" in out)
            ok &= check("raw-escaped block repeated over extras",
                        "Annexe 1" in out and "Annexe 2" in out)
            ok &= check("v-pre kept Vue braces literal",
                        "{{ vue_would_eat_this }}" in out)
            ok &= check("$${...} escaped to a literal ${...} for the inbox",
                        "${not/evaluated}" in out)
            ok &= check("inlined CSS survived into the render",
                        'style="font-size: 14px' in out
                        or "font-size: 14px" in out)

        if not ok:
            failures += 1

    print(f"\n{'FAILURES: %d' % failures if failures else 'ALL CHECKS PASSED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
