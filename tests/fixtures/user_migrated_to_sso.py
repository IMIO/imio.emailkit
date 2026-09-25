"""Context data for ``imio.emailkit:user_migrated_to_sso``.

Names ``render()`` injects (``lang``, ``theme`` and its tokens,
``portal_url``, ``preheader``) are absent. Values are chosen to expose bugs:
an accented name, a long address, and a login url query string.
"""

CONTEXT = {
    "site_name": "Délibérations.be",
    "institution": "Commune de Braine-le-Château",
    "email": "prenom.nom@braine-le-chateau.example.be",
    "username": "pnom",
    "login_url": (
        "https://www.deliberations.example.be/acl_users/oidc/login"
        "?came_from=https%3A//www.deliberations.example.be/braine-le-chateau"
    ),
    "account_url": "https://auth.example.be/realms/deliberations/account/",
}
