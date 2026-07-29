"""A realistic PloneMeeting-shaped legacy body for ``render_shell`` (§9 phase 3).

``docs/plans/phase-3.md`` §1 makes this fixture the *evidence* for the phase's
central claim -- "zero template redesign" -- and §4 gate 4 asks for exactly this:
a body carrying "the actual HTML idioms those notifications emit", snapshotted so
that a change to the kit which quietly mangles legacy markup shows up as a diff.

So the shape below is not decoration. Every idiom in it is one PloneMeeting
notifications really produce, because they are assembled by string concatenation
out of `MeetingConfig` mail texts and item data rather than authored as templates:

* **nested tables** -- an outer layout table wrapping an inner data table, the
  1990s way of getting a border and padding in Outlook;
* **``bgcolor`` rows** -- zebra striping done with the presentational attribute,
  not CSS, which is also what the kit itself has to do for Outlook
  (``docs/DECISIONS.md``, "theme tokens colour cells via ``bgcolor``");
* **inline ``style``** on cells and paragraphs, unrelated to and unaware of the
  kit's own inlined CSS -- the collision the plan wants proof about;
* **a styled ``<a>``** with its own colour and underline, which is what makes
  "does the legacy link still look like a link inside our shell" answerable;
* **``&nbsp;``** (French typography uses it before ``:`` and inside quotes) and
  **``&laquo;``/``&raquo;``**, so an entity that the plaintext extraction has to
  unescape is present;
* **a bare ``<br>``** and a bare ``<hr>`` -- void elements written unclosed, which
  is legal HTML and invalid XML, and therefore the interesting case for anything
  that might try to re-parse the body;
* **``<b>``** rather than ``<strong>``, because that is what the legacy editor
  emitted.

**Whitespace is part of the fixture.** The data table's rows are written on one
line each, with no newline between cells, because that is what
``'<tr><td>%s</td><td>%s</td></tr>' % (...)`` in a loop produces -- and it is the
only shape in which the plaintext extraction's cell separator is observable at
all: a newline between cells leaves the separator at end of line, where
``naive_text`` strips it (``docs/DECISIONS.md``, "Plaintext: table cells get a
`` | `` separator"). The surrounding layout tables keep their indentation, because
the other half of a legacy body comes from a rich-text field that has newlines.
Both shapes therefore go through the golden.

Two things are deliberately **absent**.

* **No ``${...}``.** A legacy body may well contain one -- that is the security
  question of this phase -- but it belongs in ``tests/test_render_shell.py``,
  where the assertion is that it survives *verbatim*. Putting one here would make
  the golden harness's own ``test_golden_has_no_unresolved_placeholder`` fire,
  which exists to catch a snapshot taken on a broken engine and must keep meaning
  exactly that.
* **No ``<html>``/``<style>``/unclosed-tag pathology.** Also in
  ``test_render_shell.py`` (gate 6): those cases are about *what the shell does
  with broken input*, and a snapshot of broken input would freeze the current
  answer instead of asserting it.

``subject`` is a **literal string**, not a msgid, because that is what a legacy
caller has: PloneMeeting computes the subject from the item and the meeting date
before it ever reaches us. §6.2's "a msgid or a literal" is exercised on the msgid
side by ``test_render_shell.py``'s language gate.
"""

CONTEXT = {
    "subject": "Point publié : Approbation du budget 2026",
    "body_html": (
        "<p>Bonjour,</p>\n"
        "<p>Le point"
        ' <a href="https://sambreville.example.be/seances/2026-08-12/budget-2026"'
        ' style="color: #005a9c; text-decoration: underline;">'
        "Approbation du budget 2026</a>"
        " a été publié dans la séance du conseil communal du 12 août 2026.</p>\n"
        '<table border="1" cellpadding="4" cellspacing="0"'
        ' style="border-collapse: collapse; width: 100%;">\n'
        '  <tr bgcolor="#eeeeee"><td><b>Point</b></td>'
        "<td><b>Décision</b></td></tr>\n"
        "  <tr><td>1.&nbsp;Budget 2026</td><td>Approuvé</td></tr>\n"
        '  <tr bgcolor="#f7f7f7">'
        "<td>2.&nbsp;Marché public&nbsp;: réfection de la voirie</td>"
        "<td>Reporté</td></tr>\n"
        "</table>\n"
        '<table cellpadding="0" cellspacing="0" width="100%">\n'
        "  <tr>\n"
        '    <td style="padding-top: 8px;">\n'
        '      <table border="0" cellpadding="2" cellspacing="0">\n'
        "        <tr>\n"
        '          <td style="font-size: 11px; color: #666666;">'
        "Annexes&nbsp;: 2 documents</td>\n"
        "        </tr>\n"
        "      </table>\n"
        "    </td>\n"
        "  </tr>\n"
        "</table>\n"
        '<p style="margin-top: 12px;">Cordialement,<br>Le secrétariat communal</p>\n'
        "<hr>\n"
        "<p><small>Vous recevez ce message parce que vous êtes membre du groupe"
        " &laquo;&nbsp;Conseil communal&nbsp;&raquo;.</small></p>"
    ),
}
