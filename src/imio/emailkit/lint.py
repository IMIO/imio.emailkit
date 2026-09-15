"""The authoring lint -- gate 2 of ``bin/check-emails``.

Reads ``.vue`` email sources and reports ``path:line: rule-id`` for each
violation of the authoring rules below, exiting non-zero if there is one.

    python -m imio.emailkit.lint emails/src/templates src/imio/emailkit/kit
    python -m imio.emailkit.lint --list-rules

**Every rule here is a failure this project actually hit, and every one of them
produced a SUCCESSFUL Maizzle build.** That is the whole reason the module
exists: the settled position of this project is that the
Maizzle exit code carries almost no information about correctness. A browser
preview does not show these either -- three of the eight rules only ever fail in
a mail client or inside Chameleon at *send* time, long after CI was green.

Design constraints, in the order they matter.

**Plain regex, no parser.** A lint that needs a parser
is a lint nobody runs, and this one has to run in a buildout-generated script on
a machine with nothing but the egg installed. Nothing below imports anything
outside the standard library, and nothing below imports from this package -- so
``python src/imio/emailkit/lint.py <paths>`` works with a bare interpreter, while
``python -m imio.emailkit.lint`` is the entry point the Makefile and
``bin/check-emails`` use.

**Prefer a missed case to a false positive.** A lint that cries wolf gets
disabled, and then ``style-placeholder`` and ``comment-double-dash`` ship to
production. So every pattern below stops at the first ambiguity rather than
guessing: attribute lists are read only as far as the first ``>``, ``${...}`` is
read only as far as the first ``}``, and the contents of ``<script>`` blocks and
of Vue-bound attribute values are not scanned for Chameleon syntax at all. Each
rule has a *clean* fixture in ``tests/fixtures/lint/clean/`` that must stay
silent, as well as a violating one.

**An escape hatch, because without one someone deletes the gate.** Any line may
carry ``emailkit-lint: ignore=<rule-id>`` (comma-separated ids, or ``all``) in a
comment; the marker counts on the offending line, on the line just above it, and
anywhere inside the enclosing tag -- an HTML comment cannot be written *inside* a
tag, so a violation on the fourth line of a multi-line tag would otherwise have
nowhere to put one.

**Say what the consequence is.** These failures are invisible at build time, so
a bare rule name teaches nobody anything. Every report prints why it matters and
what to write instead.
"""

from dataclasses import dataclass
from pathlib import Path

import argparse
import re
import sys


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """One check: its id, what it found, the consequence, and the fix."""

    rule_id: str
    what: str
    why: str
    fix: str


def _rule(rule_id, what, why, fix):
    return Rule(rule_id=rule_id, what=what, why=why, fix=fix)


RULES = {
    rule.rule_id: rule
    for rule in (
        _rule(
            "tal-on-component",
            "a tal:/i18n:/metal: attribute on a kit component",
            "Vue attribute fallthrough lands it on the component's root element, "
            "which the kit owns and may change; the build succeeds either way",
            "author dynamic regions as plain <tr>/<td> markup and put the "
            "tal: attribute there, or wrap the component in a <div tal:...>",
        ),
        _rule(
            "runtime-class",
            "a class value that is not literal in the build output",
            "Tailwind's scanner and css.purge only see build-time markup, so the "
            "utilities are never generated and the class silently styles nothing",
            'use tal:attributes="style string:..." with literal values for '
            "runtime styling, and keep whole class names literal in the source",
        ),
        # Phase 0 caveat A1. The single most damaging rule in this file.
        _rule(
            "style-placeholder",
            "a Chameleon ${...} placeholder in a literal style attribute",
            "juice parses every style attribute as CSS: the { opens a block, the "
            "closing } is EATEN, and CSS inlining then stops for the WHOLE "
            "document (measured: 31 inline styles down to 6) with exit code 0",
            'tal:attributes="style string:background-color: ${theme/primary_color}"'
            ' -- or bgcolor="${...}", which is never parsed as CSS',
        ),
        # Phase 0 control 2.
        _rule(
            "class-placeholder",
            "a Chameleon ${...} placeholder in a literal class attribute",
            "css.safe rewrites $ to - and strips the braces inside class atoms, "
            "so the placeholder is corrupted rather than substituted",
            'tal:attributes="class string:..." if it is truly needed -- but see '
            "runtime-class first: a runtime class has no CSS behind it",
        ),
        # An enforced-alt a11y default. RGAA applies to iMio's clients.
        _rule(
            "missing-alt",
            "an image with no alt attribute",
            "a screen reader announces the file name or nothing at all, and a "
            "client that blocks remote images shows an empty box with no label",
            'add alt="..." (i18n:attributes="alt <msgid>" to translate it); '
            'alt="" is the correct spelling for a purely decorative image',
        ),
        # Phase 0 caveat A2.
        _rule(
            "comment-double-dash",
            'a "--" sequence inside an HTML comment',
            "-- is illegal inside any XML/HTML comment: Chameleon raises "
            "\"The string '--' is not allowed in a comment\" and the .pt is "
            "unparseable AT RUNTIME while the build reports success",
            "use ; or a full stop instead of --; the same rule holds for every "
            "ZCML and GenericSetup XML comment in the repo, which have no "
            "comment stripper protecting them",
        ),
        # Phase 1 -- Maizzle's rawExtract plugin.
        _rule(
            "raw-in-comment",
            "the <Raw> component named in angle brackets inside a comment",
            "Maizzle extracts <Raw> with one naive global regex over the whole "
            "file, comments included, so the mention becomes the opening tag of "
            "the match, swallows the real block and deletes it from the output",
            "write Raw without the angle brackets in prose, or spell it &lt;Raw&gt;",
        ),
        # Phase 1 -- the locale helpers.
        _rule(
            "path-call",
            "a function call in a TAL path expression",
            "TAL paths cannot call functions: this raises "
            '"Invalid variable name" when Chameleon compiles the .pt',
            "${python: format_date(when)} -- the python: prefix is what makes it "
            "an expression rather than a path",
        ),
    )
}


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """One rule firing at one place."""

    path: str
    line: int
    rule: Rule
    detail: str = ""

    def __str__(self):
        head = f"{self.path}:{self.line}: {self.rule.rule_id} {self.rule.what}"
        if self.detail:
            head += f"\n    found: {self.detail}"
        return "\n".join((
            head,
            f"    why: {self.rule.why}",
            f"    fix: {self.rule.fix}",
            f"    (deliberate exception? put `{IGNORE_HINT}{self.rule.rule_id}`"
            " in a comment on that line, or just above the tag)",
        ))


IGNORE_HINT = "emailkit-lint: ignore="


# ---------------------------------------------------------------------------
# Reading a .vue file with regexes only
# ---------------------------------------------------------------------------

# <script>/<style> *contents* are blanked before anything is scanned. They are
# JavaScript and CSS, and they are full of things that look like violations to a
# regex: `/** ---- */` banner comments, `${config.emailkit.cssEntry}` JS template
# literals, and `'<!--[if mso]>...'` raw strings. None of it is authored markup.
_SCRIPT_OR_STYLE = re.compile(r"(<(script|style)\b[^>]*>)(.*?)(</\2\s*>)", re.S | re.I)

# An opening tag. `[^>]*` deliberately stops at the first `>`, even one inside a
# quoted value: truncating the attribute list can only make us miss a violation,
# never invent one.
_TAG = re.compile(r"<([A-Za-z][-\w.:]*)([^>]*)>", re.S)

# A PascalCase tag is a Vue component -- kit (`KitButton`) or Maizzle built-in
# (`Container`, `Outlook`). Attribute fallthrough is the same hazard for both.
_COMPONENT = re.compile(r"^[A-Z][A-Za-z0-9]*$")

_ATTR = re.compile(r"""([@:\w][-\w.:]*)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.S)
_ATTR_NAME = re.compile(r"([@:\w][-\w.:]*)")
_QUOTED_VALUE = re.compile(r"""=\s*("[^"]*"|'[^']*')""", re.S)

# Vue-bound attributes (`:class`, `v-html`, `@click`). Their values are
# JavaScript evaluated at *build* time, so a `${...}` in one is a JS template
# literal and not Chameleon -- scanning them for TAL would be a false positive
# factory. Values are blanked before the placeholder scan; the attribute pass
# still sees them, because `:style` and `:class` have rules of their own.
_VUE_BOUND = re.compile(r"""(?:^|\s)(?::|@|v-)[-\w.:]*\s*=\s*("[^"]*"|'[^']*')""", re.S)

_HTML_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
# Outlook conditional comments are load-bearing markup, not commentary, and they
# legitimately carry `-` runs. Recognised exactly as the kit's comment stripper
# recognises them, which also covers the downlevel-revealed `<!--[if !mso]><!-->`.
_CONDITIONAL_COMMENT = re.compile(r"\[if|\[endif\]")
_JS_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_RAW_MENTION = re.compile(r"</?Raw\b")

# `[^}]*` stops at the first `}`, so a nested expression such as
# `${python:(theme or {}).get('x')}` simply is not matched. Missing it is fine;
# it starts with `python:` and would have been skipped anyway.
_PLACEHOLDER = re.compile(r"\$\{([^}]*)\}")

# Prefixes that make a `${...}` something other than a TAL *path*, so a call
# inside it is legal.
_NOT_A_PATH = (
    "python:",
    "string:",
    "structure",
    "path:",
    "not:",
    "nocall:",
    "exists:",
    "defer:",
    "load:",
    "import:",
    "provider:",
)

_IGNORE = re.compile(r"emailkit-lint:\s*ignore\s*=\s*([-\w]+(?:\s*,\s*[-\w]+)*)", re.I)

_ALT_VIA_TAL = re.compile(r"""(?:tal|i18n):attributes\s*=\s*["'][^"']*\balt\b""", re.S)

_ALT_ATTRS = frozenset({"alt", ":alt", "v-bind:alt"})
_IMAGE_TAGS = frozenset({"img", "Img", "KitImg"})


def _blank(text):
    """``text`` with every character except newlines replaced by a space.

    Length and newline positions are preserved, so every offset taken from a
    blanked copy is still a valid offset into the original source and line
    numbers stay honest.
    """
    return re.sub(r"[^\n]", " ", text)


def markup_only(source):
    """``source`` with ``<script>`` and ``<style>`` contents blanked out."""
    return _SCRIPT_OR_STYLE.sub(
        lambda m: m.group(1) + _blank(m.group(3)) + m.group(4), source
    )


def _script_bodies(source):
    """``(offset, text)`` for each ``<script>``/``<style>`` body."""
    return [(m.start(3), m.group(3)) for m in _SCRIPT_OR_STYLE.finditer(source)]


def _blank_quoted_values(text):
    """``text`` with every quoted attribute value blanked.

    Attribute *names* are then safe to scan: without this, the words inside a
    long ``tal:define="..."`` value read as attribute names, and a component
    whose ``title`` happened to mention ``tal:content`` would be reported.
    """
    return _QUOTED_VALUE.sub(
        lambda m: m.group(0).replace(m.group(1), _blank(m.group(1)), 1), text
    )


def _blank_spans(text, spans):
    """``text`` with the given ``(start, end)`` ranges blanked."""
    out = list(text)
    for start, end in spans:
        for index in range(start, end):
            if out[index] != "\n":
                out[index] = " "
    return "".join(out)


def line_at(source, offset):
    """The 1-based line number of ``offset`` in ``source``."""
    return source.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# The checks. Each yields (line, rule_id, detail).
# ---------------------------------------------------------------------------


def _component_findings(source, name, skeleton, base):
    """Rule 1: ``tal:``/``i18n:``/``metal:`` on a PascalCase (component) tag."""
    if not _COMPONENT.match(name):
        return
    for match in _ATTR_NAME.finditer(skeleton):
        attr = match.group(1)
        if attr.startswith(("tal:", "i18n:", "metal:")):
            yield (
                line_at(source, base + match.start(1)),
                "tal-on-component",
                f"<{name} {attr}=...>",
            )


def _assigns_class(value):
    """Does a ``tal:attributes`` value set ``class``?"""
    return any(clause.split()[:1] == ["class"] for clause in value.split(";"))


def _assembles_a_name(value):
    """Does a Vue expression *build* a class string rather than pick a whole one?

    ``:class="toneClass"`` and ``:class="cond ? 'bg-a' : 'bg-b'"`` are fine: the
    complete utility names are present in the source, so Tailwind's content
    scanner finds them and Vue resolves the binding at build time -- the kit's
    own ``Panel.vue`` does exactly this and is correct. ``:class="'bg-' + tone"``
    and ``:class="`bg-${tone}`"`` are not: no complete name exists anywhere for
    the scanner to find, so the CSS is never generated.
    """
    return "+" in value or "`" in value or "${" in value


def _is_runtime_class(name, bare, value):
    """Rule 2: would this attribute produce a class no scanner ever saw?

    Two shapes: Chameleon computing the attribute at render time, and a Vue
    binding assembling the name out of fragments.
    """
    if name in ("tal:attributes", "tal:attribute"):
        return _assigns_class(value)
    return bare == "class" and name != "class" and _assembles_a_name(value)


def _attr_findings(name, value, line):
    """Rules 2, 3 and 4: what one attribute's own value gives away."""
    bare = name.lstrip("@:").removeprefix("v-bind:")
    if _is_runtime_class(name, bare, value):
        yield line, "runtime-class", f'{name}="{value}"'
    if bare == "style" and "${" in value:
        yield line, "style-placeholder", f'{name}="{value}"'
    if name == "class" and "${" in value:
        yield line, "class-placeholder", f'{name}="{value}"'


def _alt_findings(source, name, attrs, skeleton, offset):
    """Rule 5: an image with no ``alt``."""
    if name not in _IMAGE_TAGS:
        return
    present = {match.group(1) for match in _ATTR_NAME.finditer(skeleton)}
    if present & _ALT_ATTRS or _ALT_VIA_TAL.search(attrs):
        return
    yield line_at(source, offset), "missing-alt", f"<{name} ...>"


def _tag_body_findings(source, tag):
    """Every rule that is about one opening tag."""
    name = tag.group(1)
    attrs = tag.group(2)
    base = tag.start(2)
    skeleton = _blank_quoted_values(attrs)
    yield from _component_findings(source, name, skeleton, base)
    for match in _ATTR.finditer(attrs):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        line = line_at(source, base + match.start(1))
        yield from _attr_findings(match.group(1), value, line)
    yield from _alt_findings(source, name, attrs, skeleton, tag.start())


def _tag_findings(source, tag):
    """``_tag_body_findings`` with the tag's own first line as the opt-out anchor.

    The anchor is what lets a marker written above a multi-line tag suppress a
    violation found on one of its inner lines. See ``ignored_on``.
    """
    anchor = line_at(source, tag.start())
    for line, rule_id, detail in _tag_body_findings(source, tag):
        yield line, rule_id, detail, anchor


def _comment_findings(source, markup):
    """Rules 6 and 7: what is written inside a comment."""
    for match in _HTML_COMMENT.finditer(markup):
        inner = match.group(1)
        if _CONDITIONAL_COMMENT.search(inner):
            continue
        index = inner.find("--")
        if index >= 0:
            yield (
                line_at(source, match.start(1) + index),
                "comment-double-dash",
                _excerpt(inner),
            )
    # Rule 7 looks at *every* comment, including the ones inside <script> and
    # inside conditional comments, because Maizzle's rawExtract regex runs over
    # the raw file and has no idea what a comment is.
    for offset, text in _all_comments(source):
        hit = _RAW_MENTION.search(text)
        if hit:
            yield (
                line_at(source, offset + hit.start()),
                "raw-in-comment",
                # A window around the mention, not the whole comment: these are
                # often long prose blocks and the point is the six characters.
                _excerpt(text[max(0, hit.start() - 30) : hit.start() + 40]),
            )


def _all_comments(source):
    """``(offset, text)`` for every comment: HTML anywhere, JS inside scripts."""
    for match in _HTML_COMMENT.finditer(source):
        yield match.start(1), match.group(1)
    for offset, body in _script_bodies(source):
        for match in _JS_COMMENT.finditer(body):
            yield offset + match.start(), match.group(0)


def _placeholder_findings(source, markup):
    """Rule 8: a call inside a ``${...}`` that is a path expression."""
    scannable = _blank_spans(
        markup, [(m.start(1), m.end(1)) for m in _VUE_BOUND.finditer(markup)]
    )
    for match in _PLACEHOLDER.finditer(scannable):
        expression = match.group(1).strip()
        if "(" not in expression or expression.startswith(_NOT_A_PATH):
            continue
        yield line_at(source, match.start()), "path-call", "${" + expression + "}"


def _excerpt(text, limit=70):
    """One line of ``text``, shortened -- reports quote sources, not dump them."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


# ---------------------------------------------------------------------------
# The opt-out
# ---------------------------------------------------------------------------


def ignored_on(lines, line_number, anchor=None):
    """Rule ids opted out for a violation reported on ``line_number``.

    The marker counts on the reported line and on the line just above it, and --
    when ``anchor`` names the first line of the enclosing tag -- anywhere from
    just above that tag down to the reported line. An HTML comment cannot be
    written *inside* a tag, so without that span a violation on the fourth line
    of a multi-line tag would have nowhere to put a marker, and an author who
    cannot opt out deletes the whole gate instead.
    """
    first = min(line_number, anchor if anchor is not None else line_number) - 1
    ignored = set()
    for candidate in range(first, line_number + 1):
        if not 1 <= candidate <= len(lines):
            continue
        match = _IGNORE.search(lines[candidate - 1])
        if match:
            ignored.update(part.strip() for part in match.group(1).split(","))
    return ignored


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_source(source, path="<string>"):
    """Every violation in one ``.vue`` source, sorted by line then rule id."""
    markup = markup_only(source)
    findings = []
    for tag in _TAG.finditer(markup):
        findings.extend(_tag_findings(source, tag))
    # A comment or a bare `${...}` is its own opt-out anchor: there is no tag to
    # be trapped inside.
    for line, rule_id, detail in _comment_findings(source, markup):
        findings.append((line, rule_id, detail, line))
    for line, rule_id, detail in _placeholder_findings(source, markup):
        findings.append((line, rule_id, detail, line))

    lines = source.splitlines()
    violations = []
    for line, rule_id, detail, anchor in findings:
        ignored = ignored_on(lines, line, anchor)
        if rule_id in ignored or "all" in ignored:
            continue
        violations.append(Violation(str(path), line, RULES[rule_id], detail))
    return sorted(violations, key=lambda v: (v.line, v.rule.rule_id, v.detail))


def check_file(path):
    """Every violation in the ``.vue`` file at ``path``."""
    path = Path(path)
    return check_source(path.read_text(encoding="utf-8"), path)


def collect(paths):
    """``(files, missing)`` -- the ``.vue`` files under ``paths``.

    A directory is walked recursively, skipping ``node_modules``: pointing the
    lint at ``emails/`` should not spend a minute on Maizzle's own components.
    """
    files = []
    missing = []
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_dir():
            files.extend(
                sorted(
                    found
                    for found in candidate.rglob("*.vue")
                    if "node_modules" not in found.parts
                )
            )
        elif candidate.is_file():
            files.append(candidate)
        else:
            missing.append(raw)
    return files, missing


def report(violations, checked, stream=None):
    """Print ``violations`` and the summary. Returns the process exit code.

    ``stream`` is resolved here rather than in the signature: bound as a default
    it would capture whatever ``sys.stdout`` was at import time, which is not the
    stream a test (or a buildout script that redirects output) is watching.
    """
    stream = sys.stdout if stream is None else stream
    for violation in violations:
        print(violation, file=stream)
        print(file=stream)
    plural = "" if checked == 1 else "s"
    if not violations:
        print(f"emailkit-lint: {checked} file{plural}, no violations", file=stream)
        return 0
    affected = len({violation.path for violation in violations})
    count = len(violations)
    print(
        f"emailkit-lint: {count} violation{'' if count == 1 else 's'} in "
        f"{affected} of {checked} file{plural}.",
        file=stream,
    )
    print(
        "  Every rule above is a failure that produced a SUCCESSFUL build, so "
        "fixing it is\n  the only way it gets noticed before a mail client "
        f"does. `{IGNORE_HINT}<rule-id>`\n  in a comment on the offending line "
        "opts out one rule for one line; "
        "`--list-rules`\n  explains all of them.",
        file=stream,
    )
    return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _list_rules(stream=None):
    stream = sys.stdout if stream is None else stream
    for rule in RULES.values():
        print(f"{rule.rule_id}\n    what: {rule.what}", file=stream)
        print(f"    why:  {rule.why}\n    fix:  {rule.fix}\n", file=stream)
    return 0


def main(argv=None):
    """``python -m imio.emailkit.lint <paths>``. Non-zero if anything fired."""
    parser = argparse.ArgumentParser(
        prog="python -m imio.emailkit.lint",
        description=(
            "gate 2: check .vue email sources against the authoring "
            "rules. Every rule catches a mistake that compiles cleanly and "
            "fails silently at render time or in a mail client."
        ),
    )
    parser.add_argument("paths", nargs="*", help="`.vue` files, or directories to walk")
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="explain every rule and exit",
    )
    args = parser.parse_args(argv)

    if args.list_rules:
        return _list_rules()
    if not args.paths:
        parser.error("no paths given (use --list-rules to see the rules)")

    files, missing = collect(args.paths)
    if missing:
        for raw in missing:
            print(f"emailkit-lint: no such file or directory: {raw}", file=sys.stderr)
        return 2
    if not files:
        # A gate that silently passes because it looked at nothing is worse than
        # no gate: it is a green tick nobody can distinguish from a real one.
        print(
            "emailkit-lint: no .vue files found under "
            f"{' '.join(args.paths)} -- nothing was checked",
            file=sys.stderr,
        )
        return 2

    violations = []
    for path in files:
        violations.extend(check_file(path))
    return report(violations, len(files))


if __name__ == "__main__":
    sys.exit(main())
