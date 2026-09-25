"""Context data for ``imio.emailkit:user_migrated_to_sso``.

One key per placeholder and no more. The names ``render()`` injects (``lang``,
``theme`` and its tokens, ``portal_url``, ``preheader``) are absent on purpose:
pinning them here would hide a broken injection.

The values expose bugs rather than look tidy: an accented institution name, an
address long enough to make the card wrap, and a login url with a query string
that has to survive escaping.
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
