"""Shared constants and helpers for the test suite.

This module is also the single place where the suite states the **API contract it
was written against**. The tests were derived from the original design, not
from the implementation -- so where a behaviour is named but not a symbol, the
name is chosen here, once. If the runtime ends up exporting a different name,
this file is the only edit, and the mismatch is a finding to reconcile rather
than a test to weaken.

Contract encoded:

===============================================  ==========================
``imio.emailkit.render(name, context, language)`` returns ``(html, text)``
``imio.emailkit.interfaces.TemplateNotFound``     ``.name`` + ``.available``
``imio.emailkit.helpers.format_date`` etc.        locale helpers, ``(value, language)``
``imio.emailkit.interfaces.IEmailkitLayer``       browser layer
template name ``imio.emailkit:notification``      the one ``render()``-able template
``imio.emailkit.Email``                           the builder, spelled verbatim
``imio.emailkit.interfaces.IEmailRecipient``      ``email`` / ``fullname`` / ``language``
``imio.emailkit.interfaces.RecipientError``       raised at ``.send()``
``imio.emailkit.interfaces.AttachmentError``      raised at ``.send()``
view name ``emailkit-preview``                    spelled ``@@emailkit-preview``
``imio.emailkit.render_shell(subject, body_html)`` ``render()``'s sibling
===============================================  ==========================

Of those, four are **guesses this file owns** rather than quotations, and they
are listed again next to the code that makes them, so a wrong guess is one edit
here: which module the two new exceptions and the recipient interface live in
(:data:`INTERFACES_MODULE`), the preview view's language parameter
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
# Template names (namespaced ``<package>:<template>``)
# ---------------------------------------------------------------------------

# The suppression below is for S105: this is a template name, not a credential.
# Plone's own view is called `mail_password_template`, and renaming the constant
# to appease a linter would break the one property that makes these readable --
# they are the stock view names, verbatim.
# (This comment must not begin with the word ruff reads as a blanket directive,
# or the linter treats the whole comment as one.)
MAIL_PASSWORD = "mail_password_template"  # noqa: S105
REGISTERED_NOTIFY = "registered_notify_template"

#: The two Plone default mails whose *views* this package owns
#: (``imio.emailkit.browser.default_mails``).
#:
#: They were jbot overrides once, and the cost of that was a foreign dialect and
#: no discovery. Owning the view makes them ordinary registered templates, so they
#: appear in :data:`RENDERABLE_TEMPLATES` below as well; this tuple is what the
#: tests that go through the *stock calling convention* parametrise on
#: (``test_default_mails.py``, ``test_optout.py``).
DEFAULT_MAIL_TEMPLATES = (MAIL_PASSWORD, REGISTERED_NOTIFY)

#: Every template this package registers: the flat-context dialect, one set of
#: authoring rules, one preview list. Driven off discovery in the tests that can;
#: this tuple is for parametrisation, which needs values at import time.
#:
#: All four are here, which is the point of owning the views. ``get_username`` was
#: the first (stock Plone has no template for it, so jbot could not reach it and
#: the view was the only seam); the two default mails followed, because reaching
#: them with jbot was possible but made them second-class.
NOTIFICATION = "notification"
GET_USERNAME = "get_username"
RENDERABLE_TEMPLATES = (
    NOTIFICATION,
    GET_USERNAME,
    MAIL_PASSWORD,
    REGISTERED_NOTIFY,
)


def qualified(name):
    """``mail_password_template`` -> ``imio.emailkit:mail_password_template``."""
    return f"{PACKAGE_NAME}:{name}"


# ---------------------------------------------------------------------------
# The stock CMFPlone mails these two replace
# ---------------------------------------------------------------------------

#: Path fragment of the stock file each of our two views replaces. A ``:base``
#: site gets stock Plone's view, and therefore stock Plone's template; this is
#: what asserts that.
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

STOCK_BODY_MARKERS = {
    MAIL_PASSWORD: (
        "The following link will take you to a page where you can reset your password"
    ),
    REGISTERED_NOTIFY: "Your user account has been created",
}


# ---------------------------------------------------------------------------
# Kit-output markers -- these hold whatever markup the kit author chooses.
# ---------------------------------------------------------------------------

#: Accessibility default: ``role="presentation"`` on all layout tables.
A11Y_TABLE_MARKER = 'role="presentation"'

#: The layout emits ``lang="${lang}"`` on ``<html>``.
LANG_ATTRIBUTE = re.compile(r"<html[^>]*\blang=\"([a-zA-Z-]+)\"")

#: An inline ``style`` attribute carrying at least one CSS declaration.
INLINE_STYLE = re.compile(r'style="[^"]*[a-z-]+\s*:[^"]+"')

#: Phase 0 measured a comparable compiled template at **31** inline ``style``
#: attributes when inlining worked and **6** when caveat A1 had silently killed
#: it. Anything below this threshold means inlining died, not that the template
#: is small.
MIN_INLINE_STYLES = 10

#: The placeholder and TAL-residue patterns, and the assertion built on them, now
#: live in the **shipped** ``imio.emailkit.golden`` module: the base class is
#: exported for consumers as of Phase 4, and the audit is the half of it a consumer
#: needs most. They are reached through the thin delegations further down rather
#: than restated here -- two copies of this regex is exactly how one of them ends
#: up weaker than the other.


# ---------------------------------------------------------------------------
# Registry records (theming model)
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
    "this suite encodes at {section}; if the runtime chose another name, "
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

    Used only where a *behaviour* is pinned but not a *symbol*.
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
# Fixture data (``tests/fixtures/<template>.py``)
# ---------------------------------------------------------------------------


def fixture_path(template):
    return FIXTURES_DIR / f"{template}.py"


def load_fixture(template):
    """Return the ``CONTEXT`` dict of ``tests/fixtures/<template>.py``.

    Loaded by path rather than imported, so ``tests/fixtures/`` stays a
    directory of data files instead of becoming an importable package whose
    name would collide with the word "fixtures".
    """
    path = fixture_path(template)
    if not path.exists():
        raise FileNotFoundError(
            f"No fixture for {template!r}. One is required per template at {path}."
        )
    spec = importlib.util.spec_from_file_location(f"_emailkit_fixture_{template}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.CONTEXT)


def load_fixture_from(directory, template):
    """:func:`load_fixture` against another add-on's fixture directory.

    Used by the Phase 4 gates, whose fixtures belong to the two dummy consumer
    add-ons under ``tests/dummies/`` rather than to this package. Same loader --
    the one shipped in ``imio.emailkit.golden`` for consumers -- so a fixture that
    works for a dummy works for a real add-on.
    """
    from imio.emailkit.golden import load_fixture as shipped

    return shipped(Path(directory) / f"{template}.py")


def available_fixtures():
    return sorted(p.stem for p in FIXTURES_DIR.glob("*.py") if p.stem != "__init__")


# ---------------------------------------------------------------------------
# Golden files
# ---------------------------------------------------------------------------

#: Regeneration is **deliberate**, never a side effect of a failing comparison.
#: ``make update-golden`` sets this; so does ``EMAILKIT_UPDATE_GOLDEN=1 pytest``.
UPDATE_GOLDEN_ENV = "EMAILKIT_UPDATE_GOLDEN"

#: The one template the snapshot gate covers, and the one language it covers it
#: in. Not every template in every language, which is what this was.
#:
#: A byte-comparison of a whole rendered mail fails for two very different
#: reasons, and it had stopped distinguishing them. A real regression -- a purged
#: Tailwind class, a `${...}` that stopped resolving -- is one. The other is any
#: change at all to a shared layout, or a Plone point release that reflows the
#: markup a little, and that one arrived as eighteen failing files that all had
#: to be regenerated and read. Eighteen diffs nobody reads are worth less than
#: one diff somebody does.
#:
#: What still catches the first reason everywhere: `assert_render_is_clean` runs
#: on every rendered body in the suite (`test_render.py`, `test_i18n.py`,
#: `test_theme_tokens.py`, `test_preview.py` all render all four templates), and
#: `make check-emails` still compares the committed build byte for byte against a
#: fresh one. The snapshot is a smoke test for the rendering pipeline, not the
#: only thing standing between the kit and a broken mail.
GOLDEN_TEMPLATES = (NOTIFICATION,)

GOLDEN_LANGUAGES = ("fr",)


def updating_golden():
    from imio.emailkit.golden import updating_golden as shipped

    return shipped()


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

    Only for views that *have* an ``index``: stock Plone's own mail views (which
    is what a ``:base`` site gets) and the login-help form. This package's own
    default-mail views render through ``render()`` and have none; the equivalent
    lookup for those goes through ``imio.emailkit.render._page_template``.
    """
    return view.index.__func__


#: Fixture member identity, reused by every default-mail test.
MEMBER_FULLNAME = "Zoé Testeuse"
MEMBER_EMAIL = "zoe.testeuse@example.be"


def registered_subject(template):
    """The ``subject`` msgid a template's registration declares.

    The subject of a default mail is now a msgid in ``configure.zcml`` like every
    other subject in the package, not markup in a hand-emitted ``Subject:`` line.
    Comparing a rendered header against the translation of *this* is what proves
    the header came from our registration rather than from
    ``PasswordResetToolView``'s own ``mail_password_subject()``. A blacklist of
    stock subject strings could not do it: our msgid's English default is allowed
    to read exactly like Plone's, because it is the same mail.
    """
    from imio.emailkit.discovery import get_template

    return get_template(qualified(template)).subject


def stock_mail_view(portal, request, template):
    """Look the mail view up exactly the way ``RegistrationTool`` does.

    The context is ``portal_registration``, **not** the portal:
    ``Products/CMFPlone/RegistrationTool.py`` calls
    ``getMultiAdapter((self, self.REQUEST), name=...)``. Looking it up on the
    portal instead would still work but would not be the production path, and
    the whole point is that the *stock* view renders our file.
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
    from imio.emailkit.golden import unresolved_placeholders as shipped

    return shipped(rendered)


def assert_render_is_clean(rendered, what="output"):
    """No unsubstituted placeholder and no leftover TAL attribute.

    The single most important assertion in this suite. Phase 0: with the
    zope.tal fallback engine, ``${...}`` reaches the inbox verbatim and nothing
    raises -- so a test that only checks "our marker is present" ships raw
    placeholders to production and stays green.

    Delegated to the shipped ``imio.emailkit.golden`` since Phase 4 exported the
    base class: consumers get the same audit this suite runs, and there is one
    copy of it. Imported inside the function so ``require_runtime()`` still gets
    to report a missing package rather than this module failing to import.
    """
    from imio.emailkit.golden import assert_render_is_clean as shipped

    shipped(rendered, what)


# ===========================================================================
# Phase 2 -- the ``Email`` builder and the preview view
# ===========================================================================
#
# Everything below was written while the builder and the preview view were
# being written in parallel. Nothing here was derived from that code.

#: The frozen method set, verbatim, in the order the example chains them.
#: "Methods, and nothing beyond them" is the rule, and "no new builder
#: methods beyond the frozen set" is listed as a non-goal -- which is only
#: enforceable if a test names the closed set.
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

#: Every builder method except ``.send()`` returns ``self`` ("each method
#: returns ``self``"), so these are the ones an identity test can chain.
CHAINING_METHODS = tuple(name for name in BUILDER_METHODS if name != "send")

#: **GUESS.** ``RecipientError``, ``AttachmentError`` and
#: ``IEmailRecipient`` are named but not their module. Phase 1 put ``TemplateNotFound``
#: and ``IEmailkitLayer`` in ``imio.emailkit.interfaces`` ("Module where all
#: interfaces, events and exceptions live"), so that is where these are looked
#: for. If the runtime chose otherwise, change this one line.
INTERFACES_MODULE = "imio.emailkit.interfaces"

#: Verbatim: "``@@emailkit-preview`` (Manager-only)".
PREVIEW_VIEW = "emailkit-preview"

#: A language switcher is required but no parameter is named. Guessed as
#: ``language``, mirroring ``render(..., language=...)``, and since
#: **confirmed** against the view.
PREVIEW_LANGUAGE_PARAM = "language"

#: Likewise for the template selector.
PREVIEW_TEMPLATE_PARAM = "template"

#: A **Send test** button is required but no form control is named. Guessed as
#: ``send_test``; the view spells it ``form.button.send_test``, which is the
#: house convention, so this is the reconciled name rather than the guess.
SEND_TEST_BUTTON = "form.button.send_test"

SEND_TEST_FORM = {SEND_TEST_BUTTON: "Send test"}

#: The send test only fires on ``POST``. Not a detail mentioned elsewhere, and a
#: good call the tests have to honour: a URL that sends mail when merely
#: *fetched* is a URL a prefetcher, a link checker or somebody's browser history
#: eventually fetches.
SEND_TEST_METHOD = "POST"

#: The preview renders "each in an iframe using committed fixture data".
IFRAME_SRC = re.compile(r"<iframe[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Identities used across the Phase 2 modules
# ---------------------------------------------------------------------------

#: A recipient that is only ever an address -- no member behind it, so
#: :data:`IEmailRecipient`'s ``language`` is ``None`` for it and grouping
#: has to fall back to the site default.
PLAIN_ADDRESS = "greffe@commune.example.be"

#: A second one, for "two addresses land in one message" assertions.
OTHER_ADDRESS = "secretariat@commune.example.be"

#: Neither an address nor a userid. Unresolvable recipients "raise
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

#: "``From`` defaults to the site's configured sender". In Plone 6 that is
#: the pair of ``plone.app.registry`` records below, which is what the site
#: control panel writes.
SENDER_ADDRESS_RECORD = "plone.email_from_address"
SENDER_NAME_RECORD = "plone.email_from_name"
SITE_SENDER_ADDRESS = "noreply@commune.example.be"
SITE_SENDER_NAME = "Commune de Test"

#: An explicit ``.sender(...)`` override, distinct from the site default.
OVERRIDE_SENDER = "convocations@commune.example.be"

#: ``.reply_to(...)``, the address the builder's own example uses.
REPLY_TO = "noreply@imio.be"

#: The registry record Plone reads the site's default language from. Recipients
#: group by "resolved language"; the site default is the fallback for a
#: recipient that has none.
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

#: A literal ``.subject(...)`` override. ``.subject()`` "accepts a msgid or
#: literal string" -- a literal is not a msgid, so it must reach every language
#: group unchanged.
LITERAL_SUBJECT = "Convocation - seance du 12 aout"


def message_id(msgid, default=None):
    """A ``zope.i18nmessageid.Message`` in this package's domain."""
    from zope.i18nmessageid import Message

    return Message(msgid, domain=PACKAGE_NAME, default=default)


def translated(msgid, language):
    """Translate ``msgid`` for ``language`` the way a template would.

    Expected subjects are computed rather than hardcoded on purpose: the subject
    msgid is "translated per recipient language at send time", so
    the assertion has to be "equals the translation", not "equals this French
    string I typed". A hardcoded string would turn every catalog edit into a
    test failure and -- worse -- would still pass if the builder shipped the
    *bare msgid*, whenever the catalog happens to have no entry.
    """
    from zope.i18n import translate

    return translate(msgid, target_language=language)


def registration_subject(template=NOTIFICATION):
    """The subject msgid the registration declares for ``template``.

    Read out of discovery rather than restated here: the subject
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
    "{target} is not available. This module encodes the frozen Email builder "
    "API; the builder itself was written in parallel with these tests. Every "
    "assertion here is written and runs unchanged as soon as it lands -- "
    "nothing was weakened to go green. If it chose a different name, "
    "reconcile in tests/support.py ({hint})."
)


def require_builder():
    """Return ``imio.emailkit.Email`` or skip the calling module.

    ``Email`` is one of the few names spelled out literally
    (``from imio.emailkit import Email``), so there is nothing to guess --
    only to wait for.
    """
    require_runtime()
    import imio.emailkit

    email_class = getattr(imio.emailkit, "Email", None)
    if email_class is None:
        pytest.skip(
            _BUILDER_PENDING.format(
                target="imio.emailkit.Email",
                hint="the name is quoted verbatim, so this is W1 pending",
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
            f"@@{PREVIEW_VIEW} is not registered. The preview view was "
            "written in parallel with these tests; they run unchanged once "
            "it lands."
        )
    return view


# ---------------------------------------------------------------------------
# Reading a sent message
# ---------------------------------------------------------------------------
#
# Every helper here works on the *parsed* message. The MIME shape is pinned
# (``set_content(text)`` + ``add_alternative(html, subtype="html")``), and
# Phase 0's lesson is that marker-string assertions pass while raw ``${}`` ships
# -- so these return decoded content and structure, never a haystack to grep.


def sole(sent, what="message"):
    """Exactly one item, or a failure that says how many there were."""
    assert len(sent) == 1, f"expected exactly one {what}, got {len(sent)}"
    return sent[0]


def alternative_part(message):
    """The ``multipart/alternative`` section of a message.

    Returns the message itself when it *is* the alternative (the message shape
    with no attachments), or the nested one when ``add_attachment`` has wrapped it in
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
        "no multipart/alternative section in the message; "
        f"set_content(text) + add_alternative(html) is required: got {message.get_content_type()} "
        f"with parts {[p.get_content_type() for p in message.walk()]}"
    )


def body_parts(message):
    """The ``(text/plain, text/html)`` parts of the alternative, in wire order."""
    return list(alternative_part(message).iter_parts())


def decoded(part):
    """A text part's content, decoded and with line endings normalised.

    ``\\r\\n`` is the on-the-wire line ending; comparing against ``render()``'s
    output -- which is what the preview and the golden files also compare --
    means normalising it. That is a transport detail, not a value.
    """
    content = part.get_content()
    return content.replace("\r\n", "\n").rstrip("\n")


def bodies(message):
    """``(text, html)`` of one message, decoded."""
    parts = body_parts(message)
    assert len(parts) == 2, (
        "The builder's message has exactly two alternatives, text then html; got "
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


def envelope(record):
    """The bare addresses the SMTP layer was handed, lowercased.

    ``Products.MailHost`` runs every entry of ``toaddrs`` through
    ``formataddr``, so a recipient with a display name arrives as
    ``Frederic Wallon <fr.membre@commune.example.be>``. Parsed with
    ``getaddresses`` for the same reason :func:`addresses` is: comparing the
    formatted string would make an assertion about the display name that the
    test did not mean to make, and substring matching would accept
    ``...@commune.example.be.evil``.
    """
    from email.utils import getaddresses

    return sorted(
        address.lower()
        for _name, address in getaddresses([str(v) for v in record.recipients])
        if address
    )


def display_names(message, header):
    """The display names in one header (``IEmailRecipient.fullname``)."""
    from email.utils import getaddresses

    raw = message.get_all(header) or []
    return [name for name, _address in getaddresses([str(v) for v in raw]) if name]


def lang_of(message):
    """The ``lang`` attribute the kit layout emits on ``<html>``."""
    match = LANG_ATTRIBUTE.search(html_of(message))
    assert match, "no lang attribute on <html> in the sent message"
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


# ===========================================================================
# Phase 3 -- ``render_shell``
# ===========================================================================
#
# ``render_shell`` is the only new name, and its signature is spelled
# literally (``from imio.emailkit import render_shell``), so nothing below is a
# guess about the API -- only about test-local fixture names.

#: Verbatim: ``render_shell(subject, body_html, language=None)``.
#: A ``render()`` sibling, **not** a builder method -- "no new builder
#: methods" is listed as a non-goal, which is what
#: ``tests/test_builder.py::TestTheMethodSet`` already keeps closed.
SHELL_ARGUMENTS = ("subject", "body_html", "language")

#: Fixtures whose ``CONTEXT`` is a ``render_shell`` call rather than a template
#: context: ``{"subject": ..., "body_html": ...}``. They live in the same
#: directory and are loaded by the same :func:`load_fixture`, because
#: "fixture + snapshot per template" is the same contract -- the shell simply has
#: its markup handed in instead of authored.
SHELL_FIXTURES = ("shell_plonemeeting",)


def require_shell():
    """Return ``imio.emailkit.render_shell`` or skip the calling module.

    Coarse like :func:`require_builder`, and for the same reason: the name is
    quoted verbatim, so there is nothing to guess -- a missing name means the
    implementation is not there yet, and every assertion in the Phase 3 modules
    runs unchanged once it is.
    """
    require_runtime()
    import imio.emailkit

    function = getattr(imio.emailkit, "render_shell", None)
    if function is None:
        pytest.skip(
            "imio.emailkit.render_shell is not available. Its signature is "
            "spelled `from imio.emailkit import render_shell`; these tests "
            "encode that signature and were not weakened to go green.",
            allow_module_level=True,
        )
    return function


def load_shell_fixture(name):
    """``(subject, body_html)`` of a shell fixture.

    Keyed rather than positional so a fixture that forgets one of the two fails
    with the key name instead of with a tuple-unpacking error.
    """
    data = load_fixture(name)
    missing = [key for key in ("subject", "body_html") if key not in data]
    assert missing == [], (
        f"shell fixture {name!r} is missing {missing}; a shell fixture's CONTEXT "
        "is the render_shell(subject, body_html) call itself"
    )
    return data["subject"], data["body_html"]


#: The names ``render()`` puts in the template namespace:
#: the caller's context, the ``theme/*`` tokens, ``portal_url``, ``translate``,
#: the three locale helpers, ``lang`` -- plus ``preheader`` and the two names
#: ``render_shell`` itself binds. Used by the injection test: a ``${name}`` for
#: **each** of them goes into an injected body, and every one has to come back out
#: verbatim. Enumerated from the original design rather than read off the
#: implementation, so a name the runtime added silently is simply not covered
#: rather than rubber-stamped.
RENDER_NAMESPACE_NAMES = (
    "theme",
    "theme/primary_color",
    "theme/logo_url",
    "theme/footer_html",
    "lang",
    "portal_url",
    "translate",
    "format_date",
    "format_datetime",
    "format_number",
    "preheader",
    "subject",
    "body_html",
)

#: Zero-width and invisible characters the kit uses for layout (``&zwj;`` in an
#: Outlook spacer cell, the preheader's padding). Harmless in HTML, noise or
#: mojibake in a ``text/plain`` part -- so the plaintext gate asserts on them.
INVISIBLE_CHARACTERS = re.compile(
    "["
    "\u200b"  # zero-width space
    "\u200c"  # zero-width non-joiner
    "\u200d"  # zero-width joiner -- the kit's `&zwj;` Outlook spacer cell
    "\u2007"  # figure space -- the kit's preheader padding
    "\ufeff"  # zero-width no-break space
    "\u034f"  # combining grapheme joiner -- also preheader padding
    "]"
)

#: Anything that still looks like a tag. ``<`` alone is not enough: a plaintext
#: part may legitimately contain ``<`` from an unescaped ``&lt;`` in the source.
HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(\s[^<>]*)?/?>")


def head_of(html):
    """Everything before ``<body``: the part of the document the layout owns.

    The shell and an authored template are the same kit layout with different
    content, so their heads -- charset, viewport, colour-scheme meta, the
    dark-mode ``<style>``, the ``<html>`` attributes -- must be identical for the
    same language. Comparing the whole head rather than a handful of markers is
    the only form of "exactly as for an authored template" (gate 2) that a
    marker cannot fake.

    ``<title>`` is the one exclusion, and it is the narrowing the gate's own
    docstring anticipated. A title is *content*: the layout emits one when the
    render context carries a ``title`` name and none when the template supplies
    its heading as a translated slot instead, because Vue parses ``<title>`` as a
    rawtext element and escapes a slot written inside it (see
    ``kit/layouts/Main.vue``). So the shell, whose heading is a ``#title`` slot
    over ``${subject}``, legitimately has no title element while
    ``notification``, whose heading is runtime data, legitimately has one. That
    difference is the two templates differing, not the layout differing, and it
    is the only part of the head that varies with the context.
    """
    index = html.lower().find("<body")
    assert index != -1, "no <body> in the rendered document"
    return _TITLE_ELEMENT.sub("", html[:index])


_TITLE_ELEMENT = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)
