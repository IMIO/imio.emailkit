"""``bin/compile-emails --new NAME`` (SPEC §5).

"``--new NAME`` scaffolds the four files a template needs -- a minimal ``.vue``
skeleton, a fixture, a golden placeholder, and a registration stub to paste.
Templates have a rigid shape; making the right structure the path of least
resistance beats documenting it."

Every skeleton below encodes an authoring rule that this project learned the hard
way and that ``docs/DECISIONS.md`` records: no Chameleon placeholder in a literal
``style`` or ``class`` attribute, no ``tal:``/``i18n:`` on a kit component, locale
helpers called as ``${python: ...}``, no ``--`` in a comment. The point of
scaffolding is that a new template starts on the right side of all four.
"""

from pathlib import Path


class ScaffoldError(Exception):
    """A file the scaffolding would create already exists, or cannot be placed."""


#: The language the golden placeholder is written for. First of §7's pair; the
#: second is produced by the same regeneration run.
GOLDEN_LANGUAGE = "fr"

VUE_TEMPLATE = """\
<script setup>
/**
 * {name}
 *
 * Context this template expects (keep this list in step with
 * tests/fixtures/{name}.py, which is what the preview and the golden test feed it):
 *   title  ; heading text
 *   intro  ; lead paragraph
 *
 * Authoring rules that apply here (SPEC §3, enforced by `bin/check-emails`):
 *   1. no tal: or i18n: attribute on a Kit* component; author dynamic regions as
 *      plain <tr>/<td> markup instead
 *   2. no Chameleon placeholder in a literal `class` or `style` attribute; use
 *      tal:attributes="style string:..." when a value has to be computed
 *   3. locale helpers are called as ${{python: format_date(when)}}; a TAL path
 *      expression cannot call a function
 *   4. never write two dashes in a comment ; Chameleon refuses to parse the
 *      compiled output
 */
</script>

<template>
  <KitMain>
    <h1 class="m-0 mb-3 font-display text-lg font-bold leading-7 text-imio-black">${{title}}</h1>

    <p class="m-0 mb-4 text-sm leading-6 text-imio-black">${{intro}}</p>
  </KitMain>
</template>
"""

FIXTURE_TEMPLATE = '''\
"""Fixture for the `{name}` template (SPEC §7).

One dict of context data, named CONTEXT. It feeds three things and must keep all
three honest: `bin/preview-emails`, the golden-file test, and anybody reading the
template to find out what it expects.

Prefer values that would *expose* a bug: accented characters, a long line that
has to wrap, an empty optional, a number that has to be formatted.
"""

CONTEXT = {{
    "title": "Titre de l'e-mail {name}",
    "intro": (
        "Remplacez ce texte par un contenu réaliste : accents, ponctuation "
        "française et une longueur qui oblige le gabarit à passer à la ligne."
    ),
}}
'''

GOLDEN_TEMPLATE = """\
PLACEHOLDER. This file is not a snapshot yet.

`{name}` has been scaffolded but never rendered, so there is nothing to compare
against. Regenerate deliberately once the template renders the way you want:

    make update-golden          # or: EMAILKIT_UPDATE_GOLDEN=1 pytest

and review the diff before committing it. SPEC §7: "`bin/test --update-golden`
regenerates snapshots deliberately."

Leaving this text in place is intentional: a golden file that silently agreed
with whatever the template happens to emit would catch nothing, which is the one
failure mode §7 exists to prevent.
"""

REGISTRATION_TEMPLATE = """\
# Paste into {package}'s ZCML (SPEC §4), inside its existing
# `<emailkit:templates>` block:
#
#     <emailkit:template
#         name="{name}"
#         subject="[email_subject_{name}] TODO subject"
#         preheader="[email_preheader_{name}] TODO preheader"
#         />
#
# `subject` and `preheader` are `[msgid] Default text` -- the msgid is
# translated per recipient language at send time; `preheader` is the optional
# hidden inbox-preview line every mail client shows next to the subject. Omit
# it and the layout's preview div collapses to nothing.
#
# No `<emailkit:templates>` block in {package} yet? Add the whole thing:
# declare the namespace on your `<configure>` root (without it the file does
# not parse, and build tooling does not even discover the package), plus the
# one-time meta include every consumer needs:
#
#     <configure
#         xmlns="http://namespaces.zope.org/zope"
#         xmlns:emailkit="http://namespaces.imio.be/emailkit"
#         ...>
#
#     <include package="imio.emailkit" file="meta.zcml" />
#     <emailkit:templates>
#       <emailkit:template
#           name="{name}"
#           subject="[email_subject_{name}] TODO subject"
#           preheader="[email_preheader_{name}] TODO preheader"
#           />
#     </emailkit:templates>

    <emailkit:template
        name="{name}"
        subject="[email_subject_{name}] TODO subject"
        preheader="[email_preheader_{name}] TODO preheader"
        />
"""


def new_template(project, name, force=False):
    """Create the four files ``name`` needs in ``project``; return their paths.

    :raises ScaffoldError: if the project ships no sources, if ``name`` is not a
        usable file stem, or if any target exists and ``force`` is false.
    """
    if not project.compilable:
        raise ScaffoldError(
            f"{project.package} ships no `emails/` directory, so there is nowhere "
            f"to put a new template. `emails/` is pruned from the sdist (SPEC §4), "
            f"so scaffolding only works in a checkout."
        )
    if not name or not name.replace("_", "").replace("-", "").isalnum():
        raise ScaffoldError(
            f"{name!r} is not a usable template name. A name becomes a filename, "
            f"a `<name>.pt`, a fixture module and a lookup key "
            f"({project.package}:{name}), so keep it to letters, digits and "
            f"underscores."
        )

    tests_dir = project.tests_dir
    files = {
        project.sources_dir / f"{name}.vue": VUE_TEMPLATE.format(name=name),
        tests_dir / "fixtures" / f"{name}.py": FIXTURE_TEMPLATE.format(name=name),
        tests_dir / "golden" / f"{name}.{GOLDEN_LANGUAGE}.html": GOLDEN_TEMPLATE.format(
            name=name
        ),
        project.sources_dir / f"{name}.registration.txt": REGISTRATION_TEMPLATE.format(
            name=name, package=project.package
        ),
    }

    existing = sorted(str(path) for path in files if path.exists())
    if existing and not force:
        raise ScaffoldError(
            "refusing to overwrite:\n  "
            + "\n  ".join(existing)
            + "\nPass --force if that is really what you want."
        )

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return sorted(files)


def registration_stub(project, name):
    """The paste-me text, for echoing to stdout as well as writing to a file."""
    return REGISTRATION_TEMPLATE.format(name=name, package=project.package)


def next_steps(project, name, paths):
    """What the developer has to do that the scaffolding cannot do for them."""
    source = next(
        (Path(path).name for path in paths if str(path).endswith(".vue")),
        f"{name}.vue",
    )
    return (
        f"\nScaffolded {project.package}:{name}:\n"
        + "".join(f"  {path}\n" for path in paths)
        + "\nNext, in this order:\n"
        f"  1. paste the registration stub into {project.package}'s ZCML, inside "
        "its `<emailkit:templates>` block\n"
        f"  2. write the real markup in {source} and real data in the fixture\n"
        f"  3. `bin/preview-emails --package {project.package}` to look at it\n"
        f"  4. `make update-golden` once it is right, then commit the `.pt` too\n"
    )
