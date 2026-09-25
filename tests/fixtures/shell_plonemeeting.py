"""A realistic PloneMeeting-shaped legacy body for ``render_shell``.

Snapshotted so a kit change that mangles legacy markup shows as a diff.
Idioms present: nested tables, ``bgcolor`` zebra rows, inline ``style``, a
styled ``<a>``, ``&nbsp;``/``&laquo;``/``&raquo;``, unclosed ``<br>``/``<hr>``,
and ``<b>`` instead of ``<strong>`` -- all real PloneMeeting output, since
notifications are assembled by string concatenation, not templates.

Whitespace matters: the data table's rows have no newline between cells,
which is the only shape where the plaintext extraction's cell separator is
observable.

No ``${...}`` and no ``<html>``/unclosed-tag pathology: both belong in
``tests/test_render_shell.py`` instead, where broken input is asserted on,
not frozen into a snapshot.

``subject`` is a literal string, not a msgid, matching what PloneMeeting
actually passes.
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
