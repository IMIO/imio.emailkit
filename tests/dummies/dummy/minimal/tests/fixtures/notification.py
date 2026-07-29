"""Context data for ``dummy.minimal:notification`` (SPEC §7).

One key per ``${...}`` in the template and nothing else. This dict *is* the
contract between the template and the test suite: add a placeholder to the
template without adding the key here and the golden test fails loudly, which is
the whole point.

Names ``render()`` supplies are deliberately absent -- ``lang``, ``theme`` and its
three tokens, ``preheader``. Pinning them here would hide a broken injection and
would pin every snapshot to one language.

Plain strings, not objects: ``render()``'s context is a flat mapping and Zope path
traversal enforces security declarations, so a plain Python instance would need
``__allow_access_to_unprotected_subobjects__`` before ``${item/title}`` resolved.
"""

CONTEXT = {
    # Accented, non-ASCII text on purpose: a charset regression in the compiled
    # output or in the render shows up here and nowhere else.
    "title": "Votre demande a été enregistrée",
    "intro": (
        "Nous avons bien reçu votre demande. Un agent du service population "
        "la traitera dans les cinq jours ouvrables."
    ),
}
