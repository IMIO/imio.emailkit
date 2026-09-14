"""Context data for ``imio.emailkit:notification`` (SPEC §7).

The fixture is the *contract* between the template author and the test suite: a
placeholder added to the template without a matching key here makes the golden
test fail loudly, which is the point. It is also what ``make preview-emails``
(§5) and ``@@emailkit-preview`` (§6.3) render, so keeping it realistic is not
cosmetic -- it is the data every developer will look at.

Four names are deliberately **absent**, because ``render()`` supplies them and a
fixture that pinned them would hide a broken injection:

* ``lang`` -- the render language (§6.1). Hardcoding it would pin every golden
  file to one language and make a broken ``language=`` argument invisible.
* ``theme`` / ``logo_url`` / ``primary_color`` / ``footer_html`` -- injected from
  ``plone.app.registry`` (§3), which is exactly what
  ``tests/test_theme_tokens.py`` varies.
* ``preheader`` -- comes from the *registration* (§4), not from the caller.

Plain strings rather than objects: ``render()``'s context is a flat mapping, and
Zope path traversal enforces security declarations, so a plain Python instance
would need ``__allow_access_to_unprotected_subobjects__`` before
``${item/title}`` resolved. Real content objects carry those declarations; test
data has no reason to.
"""

CONTEXT = {
    # Accented and non-ASCII on purpose: a charset regression in the compiled
    # output or in the render shows up here and nowhere else.
    "title": "Séance du conseil communal du 12 août",
    # The banner's second line. Optional in the shell, so a fixture that omitted
    # it would leave the v2 layout's `subtitle` branch unrendered in every golden
    # file -- and an unrendered branch is one nobody notices breaking.
    "subtitle": "Commune de Sambreville",
    "intro": (
        "La convocation pour la prochaine séance est disponible. "
        "Vous pouvez la consulter dès maintenant."
    ),
    "cta_label": "Consulter la convocation",
    "cta_url": "https://sambreville.example.be/seances/2026-08-12",
}
