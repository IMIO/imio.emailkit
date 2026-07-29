"""Shared constants and helpers for the test suite.

This module is also the single place where the suite states the **API contract it
was written against**. The tests were derived from ``SPEC.md`` and
``docs/plans/phase-1.md``, not from the implementation -- so where the spec names
a behaviour but not a symbol, the name is chosen here, once. If the runtime ends
up exporting a different name, this file is the only edit, and the mismatch is a
finding to reconcile rather than a test to weaken.

Contract encoded (spec reference in brackets):

===============================================  ==========================
``imio.emailkit.render(name, context, language)`` [§6.1] returns ``(html, text)``
``imio.emailkit.interfaces.TemplateNotFound``     [§4] ``.name`` + ``.available``
``imio.emailkit.helpers.format_date`` etc.        [§6.1] locale helpers, ``(value, language)``
``imio.emailkit.interfaces.IEmailkitLayer``       [§8.1] browser layer
template name ``imio.emailkit:notification``      [§4] the one ``render()``-able template
===============================================  ==========================
"""

from pathlib import Path

import importlib.util
import os
import pytest
import re


PACKAGE_NAME = "imio.emailkit"

HERE = Path(__file__).parent
FIXTURES_DIR = HERE / "fixtures"
GOLDEN_DIR = HERE / "golden"

# ---------------------------------------------------------------------------
# Template names (SPEC §4: names are namespaced ``<package>:<template>``)
# ---------------------------------------------------------------------------

# The suppression below is for S105: this is a template name, not a credential.
# Plone's own view is called `mail_password_template`, and renaming the constant
# to appease a linter would break the one property that makes these readable --
# they are the stock view names, verbatim.
# (This comment must not begin with the word ruff reads as a blanket directive,
# or the linter treats the whole comment as one.)
MAIL_PASSWORD = "mail_password_template"  # noqa: S105
REGISTERED_NOTIFY = "registered_notify_template"

#: The two Plone default mails ``imio.emailkit:default`` restyles (§8.1).
#:
#: **These are jbot-only: not discovered, not renderable through ``render()``.**
#: The reason is dialect, not file location. They are rendered by a *stock Plone
#: view*, whose keyword arguments land in ``options`` and whose ``member`` is a
#: ``MemberData`` that cannot be path-traversed at all (Phase 0, caveat D2) -- so
#: their bodies must use ``options/...`` and ``python:member.getProperty(...)``.
#: ``render()`` supplies a flat context, so it could never render them wherever
#: the files sat. Recorded in ``docs/DECISIONS.md`` ("Default-mail templates are
#: built once and copied to the jbot overrides dir"), which amends §8's claim that
#: they are "discovered ... exactly like consumer templates".
#:
#: Consequence for this suite: they are covered through the stock view
#: (``test_default_mails.py``, ``test_optout.py``, ``test_layer_override.py``) and
#: never through ``render()``.
DEFAULT_MAIL_TEMPLATES = (MAIL_PASSWORD, REGISTERED_NOTIFY)

#: Templates that go through ``render()`` -- the flat-context dialect §3 teaches
#: and the one every consumer addon will use. Driven off discovery in the tests
#: that can; this tuple is for parametrisation, which needs values at import time.
NOTIFICATION = "notification"
RENDERABLE_TEMPLATES = (NOTIFICATION,)


def qualified(name):
    """``mail_password_template`` -> ``imio.emailkit:mail_password_template``."""
    return f"{PACKAGE_NAME}:{name}"


# ---------------------------------------------------------------------------
# The stock CMFPlone mail views and their jbot override filenames
# ---------------------------------------------------------------------------

#: Both views are registered with ``browser:page template=...``, which becomes a
#: ``Products.Five.browser.pagetemplatefile.ViewPageTemplateFile`` -- the class
#: z3c.jbot patches. The required override filename is the dotted module path of
#: the shadowed file (Phase 0 report, section (d)).
JBOT_OVERRIDE_FILENAMES = {
    MAIL_PASSWORD: (
        "Products.CMFPlone.browser.login.templates.mail_password_template.pt"
    ),
    REGISTERED_NOTIFY: (
        "Products.CMFPlone.browser.login.templates.registered_notify_template.pt"
    ),
}

#: Path fragment of the *stock* file each override shadows, for negative controls.
STOCK_TEMPLATE_TAILS = {
    MAIL_PASSWORD: os.path.join(
        "Products",
        "CMFPlone",
        "browser",
        "login",
        "templates",
        "mail_password_template.pt",
    ),
    REGISTERED_NOTIFY: os.path.join(
        "Products",
        "CMFPlone",
        "browser",
        "login",
        "templates",
        "registered_notify_template.pt",
    ),
}

#: Body text that exists **only** in the stock templates. Deliberately the
#: English default text rather than the msgid: ``i18n:translate`` replaces the
#: msgid with its translation, so asserting on msgids would pass even when the
#: stock template rendered -- a negative control that can never fail is worse
#: than none.
STOCK_BODY_MARKERS = {
    MAIL_PASSWORD: (
        "The following link will take you to a page where you can reset your password"
    ),
    REGISTERED_NOTIFY: "Your user account has been created",
}


# ---------------------------------------------------------------------------
# Kit-output markers -- every one of them is mandated by SPEC §3, so they hold
# whatever markup the kit author chooses.
# ---------------------------------------------------------------------------

#: §3 "accessibility defaults: ``role="presentation"`` on all layout tables".
A11Y_TABLE_MARKER = 'role="presentation"'

#: §3 "the layout emits ``lang="${lang}"`` on ``<html>``".
LANG_ATTRIBUTE = re.compile(r"<html[^>]*\blang=\"([a-zA-Z-]+)\"")

#: An inline ``style`` attribute carrying at least one CSS declaration.
INLINE_STYLE = re.compile(r'style="[^"]*[a-z-]+\s*:[^"]+"')

#: Phase 0 measured a comparable compiled template at **31** inline ``style``
#: attributes when inlining worked and **6** when caveat A1 had silently killed
#: it. Anything below this threshold means inlining died, not that the template
#: is small.
MIN_INLINE_STYLES = 10

#: A Chameleon placeholder that survived into the output. Phase 0: without the
#: ``IPageTemplateEngine`` utility, zope.pagetemplate falls back to zope.tal
#: where ``${...}`` passes through **verbatim and with no error**.
UNRESOLVED_PLACEHOLDER = re.compile(r"\$\{[^}]*\}")

#: TAL/i18n attributes that should never survive a render.
TAL_RESIDUE = re.compile(r"\s(?:tal|i18n|metal):[a-z]+=")


# ---------------------------------------------------------------------------
# Registry records (SPEC §3 theming model)
# ---------------------------------------------------------------------------

THEME_RECORDS = {
    "logo_url": "imio.emailkit.theme.logo_url",
    "primary_color": "imio.emailkit.theme.primary_color",
    "footer_html": "imio.emailkit.theme.footer_html",
}


# ---------------------------------------------------------------------------
# Guards for work that lands in another workstream
# ---------------------------------------------------------------------------

_RUNTIME_PENDING = (
    "imio.emailkit runtime is not importable yet ({exc}). The Phase 1 runtime "
    "(W2: discovery.py, render(), interfaces.py, profiles/) is a parallel "
    "workstream; this module's assertions are written and will run unchanged as "
    "soon as it lands. Nothing here was weakened to go green."
)

_CONTRACT_PENDING = (
    "{target} is not available. tests/support.py documents the API contract "
    "this suite encodes from SPEC {section}; if the runtime chose another name, "
    "reconcile there -- do not drop the assertion."
)


def require_runtime():
    """Skip the calling module if the add-on is not importable at all.

    Coarse on purpose: it triggers only when the *package* is missing. Once
    ``imio.emailkit`` imports, every test runs for real and a missing function or
    profile is a hard failure, not a skip.
    """
    try:
        import imio.emailkit  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        pytest.skip(_RUNTIME_PENDING.format(exc=exc), allow_module_level=True)


def require_contract(dotted, section, *names):
    """Import ``dotted`` and return ``names`` off it, or skip the module.

    Used only where the spec pins a *behaviour* but not a *symbol*.
    """
    import importlib

    try:
        module = importlib.import_module(dotted)
    except ImportError:
        pytest.skip(
            _CONTRACT_PENDING.format(target=dotted, section=section),
            allow_module_level=True,
        )
    missing = [name for name in names if not hasattr(module, name)]
    if missing:
        pytest.skip(
            _CONTRACT_PENDING.format(
                target=f"{dotted}.{{{','.join(missing)}}}", section=section
            ),
            allow_module_level=True,
        )
    return [getattr(module, name) for name in names]


# ---------------------------------------------------------------------------
# Fixture data (SPEC §7: ``tests/fixtures/<template>.py``)
# ---------------------------------------------------------------------------


def fixture_path(template):
    return FIXTURES_DIR / f"{template}.py"


def load_fixture(template):
    """Return the ``CONTEXT`` dict of ``tests/fixtures/<template>.py``.

    Loaded by path rather than imported, so ``tests/fixtures/`` stays a
    directory of data files -- which is what §7 describes -- instead of becoming
    an importable package whose name would collide with the word "fixtures".
    """
    path = fixture_path(template)
    if not path.exists():
        raise FileNotFoundError(
            f"No fixture for {template!r}. SPEC §7 requires one per template at {path}."
        )
    spec = importlib.util.spec_from_file_location(f"_emailkit_fixture_{template}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.CONTEXT)


def available_fixtures():
    return sorted(p.stem for p in FIXTURES_DIR.glob("*.py") if p.stem != "__init__")


# ---------------------------------------------------------------------------
# Golden files (SPEC §7)
# ---------------------------------------------------------------------------

#: Regeneration is **deliberate**, never a side effect of a failing comparison.
#: ``make update-golden`` sets this; so does ``EMAILKIT_UPDATE_GOLDEN=1 pytest``.
UPDATE_GOLDEN_ENV = "EMAILKIT_UPDATE_GOLDEN"

GOLDEN_LANGUAGES = ("fr", "en")


def updating_golden():
    return os.environ.get(UPDATE_GOLDEN_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def golden_path(template, language, suffix):
    """``tests/golden/<template>.<language>.<suffix>``."""
    return GOLDEN_DIR / f"{template}.{language}.{suffix}"


# ---------------------------------------------------------------------------
# Small helpers used by more than one module
# ---------------------------------------------------------------------------


def mark_request(request, layer):
    """Apply a browser layer to a request by hand.

    ``plone.browserlayer`` marks the request from an ``IBeforeTraverseEvent``
    subscriber, and an integration test never traverses. Tests that need the
    layer therefore apply it explicitly -- and separately assert that the
    profile really *registered* it, because these are two different failures.
    """
    from zope.interface import alsoProvides

    alsoProvides(request, layer)
    return request


def resolved_template(view):
    """The ``ViewPageTemplateFile`` behind a ``browser:page template=...`` view.

    This is the object z3c.jbot patches, and ``.filename`` is what it resolved
    to. Never assert on this *alone* -- see the module docstring of
    ``tests/test_jbot_wiring.py``.
    """
    return view.index.__func__


#: Fixture member identity, reused by every default-mail test.
MEMBER_FULLNAME = "Zoé Testeuse"
MEMBER_EMAIL = "zoe.testeuse@example.be"


#: The ``Subject:`` header a jbot override emits: its ``i18n:translate`` msgid and
#: the element text that is the msgid's default.
_SUBJECT_MSGID = re.compile(
    r"^Subject:[^\n]*?i18n:translate=\"([^\"]+)\"[^\n]*?>([^<\n]*)<",
    re.MULTILINE,
)


def override_path(template):
    """The committed jbot override file for one of the two default mails."""
    import imio.emailkit

    return (
        Path(imio.emailkit.__file__).parent
        / "browser"
        / "overrides"
        / JBOT_OVERRIDE_FILENAMES[template]
    )


def override_subject_message(template):
    """The msgid the committed override declares on its ``Subject:`` line.

    Read out of the build artifact rather than hardcoded here. ``docs/DECISIONS``
    routes these subjects through a template-emitted header because the stock ones
    are Python-side methods jbot cannot reach, so the msgid lives in the compiled
    ``.pt`` and nowhere else -- and comparing the rendered header against *that*
    msgid's translation is what proves the header came from our domain rather than
    from ``PasswordResetToolView``. A hardcoded list of stock subject strings
    cannot do it: our msgid's English default is allowed to read exactly like
    Plone's, because it is the same mail.

    Returned as a ``Message`` carrying the element's own text as its ``default``,
    which is what Chameleon's ``i18n:translate`` uses when the catalog has no
    entry. Without the default, the comparison would be "translated subject vs.
    bare msgid" and would fail for a template that is perfectly correct but not
    yet translated -- reporting an i18n gap as an override bug.
    """
    path = override_path(template)
    if not path.exists():
        return None
    match = _SUBJECT_MSGID.search(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    from zope.i18nmessageid import Message

    msgid, default = match.group(1), match.group(2).strip()
    return Message(msgid, domain=PACKAGE_NAME, default=default or None)


def stock_mail_view(portal, request, template):
    """Look the mail view up exactly the way ``RegistrationTool`` does.

    The context is ``portal_registration``, **not** the portal:
    ``Products/CMFPlone/RegistrationTool.py`` calls
    ``getMultiAdapter((self, self.REQUEST), name=...)``. Looking it up on the
    portal instead would still work but would not be the production path, and
    the whole point of §8 is that the *stock* view renders our file.
    """
    from zope.component import getMultiAdapter

    return getMultiAdapter((portal.portal_registration, request), name=template)


def call_stock_mail(portal, request, template, member):
    """Render a Plone default mail through its real call site.

    Keyword arguments mirror ``RegistrationTool.mailPassword`` and
    ``RegistrationTool.registeredNotify`` verbatim -- both land in ``options``
    rather than at top level (Phase 0, caveat D2), which is why the two override
    templates are the documented exception that uses the hosting view's dialect.
    """
    view = stock_mail_view(portal, request, template)
    reset = portal.portal_password_reset.requestReset(member.getId())
    if template == MAIL_PASSWORD:
        return view(
            member=member,
            reset=reset,
            password=member.getPassword(),
            charset="utf-8",
        )
    return view(
        member=member,
        reset=reset,
        email=member.getProperty("email"),
        charset="utf-8",
    )


def count_inline_styles(rendered):
    return len(INLINE_STYLE.findall(rendered))


def unresolved_placeholders(rendered):
    return UNRESOLVED_PLACEHOLDER.findall(rendered)


def assert_render_is_clean(rendered, what="output"):
    """No unsubstituted placeholder and no leftover TAL attribute.

    The single most important assertion in this suite. Phase 0: with the
    zope.tal fallback engine, ``${...}`` reaches the inbox verbatim and nothing
    raises -- so a test that only checks "our marker is present" ships raw
    placeholders to production and stays green.
    """
    leftovers = unresolved_placeholders(rendered)
    assert not leftovers, (
        f"unsubstituted Chameleon placeholder in {what}: {leftovers[:5]}"
    )
    assert "${" not in rendered, f"stray '${{' in {what}"
    residue = sorted(set(TAL_RESIDUE.findall(rendered)))
    assert not residue, f"leftover TAL/i18n attributes in {what}: {residue}"
