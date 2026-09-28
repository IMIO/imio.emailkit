"""Context data for ``imio.emailkit:user_migrated_to_sso``.

Names ``render()`` injects (``lang``, ``theme`` and its tokens,
``portal_url``, ``preheader``) are absent. Values are chosen to expose bugs:
an accented name and a long address.
"""

CONTEXT = {
    "site_name": "Délibérations.be",
    "institution": "Commune de Braine-le-Château",
    "email": "prenom.nom@braine-le-chateau.example.be",
    "username": "pnom",
    "account_url": "https://auth.example.be/realms/deliberations/account/",
}
