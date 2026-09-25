"""Context data for ``dummy.minimal:notification``.

One key per ``${...}`` in the template. Names ``render()`` supplies
(``lang``, ``theme`` and its tokens, ``preheader``) are absent.
"""

CONTEXT = {
    # Accented on purpose: a charset regression shows up here.
    "title": "Votre demande a été enregistrée",
    "intro": (
        "Nous avons bien reçu votre demande. Un agent du service population "
        "la traitera dans les cinq jours ouvrables."
    ),
}
