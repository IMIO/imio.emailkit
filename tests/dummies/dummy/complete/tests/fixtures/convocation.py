"""Context data for ``dummy.complete:convocation``.

``when`` is an ISO string, not a ``datetime``: ``format_date`` coerces both.
``cta_url`` is present, exercising the button's ``tal:condition`` in the true
direction; ``dummy.complete:notification`` omits it and covers the false one.
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
