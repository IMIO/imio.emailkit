"""Fixture data for the Phase 0 spike render.

Throwaway. The real fixture format (SPEC §7 `tests/fixtures/<template>.py`) is a
Phase 4 deliverable; this only has to satisfy every placeholder in
maizzle/emails/spike.vue.
"""


# Mappings rather than classes on purpose: Zope 2 path traversal enforces
# security declarations, so a plain Python class needs
# `__allow_access_to_unprotected_subobjects__` before `${member/fullname}` will
# resolve. Real Plone content and member objects carry those declarations; the
# spike sidesteps the question since it is testing markup, not traversal.
ITEM = {
    "title": "Point 3 - Budget 2026",
    "absolute_url": "https://commune.example.be/points/budget-2026",
    "is_urgent": True,
    "css_class": "urgent",
}

MEMBER = {
    "fullname": "Antoine Dupont",
    "email": "antoine.dupont@commune.example.be",
}


ROWS = [
    {"title": "Approbation du PV", "status": "decide"},
    {"title": "Budget 2026", "status": "reporte"},
    {"title": "Marche public - voirie", "status": "en cours"},
]

EXTRAS = [
    {"label": "Annexe 1"},
    {"label": "Annexe 2"},
]

CONTEXT = {
    "lang": "fr",
    "preheader": "Votre convocation pour la seance du 12 mars",
    "member": MEMBER,
    "item": ITEM,
    "items": ROWS,
    "extras": EXTRAS,
    "theme": {"primary_color": "#005ba1", "logo_url": "https://example.be/logo.png"},
    # SPEC §3 rule 4: `structure` is reserved for the shell's body_html slot.
    "body_html": "<p><strong>Corps HTML injecte</strong> via structure.</p>",
}
