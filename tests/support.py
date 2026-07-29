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
``imio.emailkit.Email``                           [§6.2] the builder, spelled verbatim in the spec
``imio.emailkit.interfaces.IEmailRecipient``      [§6.2] ``email`` / ``fullname`` / ``language``
``imio.emailkit.interfaces.RecipientError``       [§6.2] raised at ``.send()``
``imio.emailkit.interfaces.AttachmentError``      [§6.2] raised at ``.send()``
view name ``emailkit-preview``                    [§6.3] spelled ``@@emailkit-preview``
===============================================  ==========================

Of those, four are **guesses this file owns** rather than spec quotations, and
they are listed again next to the code that makes them, so a wrong guess is one
edit here: which module the two new exceptions and the recipient interface live
in (:data:`INTERFACES_MODULE`), the preview view's language parameter
(:data:`PREVIEW_LANGUAGE_PARAM`) and its send-test trigger
(:data:`SEND_TEST_FORM`).
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


# ===========================================================================
# Phase 2 -- SPEC §6.2 (``Email`` builder) and §6.3 (preview view)
# ===========================================================================
#
# Everything below was written against SPEC §6.2/§6.3 and
# ``docs/plans/phase-2.md`` §6 while the builder and the preview view were being
# written in parallel. Nothing here was derived from that code.

#: §6.2's frozen method set, verbatim, in the order the spec's own example
#: chains them. ``docs/plans/phase-2.md`` §2: "Methods, and nothing beyond
#: them", and §7 lists "no new builder methods beyond §6.2" as a non-goal --
#: which is only enforceable if a test names the closed set.
BUILDER_METHODS = (
    "to",
    "cc",
    "bcc",
    "reply_to",
    "sender",
    "subject",
    "with_context",
    "attach",
    "send",
)

#: Every builder method except ``.send()`` returns ``self`` (§6.2: "each method
#: returns ``self``"), so these are the ones an identity test can chain.
CHAINING_METHODS = tuple(name for name in BUILDER_METHODS if name != "send")

#: **GUESS.** §6.2 names ``RecipientError``, ``AttachmentError`` and
#: ``IEmailRecipient`` but not their module. Phase 1 put ``TemplateNotFound``
#: and ``IEmailkitLayer`` in ``imio.emailkit.interfaces`` ("Module where all
#: interfaces, events and exceptions live"), so that is where these are looked
#: for. If the runtime chose otherwise, change this one line.
INTERFACES_MODULE = "imio.emailkit.interfaces"

#: §6.3, verbatim: "``@@emailkit-preview`` (Manager-only)".
PREVIEW_VIEW = "emailkit-preview"

#: **GUESS.** §6.3 requires "a language switcher" but names no parameter. This
#: mirrors §6.1's ``render(..., language=...)``, which is the only language
#: keyword the spec spells anywhere.
PREVIEW_LANGUAGE_PARAM = "language"

#: **GUESS.** §6.3 requires "a **Send test** button" but names no form control.
#: A single request key is assumed; the *behaviour* asserted around it -- the
#: mail goes to the logged-in user's own address and nowhere else -- is the part
#: the spec actually pins.
SEND_TEST_FORM = {"send_test": "1"}

#: §6.3: the preview renders "each in an iframe using committed fixture data".
IFRAME_SRC = re.compile(r"<iframe[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Identities used across the Phase 2 modules
# ---------------------------------------------------------------------------

#: A recipient that is only ever an address -- no member behind it, so
#: :data:`IEmailRecipient`'s ``language`` is ``None`` for it and §6.2's grouping
#: has to fall back to the site default (``docs/plans/phase-2.md`` §4).
PLAIN_ADDRESS = "greffe@commune.example.be"

#: A second one, for "two addresses land in one message" assertions.
OTHER_ADDRESS = "secretariat@commune.example.be"

#: Neither an address nor a userid. §6.2: unresolvable recipients "raise
#: ``RecipientError`` at ``.send()`` time (fail loud, not silent drop)".
UNRESOLVABLE = "definitely-not-a-user-or-an-address"
OTHER_UNRESOLVABLE = "also-not-a-user-or-an-address"

#: The two extra members the language-grouping tests need. Userids rather than
#: addresses so the same fixtures exercise the userid branch of the ``str``
#: adapter as well.
FR_MEMBER = {
    "userid": "fr_member",
    "email": "fr.membre@commune.example.be",
    "fullname": "Frederic Wallon",
    "language": "fr",
}
NL_MEMBER = {
    "userid": "nl_member",
    "email": "nl.lid@gemeente.example.be",
    "fullname": "Niels Vlaming",
    "language": "nl",
}

#: §6.2: "``From`` defaults to the site's configured sender". In Plone 6 that is
#: the pair of ``plone.app.registry`` records below, which is what the site
#: control panel writes.
SENDER_ADDRESS_RECORD = "plone.email_from_address"
SENDER_NAME_RECORD = "plone.email_from_name"
SITE_SENDER_ADDRESS = "noreply@commune.example.be"
SITE_SENDER_NAME = "Commune de Test"

#: An explicit ``.sender(...)`` override, distinct from the site default.
OVERRIDE_SENDER = "convocations@commune.example.be"

#: ``.reply_to(...)``, the address §6.2's own example uses.
REPLY_TO = "noreply@imio.be"

#: The registry record Plone reads the site's default language from. §6.2 groups
#: by "resolved language"; ``docs/plans/phase-2.md`` §4 makes the site default
#: the fallback for a recipient that has none.
DEFAULT_LANGUAGE_RECORD = "plone.default_language"


# ---------------------------------------------------------------------------
# Subjects: expected values are *translated*, never hardcoded
# ---------------------------------------------------------------------------

#: A second msgid in this package's own domain, used to prove ``.subject(msgid)``
#: is translated per language group. Chosen because its FR and NL catalog
#: entries genuinely differ -- ``email_subject_notification`` translates to
#: "Notification" in both FR and EN, so it cannot distinguish "translated" from
#: "passed through".
OVERRIDE_SUBJECT_MSGID = "email_subject_mail_password_template"

#: A literal ``.subject(...)`` override. §6.2: ``.subject()`` "accepts a msgid or
#: literal string" -- a literal is not a msgid, so it must reach every language
#: group unchanged.
LITERAL_SUBJECT = "Convocation - seance du 12 aout"


def message_id(msgid, default=None):
    """A ``zope.i18nmessageid.Message`` in this package's domain."""
    from zope.i18nmessageid import Message

    return Message(msgid, domain=PACKAGE_NAME, default=default)


def translated(msgid, language):
    """Translate ``msgid`` for ``language`` the way a template would.

    Expected subjects are computed rather than hardcoded on purpose: §6.2 says
    the subject msgid is "translated per recipient language at send time", so
    the assertion has to be "equals the translation", not "equals this French
    string I typed". A hardcoded string would turn every catalog edit into a
    test failure and -- worse -- would still pass if the builder shipped the
    *bare msgid*, whenever the catalog happens to have no entry.
    """
    from zope.i18n import translate

    return translate(msgid, target_language=language)


def registration_subject(template=NOTIFICATION):
    """The subject msgid the §4 registration declares for ``template``.

    Read out of discovery rather than restated here: §6.2 says the subject
    "comes from the template registration", so the test's expectation must be
    whatever the registration holds. Restating it would let the two drift apart
    and still pass.
    """
    from imio.emailkit.discovery import get_template

    return get_template(qualified(template)).subject


# ---------------------------------------------------------------------------
# Guards for the two Phase 2 workstreams
# ---------------------------------------------------------------------------

_BUILDER_PENDING = (
    "{target} is not available. SPEC §6.2 freezes the Email builder's API and "
    "this module encodes it; the builder itself is workstream W1 of "
    "docs/plans/phase-2.md and is written in parallel with these tests. Every "
    "assertion here is written and runs unchanged as soon as W1 lands -- "
    "nothing was weakened to go green. If W1 chose a different name, reconcile "
    "in tests/support.py ({hint})."
)


def require_builder():
    """Return ``imio.emailkit.Email`` or skip the calling module.

    ``Email`` is one of the few names SPEC spells literally
    (§6.2: ``from imio.emailkit import Email``), so there is nothing to guess --
    only to wait for.
    """
    require_runtime()
    import imio.emailkit

    email_class = getattr(imio.emailkit, "Email", None)
    if email_class is None:
        pytest.skip(
            _BUILDER_PENDING.format(
                target="imio.emailkit.Email",
                hint="the name is quoted verbatim from §6.2, so this is W1 pending",
            ),
            allow_module_level=True,
        )
    return email_class


def require_errors(*names):
    """Return the named Phase 2 exceptions/interfaces or skip the module."""
    require_runtime()
    import importlib

    module = importlib.import_module(INTERFACES_MODULE)
    missing = [name for name in names if not hasattr(module, name)]
    if missing:
        pytest.skip(
            _BUILDER_PENDING.format(
                target=f"{INTERFACES_MODULE}.{{{','.join(missing)}}}",
                hint="support.INTERFACES_MODULE picks the module -- a GUESS",
            ),
            allow_module_level=True,
        )
    return [getattr(module, name) for name in names]


def require_preview(portal, request):
    """Return the ``@@emailkit-preview`` view class or skip the module.

    Looked up unrestricted, so a *missing* view (W2 pending) is a skip while a
    *protected* view is not -- the Manager-only assertions in
    ``tests/test_preview.py`` must be able to fail, not vanish into a skip.
    """
    require_runtime()
    from zope.component import queryMultiAdapter

    view = queryMultiAdapter((portal, request), name=PREVIEW_VIEW)
    if view is None:
        pytest.skip(
            f"@@{PREVIEW_VIEW} is not registered. SPEC §6.3's preview view is "
            "workstream W2 of docs/plans/phase-2.md, written in parallel with "
            "these tests; they run unchanged once it lands."
        )
    return view


# ---------------------------------------------------------------------------
# Reading a sent message
# ---------------------------------------------------------------------------
#
# Every helper here works on the *parsed* message. SPEC §6.2 pins the MIME
# shape (``set_content(text)`` + ``add_alternative(html, subtype="html")``), and
# Phase 0's lesson is that marker-string assertions pass while raw ``${}`` ships
# -- so these return decoded content and structure, never a haystack to grep.


def sole(sent, what="message"):
    """Exactly one item, or a failure that says how many there were."""
    assert len(sent) == 1, f"expected exactly one {what}, got {len(sent)}"
    return sent[0]


def alternative_part(message):
    """The ``multipart/alternative`` section of a message.

    Returns the message itself when it *is* the alternative (§6.2's shape with
    no attachments), or the nested one when ``add_attachment`` has wrapped it in
    a ``multipart/mixed`` -- which is what ``EmailMessage`` does, and is correct.
    Written to accept both so the attachment tests can still assert on the body
    structure without re-deriving it.
    """
    if message.get_content_type() == "multipart/alternative":
        return message
    for part in message.walk():
        if part.get_content_type() == "multipart/alternative":
            return part
    raise AssertionError(
        "no multipart/alternative section in the message; SPEC §6.2 requires "
        f"set_content(text) + add_alternative(html): got {message.get_content_type()} "
        f"with parts {[p.get_content_type() for p in message.walk()]}"
    )


def body_parts(message):
    """The ``(text/plain, text/html)`` parts of the alternative, in wire order."""
    return list(alternative_part(message).iter_parts())


def decoded(part):
    """A text part's content, decoded and with line endings normalised.

    ``\\r\\n`` is the on-the-wire line ending; comparing against ``render()``'s
    output -- which is what §6.3's preview and §7's golden files also compare --
    means normalising it. That is a transport detail, not a value.
    """
    content = part.get_content()
    return content.replace("\r\n", "\n").rstrip("\n")


def bodies(message):
    """``(text, html)`` of one message, decoded."""
    parts = body_parts(message)
    assert len(parts) == 2, (
        "SPEC §6.2's message has exactly two alternatives, text then html; got "
        f"{[p.get_content_type() for p in parts]}"
    )
    return decoded(parts[0]), decoded(parts[1])


def html_of(message):
    return bodies(message)[1]


def attachments(message):
    """Every attachment part, in order."""
    return list(message.iter_attachments())


def addresses(message, header):
    """The bare addresses in one header, lowercased.

    Parsed with ``email.utils.getaddresses`` rather than by substring, because
    ``"Zoe Testeuse" <zoe@example.be>`` must match ``zoe@example.be`` and
    ``zoe@example.be.evil`` must not.
    """
    from email.utils import getaddresses

    raw = message.get_all(header) or []
    return sorted(
        address.lower() for _name, address in getaddresses([str(v) for v in raw])
    )


def display_names(message, header):
    """The display names in one header (``IEmailRecipient.fullname``, §6.2)."""
    from email.utils import getaddresses

    raw = message.get_all(header) or []
    return [name for name, _address in getaddresses([str(v) for v in raw]) if name]


def lang_of(message):
    """The ``lang`` attribute the kit layout emits on ``<html>`` (§3)."""
    match = LANG_ATTRIBUTE.search(html_of(message))
    assert match, "no lang attribute on <html> in the sent message (SPEC §3)"
    return match.group(1).lower()


def subject_of(message):
    return str(message["Subject"])


def assert_message_is_clean(message):
    """Neither MIME part may carry an unsubstituted placeholder.

    The same assertion ``tests/test_render.py`` makes, applied to what actually
    goes to the MTA. A builder that assembled the message from something other
    than ``render()`` -- or before the engine was ready -- fails here.
    """
    text, html = bodies(message)
    assert_render_is_clean(html, "sent html part")
    assert_render_is_clean(text, "sent text part")
