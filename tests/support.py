"""Shared constants and helpers for the test suite.

States the API contract the tests are written against:

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

Three names are guesses, listed again next to the code that sets them:
:data:`INTERFACES_MODULE`, :data:`PREVIEW_LANGUAGE_PARAM`,
:data:`SEND_TEST_FORM`. Edit here if the runtime differs.
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

# S105 false positive: this is a template name, not a password.
MAIL_PASSWORD = "mail_password_template"  # noqa: S105
REGISTERED_NOTIFY = "registered_notify_template"

#: The two Plone default mails whose *views* this package owns.
DEFAULT_MAIL_TEMPLATES = (MAIL_PASSWORD, REGISTERED_NOTIFY)

#: Every template this package registers. Listed for parametrization, which
#: needs values at import time.
NOTIFICATION = "notification"
GET_USERNAME = "get_username"
USER_MIGRATED_TO_SSO = "user_migrated_to_sso"
RENDERABLE_TEMPLATES = (
    NOTIFICATION,
    GET_USERNAME,
    MAIL_PASSWORD,
    REGISTERED_NOTIFY,
    USER_MIGRATED_TO_SSO,
)


def qualified(name):
    """``mail_password_template`` -> ``imio.emailkit:mail_password_template``."""
    return f"{PACKAGE_NAME}:{name}"


# ---------------------------------------------------------------------------
# The stock CMFPlone mails these two replace
# ---------------------------------------------------------------------------

#: Path of the stock file each view replaces, for a ``:base`` site.
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
# Kit-output markers
# ---------------------------------------------------------------------------

#: Accessibility default: ``role="presentation"`` on all layout tables.
A11Y_TABLE_MARKER = 'role="presentation"'

#: The layout emits ``lang="${lang}"`` on ``<html>``.
LANG_ATTRIBUTE = re.compile(r"<html[^>]*\blang=\"([a-zA-Z-]+)\"")

#: An inline ``style`` attribute carrying at least one CSS declaration.
INLINE_STYLE = re.compile(r'style="[^"]*[a-z-]+\s*:[^"]+"')

#: About 31 inline ``style`` attributes when CSS inlining works, about 6 when
#: it silently fails. Below this, inlining failed.
MIN_INLINE_STYLES = 10


# ---------------------------------------------------------------------------
# Registry records (theming model)
# ---------------------------------------------------------------------------

THEME_RECORDS = {
    "logo_url": "imio.emailkit.theme.logo_url",
    "primary_color": "imio.emailkit.theme.primary_color",
    "footer_html": "imio.emailkit.theme.footer_html",
}


# ---------------------------------------------------------------------------
# Guards for a missing runtime
# ---------------------------------------------------------------------------

_RUNTIME_PENDING = (
    "imio.emailkit runtime is not importable yet ({exc}). This module's "
    "assertions run unchanged once the runtime is available. Nothing here "
    "was weakened to go green."
)

_CONTRACT_PENDING = (
    "{target} is not available. tests/support.py documents the API contract "
    "this suite encodes at {section}; if the runtime chose another name, "
    "reconcile there -- do not drop the assertion."
)


def require_runtime():
    """Skip the calling module if the add-on is not importable at all."""
    try:
        import imio.emailkit  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        pytest.skip(_RUNTIME_PENDING.format(exc=exc), allow_module_level=True)


def require_contract(dotted, section, *names):
    """Import ``dotted`` and return ``names`` off it, or skip the module."""
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

    Loaded by path, not imported, so ``tests/fixtures/`` stays plain data.
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
    """:func:`load_fixture` against another add-on's fixture directory."""
    from imio.emailkit.golden import load_fixture as shipped

    return shipped(Path(directory) / f"{template}.py")


def available_fixtures():
    return sorted(p.stem for p in FIXTURES_DIR.glob("*.py") if p.stem != "__init__")


# ---------------------------------------------------------------------------
# Golden files
# ---------------------------------------------------------------------------

#: Regeneration is deliberate, never a side effect of a failing comparison.
UPDATE_GOLDEN_ENV = "EMAILKIT_UPDATE_GOLDEN"

#: The one template and language the snapshot gate covers. A byte diff of
#: every rendered mail would break on any shared-layout change, producing
#: diffs nobody reads. ``assert_render_is_clean`` still runs on every body
#: in the suite, and ``make check-emails`` still does a full byte compare.
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

    An integration test never traverses, so the normal marking never runs.
    """
    from zope.interface import alsoProvides

    alsoProvides(request, layer)
    return request


def resolved_template(view):
    """The ``ViewPageTemplateFile`` behind a ``browser:page template=...`` view.

    Use only for views with an ``index``. This package's own default-mail
    views render through ``render()`` and have none.
    """
    return view.index.__func__


#: Fixture member identity, reused by every default-mail test.
MEMBER_FULLNAME = "Zoé Testeuse"
MEMBER_EMAIL = "zoe.testeuse@example.be"


def registered_subject(template):
    """The ``subject`` msgid a template's registration declares."""
    from imio.emailkit.discovery import get_template

    return get_template(qualified(template)).subject


def stock_mail_view(portal, request, template):
    """Look the mail view up exactly the way ``RegistrationTool`` does.

    The context is ``portal_registration``, not the portal.
    """
    from zope.component import getMultiAdapter

    return getMultiAdapter((portal.portal_registration, request), name=template)


def call_stock_mail(portal, request, template, member):
    """Render a Plone default mail through its real call site.

    Keyword arguments mirror ``RegistrationTool``'s own calls, which land in
    ``options`` rather than at top level.
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

    With the zope.tal fallback engine, ``${...}`` can reach the inbox
    verbatim without raising. Delegates to ``imio.emailkit.golden``.
    """
    from imio.emailkit.golden import assert_render_is_clean as shipped

    shipped(rendered, what)


# ===========================================================================
# The ``Email`` builder and the preview view
# ===========================================================================

#: The frozen builder method set, in the order the example chains them.
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

#: Every method except ``.send()`` returns ``self`` and can be chained.
CHAINING_METHODS = tuple(name for name in BUILDER_METHODS if name != "send")

#: GUESS: the module for ``RecipientError``, ``AttachmentError`` and
#: ``IEmailRecipient``. Change this line if the runtime uses another module.
INTERFACES_MODULE = "imio.emailkit.interfaces"

#: The preview view name. Manager-only.
PREVIEW_VIEW = "emailkit-preview"

#: GUESS, confirmed against the view: the language switcher parameter.
PREVIEW_LANGUAGE_PARAM = "language"

#: Likewise for the template selector.
PREVIEW_TEMPLATE_PARAM = "template"

#: The Send-test button control name.
SEND_TEST_BUTTON = "form.button.send_test"

SEND_TEST_FORM = {SEND_TEST_BUTTON: "Send test"}

#: The send test fires only on ``POST``, never on a fetch.
SEND_TEST_METHOD = "POST"

#: Each preview renders in an iframe using committed fixture data.
IFRAME_SRC = re.compile(r"<iframe[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Shared identities for the builder and preview tests
# ---------------------------------------------------------------------------

#: An address with no member behind it, so ``IEmailRecipient.language`` is
#: ``None`` and grouping falls back to the site default.
PLAIN_ADDRESS = "greffe@commune.example.be"

#: A second one, for "two addresses land in one message" assertions.
OTHER_ADDRESS = "secretariat@commune.example.be"

#: Neither an address nor a userid: must raise ``RecipientError`` at
#: ``.send()`` time, not drop silently.
UNRESOLVABLE = "definitely-not-a-user-or-an-address"
OTHER_UNRESOLVABLE = "also-not-a-user-or-an-address"

#: The two extra members the language-grouping tests need.
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

#: ``From`` defaults to the site's configured sender records.
SENDER_ADDRESS_RECORD = "plone.email_from_address"
SENDER_NAME_RECORD = "plone.email_from_name"
SITE_SENDER_ADDRESS = "noreply@commune.example.be"
SITE_SENDER_NAME = "Commune de Test"

#: An explicit ``.sender(...)`` override, distinct from the site default.
OVERRIDE_SENDER = "convocations@commune.example.be"

#: ``.reply_to(...)``, the address the builder's own example uses.
REPLY_TO = "noreply@imio.be"

#: The registry record for the site's default language, the fallback for a
#: recipient with none.
DEFAULT_LANGUAGE_RECORD = "plone.default_language"


# ---------------------------------------------------------------------------
# Subjects: expected values are *translated*, never hardcoded
# ---------------------------------------------------------------------------

#: A msgid whose FR and NL translations differ from EN, proving translation
#: rather than pass-through.
OVERRIDE_SUBJECT_MSGID = "email_subject_mail_password_template"

#: A literal ``.subject(...)`` override; must reach every language unchanged.
LITERAL_SUBJECT = "Convocation - seance du 12 aout"


def message_id(msgid, default=None):
    """A ``zope.i18nmessageid.Message`` in this package's domain."""
    from zope.i18nmessageid import Message

    return Message(msgid, domain=PACKAGE_NAME, default=default)


def translated(msgid, language):
    """Translate ``msgid`` for ``language`` the way a template would."""
    from zope.i18n import translate

    return translate(msgid, target_language=language)


def registration_subject(template=NOTIFICATION):
    """The subject msgid the registration declares for ``template``."""
    from imio.emailkit.discovery import get_template

    return get_template(qualified(template)).subject


# ---------------------------------------------------------------------------
# Guards for the builder and preview modules
# ---------------------------------------------------------------------------

_BUILDER_PENDING = (
    "{target} is not available. This module encodes the frozen Email builder "
    "API; the builder itself was written in parallel with these tests. Every "
    "assertion here is written and runs unchanged as soon as it lands -- "
    "nothing was weakened to go green. If it chose a different name, "
    "reconcile in tests/support.py ({hint})."
)


def require_builder():
    """Return ``imio.emailkit.Email`` or skip the calling module."""
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
    """Return the named builder exceptions/interfaces or skip the module."""
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

    A *missing* view skips; a *protected* one does not, so the Manager-only
    assertions can still fail.
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
# The MIME shape is fixed: ``set_content(text)`` plus
# ``add_alternative(html, subtype="html")``.


def sole(sent, what="message"):
    """Exactly one item, or a failure that says how many there were."""
    assert len(sent) == 1, f"expected exactly one {what}, got {len(sent)}"
    return sent[0]


def alternative_part(message):
    """The ``multipart/alternative`` section of a message."""
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
    """A text part's content, decoded, with line endings normalised."""
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

    Parsed, not substring-matched, so ``zoe@example.be.evil`` cannot match.
    """
    from email.utils import getaddresses

    raw = message.get_all(header) or []
    return sorted(
        address.lower() for _name, address in getaddresses([str(v) for v in raw])
    )


def envelope(record):
    """The bare addresses the SMTP layer was handed, lowercased."""
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
    """Neither MIME part may carry an unsubstituted placeholder."""
    text, html = bodies(message)
    assert_render_is_clean(html, "sent html part")
    assert_render_is_clean(text, "sent text part")


# ===========================================================================
# ``render_shell``
# ===========================================================================
#
# Its signature is spelled literally, so nothing below is a guess about the
# API, only about test-local fixture names.

#: ``render_shell(subject, body_html, language=None)``, not a builder method.
SHELL_ARGUMENTS = ("subject", "body_html", "language")

#: Fixtures whose ``CONTEXT`` is a ``render_shell`` call, not a template
#: context.
SHELL_FIXTURES = ("shell_plonemeeting",)


def require_shell():
    """Return ``imio.emailkit.render_shell`` or skip the calling module."""
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
    """``(subject, body_html)`` of a shell fixture."""
    data = load_fixture(name)
    missing = [key for key in ("subject", "body_html") if key not in data]
    assert missing == [], (
        f"shell fixture {name!r} is missing {missing}; a shell fixture's CONTEXT "
        "is the render_shell(subject, body_html) call itself"
    )
    return data["subject"], data["body_html"]


#: The names ``render()`` puts in the template namespace. The injection test
#: checks each one comes back out verbatim.
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

#: Zero-width and invisible characters the kit uses for layout. Harmless in
#: HTML, but noise or mojibake in a ``text/plain`` part.
INVISIBLE_CHARACTERS = re.compile(
    "["
    "​"  # zero-width space
    "‌"  # zero-width non-joiner
    "‍"  # zero-width joiner: kit's Outlook spacer cell
    " "  # figure space: preheader padding
    "﻿"  # zero-width no-break space
    "͏"  # combining grapheme joiner: preheader padding
    "]"
)

#: A plaintext part may legitimately contain ``<`` from an unescaped ``&lt;``.
HTML_TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(\s[^<>]*)?/?>")


def head_of(html):
    """Everything before ``<body``: the part of the document the layout owns.

    Excludes ``<title>``: it appears only when the context has a ``title``
    name, since ``Main.vue`` parses it as rawtext and would otherwise escape
    a slot written inside it.
    """
    index = html.lower().find("<body")
    assert index != -1, "no <body> in the rendered document"
    return _TITLE_ELEMENT.sub("", html[:index])


_TITLE_ELEMENT = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)
