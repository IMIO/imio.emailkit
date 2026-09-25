"""Context data for ``imio.emailkit:notification``.

Also what ``make preview-emails`` and ``@@emailkit-preview`` render, so it
stays realistic. ``lang``, ``theme`` and its tokens, and ``preheader`` are
absent, since ``render()`` supplies them and pinning them would hide a
broken injection.
"""

CONTEXT = {
    # Accented on purpose: a charset regression shows up here.
    "title": "Séance du conseil communal du 12 août",
    # Optional in the shell; present so its branch renders in the golden file.
    "subtitle": "Commune de Sambreville",
    "intro": (
        "La convocation pour la prochaine séance est disponible. "
        "Vous pouvez la consulter dès maintenant."
    ),
    "cta_label": "Consulter la convocation",
    "cta_url": "https://sambreville.example.be/seances/2026-08-12",
}
