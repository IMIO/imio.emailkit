"""Context data for ``dummy.complete:notification``.

``cta_url`` is deliberately **absent**: the template guards the button with
``tal:condition="cta_url | nothing"``, and this fixture is what exercises the
false branch. ``convocation.py`` supplies it and exercises the true one.

``cta_label`` is absent for the same reason -- if the condition ever stopped
guarding the block, a missing ``cta_label`` would surface as a render error rather
than as a button with an empty label, which is the louder of the two failures.
"""

CONTEXT = {
    "title": "Votre dossier a progressé",
    "intro": (
        "Le service urbanisme a validé votre demande de permis. "
        "Vous serez recontacté dès que l'enquête publique sera clôturée."
    ),
    "reference": "Référence du dossier : URB-2026-0417",
}
