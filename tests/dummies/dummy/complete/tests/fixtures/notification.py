"""Context data for ``dummy.complete:notification``.

``cta_url`` and ``cta_label`` are absent, exercising the false branch of the
button's ``tal:condition``; ``convocation.py`` covers the true one.
"""

CONTEXT = {
    "title": "Votre dossier a progressé",
    "intro": (
        "Le service urbanisme a validé votre demande de permis. "
        "Vous serez recontacté dès que l'enquête publique sera clôturée."
    ),
    "reference": "Référence du dossier : URB-2026-0417",
}
