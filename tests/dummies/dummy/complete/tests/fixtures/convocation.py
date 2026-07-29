"""Context data for ``dummy.complete:convocation`` (SPEC §7).

Note what the shape of this file teaches:

* ``when`` is an **ISO string**, not a ``datetime``. ``format_date`` coerces ISO
  strings and Zope ``DateTime`` objects, so a fixture stays plain data that a
  human can read in a diff.
* ``rows`` is a list of plain mappings, which is what ``tal:repeat`` +
  ``${row/title}`` needs. Real code passes real content objects; a fixture should
  not, because a plain Python instance would need
  ``__allow_access_to_unprotected_subobjects__`` before path traversal reached its
  attributes, and that is scaffolding with no test value.
* ``cta_url`` is present, so the ``tal:condition`` around the button is exercised
  in the *true* direction. ``dummy.minimal`` has no button at all and
  ``dummy.complete:notification`` omits the key, so the false direction is covered
  there -- one fixture cannot cover both branches of the same condition, and a
  branch nothing renders is a branch nothing tests.
"""

CONTEXT = {
    "title": "Convocation au conseil communal",
    "when": "2026-08-12T19:30:00",
    "place": "Salle du conseil, Hôtel de Ville",
    "rows": [
        {
            "title": "Budget 2026 - modification budgétaire n°2",
            "decision": "approuvé",
        },
        {
            "title": "Marché public - rénovation de l'école communale",
            "decision": "reporté",
        },
        {
            "title": "Règlement de police administrative",
            "decision": "approuvé",
        },
    ],
    "cta_label": "Consulter l'ordre du jour",
    "cta_url": "https://sambreville.example.be/seances/2026-08-12",
}
