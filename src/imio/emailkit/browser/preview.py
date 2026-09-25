"""``@@emailkit-preview`` -- every registered template, rendered.

Manager-only, made of two views: ``@@emailkit-preview`` is the chrome
(template list, language switcher, theme-token panel, send-test form);
``@@emailkit-preview-body`` is the rendered mail alone, loaded by the chrome
in an iframe so the mail's stylesheet cannot restyle the Plone UI.

The preview renders committed fixture data from ``tests/fixtures/<name>.py``
inside the checkout of the addon that ships the template; a missing fixture
is expected when the egg is installed as a released egg, not a source
checkout. A third mode shows the committed ``.pt`` itself, with no
``render()`` pass and no fixture: ``${...}`` placeholders stay unsubstituted.

The send-test button goes through the ``Email`` builder, always to the
logged-in manager's own address; there is no address field, since a form
that mails arbitrary HTML to an arbitrary address is a spam relay.
"""

from imio.emailkit.discovery import get_templates
from imio.emailkit.interfaces import IEmailkitTheme
from imio.emailkit.interfaces import IEmailRecipient
from imio.emailkit.interfaces import THEME_REGISTRY_PREFIX
from imio.emailkit.recipients import default_language
from imio.emailkit.render import get_theme
from imio.emailkit.render import negotiated_language
from imio.emailkit.render import render
from imio.emailkit.render import resolved_path
from plone import api
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from urllib.parse import urlencode
from zope.i18n import translate as zope_translate

import importlib.util
import logging
import traceback


logger = logging.getLogger("imio.emailkit.preview")

#: Languages the switcher offers: FR/NL/DE plus the English msgid defaults.
#: Site languages are appended, since a stock install's
#: ``plone.available_languages`` is just ``['en']``.
PREVIEW_LANGUAGES = ("fr", "nl", "de", "en")

#: What the preview shows: the two halves of ``render()``'s return value, or
#: the committed file itself.
MODE_HTML = "html"
MODE_TEXT = "text"
MODE_SOURCE = "source"
PREVIEW_MODES = (MODE_HTML, MODE_TEXT, MODE_SOURCE)

MODE_LABELS = {
    MODE_HTML: "html",
    MODE_TEXT: "text",
    MODE_SOURCE: ".pt",
}

MODE_HINTS = {
    MODE_HTML: "render()'s HTML part, with the committed fixture.",
    MODE_TEXT: "render()'s plaintext part, with the committed fixture.",
    MODE_SOURCE: (
        "The committed .pt as a browser draws it -- no render(), no fixture, and "
        "so no substitution: ${...} stands where its value would be and every "
        "tal:condition branch shows at once. What the layout looks like, not "
        "whether the template renders."
    ),
}

#: Where a fixture lives, relative to the checkout root of the addon that
#: ships the template.
FIXTURE_SUBPATH = ("tests", "fixtures")

#: How far above the template directory to look for that checkout. The walk
#: stops at the first hit either way.
FIXTURE_SEARCH_DEPTH = 6

NO_FIXTURE = (
    "No committed fixture for {name}. Fixtures live at "
    "tests/fixtures/{basename}.py in the checkout of the addon that ships the "
    "template, and tests/ is not part of the installed distribution -- so this "
    "is expected when {package} is installed as a released egg rather than as a "
    "source checkout. Searched upwards from {directory}."
)

NO_BUILDER = (
    "Cannot send: imio.emailkit.Email is not importable. The Email builder is "
    "what the send test uses, and the preview deliberately has no second way to "
    "put a message on the wire."
)

NO_ADDRESS = (
    "Cannot send: your own account ({userid}) has no email address. The send "
    "test only ever mails the logged-in user, so set one in your personal "
    "preferences first."
)

SENT = (
    "Queued a test of {name} ({language}) to your own address, {address}. "
    "Delivery is a queued IMailHost send, so it leaves with this "
    "transaction."
)

SEND_LANGUAGE_MISMATCH = (
    "The preview below is {previewed}, but the mail will be sent in {sending}: "
    "the builder renders per *recipient* language and takes no language "
    "argument, so the send follows your own preferred language (or the site "
    "default when you have none). Set yours to {previewed} to send that one."
)


def email_builder():
    """The ``Email`` builder, or ``None``. Imported here, not at module scope,
    so a missing builder degrades to a disabled button, not an import error."""
    try:
        from imio.emailkit import Email
    except ImportError:
        return None
    return Email


def preview_languages():
    """The switcher's languages: the ones we ship, then any extra site language."""
    languages = list(PREVIEW_LANGUAGES)
    available = api.portal.get_registry_record("plone.available_languages", default=())
    for language in sorted(available or ()):
        if language not in languages:
            languages.append(language)
    return languages


def fixture_path(template):
    """Locate ``tests/fixtures/<basename>.py`` for ``template``, or ``None``.

    Resolved per template: each consumer addon has its own fixtures
    directory.
    """
    directory = template.html_path.parent
    roots = (directory, *directory.parents)[: FIXTURE_SEARCH_DEPTH + 1]
    for root in roots:
        candidate = root.joinpath(*FIXTURE_SUBPATH, f"{template.basename}.py")
        if candidate.is_file():
            return candidate
    return None


def load_fixture(path):
    """Return a copy of the ``CONTEXT`` mapping the fixture at ``path`` defines.

    Executed by path, not imported: ``tests/fixtures/`` is a directory of
    data files, not a package. Never cached, so an edit shows on reload.
    """
    spec = importlib.util.spec_from_file_location(
        f"_emailkit_preview_{path.stem}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.CONTEXT)


class PreviewBase(BrowserView):
    """Selection parsing and rendering, shared by the chrome and the iframe body.

    Both views must answer "template X, in language Y" identically, or the
    page would describe one mail while the iframe showed another.
    """

    _state = None

    # -- the current selection ------------------------------------------------

    def templates(self):
        """Every registered template, sorted."""
        registered = get_templates()
        return [registered[name] for name in sorted(registered)]

    def selected_name(self):
        """The requested template name, defaulting to the first registered one."""
        requested = self.request.form.get("template") or ""
        if requested:
            return requested
        available = sorted(get_templates())
        return available[0] if available else ""

    def template(self):
        """The selected :class:`~imio.emailkit.discovery.Template`, or ``None``."""
        return get_templates().get(self.selected_name())

    def languages(self):
        return preview_languages()

    def mode(self):
        """Which of :data:`PREVIEW_MODES` to show, defaulting to the HTML part."""
        requested = self.request.form.get("mode")
        return requested if requested in PREVIEW_MODES else MODE_HTML

    def is_source(self):
        return self.mode() == MODE_SOURCE

    def unregistered_message(self):
        """The error shown in every mode when nothing is selected."""
        return (
            f"No email template is registered as {self.selected_name()!r}. "
            f"Registered: {', '.join(sorted(get_templates())) or '(none)'}."
        )

    def language(self):
        """The requested language, else the negotiated one, else the first offered."""
        languages = self.languages()
        requested = self.request.form.get("language")
        if requested in languages:
            return requested
        negotiated = negotiated_language()
        return negotiated if negotiated in languages else languages[0]

    # -- rendering ------------------------------------------------------------

    def state(self):
        """``{template, fixture, context, html, text, error}``. Cached, since
        ``render()`` must run once per request."""
        if self._state is None:
            self._state = self._resolve()
        return self._state

    def _resolve(self):
        state = {
            "template": None,
            "fixture": None,
            "fixture_missing": False,
            "context": None,
            "html": None,
            "text": None,
            "error": None,
        }
        template = state["template"] = self.template()
        if template is None:
            state["error"] = self.unregistered_message()
            return state

        path = state["fixture"] = fixture_path(template)
        if path is None:
            state["fixture_missing"] = True
            state["error"] = NO_FIXTURE.format(
                name=template.name,
                basename=template.basename,
                package=template.package,
                directory=template.html_path.parent,
            )
            return state

        try:
            state["context"] = load_fixture(path)
        except Exception:
            state["error"] = f"Could not load {path}:\n\n{traceback.format_exc()}"
            return state

        language = self.language()
        try:
            state["html"], state["text"] = render(
                template.name, context=dict(state["context"]), language=language
            )
        except Exception:
            state["error"] = (
                f"render({template.name!r}, language={language!r}) raised:\n\n"
                f"{traceback.format_exc()}"
            )
        return state

    def error(self):
        return self.state()["error"]

    def fixture_missing(self):
        """Whether the selection has no committed fixture."""
        return self.state()["fixture_missing"]

    def display_error(self):
        """What stops the current mode from showing anything, or ``None``.

        Not :meth:`error`: source mode needs neither a fixture nor a render.
        """
        if not self.is_source():
            return self.error()
        return self.unregistered_message() if self.template() is None else None

    def source_path(self):
        """The ``.pt`` source mode shows, or ``""`` when nothing is selected."""
        template = self.template()
        if template is None:
            return ""
        return str(resolved_path(template.html_path))

    # -- urls -----------------------------------------------------------------

    def view_url(self, name, **overrides):
        """A URL for ``name`` carrying the current selection, with overrides."""
        query = {
            "template": self.selected_name(),
            "language": self.language(),
            "mode": self.mode(),
        }
        query.update(overrides)
        return f"{self.context.absolute_url()}/{name}?{urlencode(query)}"

    def page_url(self, **overrides):
        return self.view_url("emailkit-preview", **overrides)

    def body_url(self, **overrides):
        return self.view_url("emailkit-preview-body", **overrides)


class EmailkitPreview(PreviewBase):
    """The preview page. Registered Manager-only on ``IEmailkitLayer``."""

    #: A ``Products.Five`` template, so the preview page is itself jbot-overridable.
    index = ViewPageTemplateFile("templates/preview.pt")

    def __call__(self):
        if self.is_send_test():
            return self.send_test()
        return self.index()

    def is_send_test(self):
        """POST only: a URL that sends mail when fetched will get fetched, by
        a prefetcher, a link checker, or browser history."""
        method = self.request.get("REQUEST_METHOD", "GET").upper()
        return method == "POST" and bool(self.request.form.get("form.button.send_test"))

    # -- panels ---------------------------------------------------------------

    def template_rows(self):
        """The template list, with everything the page shows about each entry."""
        selected = self.selected_name()
        rows = []
        for template in self.templates():
            path = fixture_path(template)
            rows.append({
                "name": template.name,
                "url": self.page_url(template=template.name),
                "css": "selected" if template.name == selected else "",
                "subject": self.subject(template),
                "source_url": self.page_url(template=template.name, mode=MODE_SOURCE),
                "fixture": str(path) if path is not None else "",
                "twin": template.text_path is not None and template.text_path.exists(),
            })
        return rows

    def language_rows(self):
        current = self.language()
        return [
            {
                "code": language,
                "url": self.page_url(language=language),
                "css": "selected" if language == current else "",
            }
            for language in self.languages()
        ]

    def mode_rows(self):
        current = self.mode()
        return [
            {
                "mode": mode,
                "label": MODE_LABELS[mode],
                "url": self.page_url(mode=mode),
                "css": "selected" if mode == current else "",
            }
            for mode in PREVIEW_MODES
        ]

    def mode_hint(self):
        return MODE_HINTS[self.mode()]

    def source_url(self):
        """Source mode for the current selection.

        Offered when the fixture is missing and the other modes have nothing
        to show.
        """
        return self.page_url(mode=MODE_SOURCE)

    def offer_source(self):
        """Whether to suggest source mode instead of the missing fixture error."""
        return bool(self.display_error()) and self.fixture_missing()

    def show_iframe(self):
        """Both the HTML part and the raw ``.pt`` are markup, and go in the frame."""
        return not self.display_error() and self.mode() in (MODE_HTML, MODE_SOURCE)

    def show_text(self):
        """The plaintext part is text, and needs no frame to be shown safely."""
        return not self.display_error() and self.mode() == MODE_TEXT

    def theme_rows(self):
        """The theme-token panel: the theme tokens as they render now.

        Read through ``render.get_theme()``, the function that injects them
        into the namespace, so the panel cannot drift from the iframe.
        """
        theme = get_theme()
        return [
            {
                "token": token,
                "record": f"{THEME_REGISTRY_PREFIX}.{token}",
                "value": theme.get(token) or "",
            }
            for token in sorted(IEmailkitTheme.names())
        ]

    def registry_url(self):
        return (
            f"{api.portal.get().absolute_url()}/portal_registry"
            f"?{urlencode({'q': THEME_REGISTRY_PREFIX})}"
        )

    def subject(self, template):
        """The registration's subject msgid, translated into the preview language.

        The builder translates the subject per recipient language at send
        time, so a browser preview would otherwise never show it.
        """
        if template.subject is None:
            return "(none registered)"
        return zope_translate(template.subject, target_language=self.language())

    def text_part(self):
        """``render()``'s plaintext half."""
        return self.state()["text"]

    def fixture(self):
        path = self.state()["fixture"]
        return str(path) if path is not None else ""

    def messages(self):
        """Status messages, as dicts: ``Message`` objects carry no security
        declarations, so a template cannot traverse ``message/type``."""
        return [
            {"type": message.type or "info", "text": message.message}
            for message in IStatusMessage(self.request).show()
        ]

    # -- send test ------------------------------------------------------------

    def member(self):
        return api.user.get_current()

    def user_address(self):
        member = self.member()
        return (member.getProperty("email", "") or "") if member is not None else ""

    def send_language(self):
        """The language the sent mail will actually render in.

        Not necessarily the one in the switcher: ``.send()`` groups recipients
        by their own resolved language, so this computes the same value
        through ``IEmailRecipient`` rather than reading the switcher.
        """
        member = self.member()
        if member is None:
            return default_language()
        recipient = IEmailRecipient(member, None)
        preferred = getattr(recipient, "language", None)
        return preferred or default_language()

    def send_language_note(self):
        """A warning when the send language will not be the previewed one."""
        sending = self.send_language()
        if sending == self.language():
            return None
        return SEND_LANGUAGE_MISMATCH.format(previewed=self.language(), sending=sending)

    def send_test_blocker(self):
        """Why the send-test button is unavailable, or ``None`` when it is not."""
        if self.error():
            return "Nothing to send: the selection above does not render."
        if email_builder() is None:
            return NO_BUILDER
        if not self.user_address():
            member = self.member()
            return NO_ADDRESS.format(userid=member.getId() if member else "anonymous")
        return None

    def send_test(self):
        """Mail the current selection to the logged-in user, then redirect back.

        Redirect rather than render: the status message then survives a
        refresh without re-sending, Plone's ordinary post/redirect/get.
        """
        level, message = self._send_test()
        IStatusMessage(self.request).addStatusMessage(message, type=level)
        self.request.response.redirect(self.page_url())
        return ""

    def _send_test(self):
        blocker = self.send_test_blocker()
        if blocker is not None:
            return "error", blocker

        state = self.state()
        template = state["template"]
        try:
            # `.to(member)`, not `.to(address)`: no address this form
            # received can reach the wire.
            email_builder()(template.name).to(self.member()).subject(
                f"[emailkit test] {template.name}"
            ).with_context(**dict(state["context"])).send()
        except Exception:
            logger.exception("Send test of %s failed", template.name)
            return "error", (
                f"Email({template.name!r}).send() raised:\n\n{traceback.format_exc()}"
            )
        return "info", SENT.format(
            name=template.name,
            language=self.send_language(),
            address=self.user_address(),
        )


class EmailkitPreviewBody(PreviewBase):
    """The rendered mail alone, for the preview's iframe.

    Returns the mail's own HTML unwrapped: what a mail client would be
    handed, byte for byte, with none of the preview chrome's markup or CSS.
    """

    def __call__(self):
        if self.is_source():
            return self.source()
        state = self.state()
        response = self.request.response
        if state["error"]:
            # Plain text: a traceback is the payload, and markup would only
            # invite the browser to reflow it.
            response.setHeader("Content-Type", "text/plain; charset=utf-8")
            return state["error"]
        response.setHeader("Content-Type", "text/html; charset=utf-8")
        return state["html"]

    def source(self):
        """The committed ``.pt``'s own bytes, served as HTML and nothing else.

        No ``render()`` and no fixture: works for a template with no fixture
        yet. Not escaped into a ``<pre>``, so a developer sees the layout.

        The path goes through ``render.resolved_path``, so a jbot-overridden
        template shows the file that would actually be compiled.
        """
        response = self.request.response
        template = self.template()
        if template is None:
            response.setHeader("Content-Type", "text/plain; charset=utf-8")
            return self.unregistered_message()

        path = resolved_path(template.html_path)
        try:
            markup = path.read_text(encoding="utf-8")
        except OSError as exc:
            response.setHeader("Content-Type", "text/plain; charset=utf-8")
            return (
                f"Could not read {path}: {exc}. The compiled output is committed, "
                f"so this is a build or packaging problem, not a runtime "
                f"one."
            )
        response.setHeader("Content-Type", "text/html; charset=utf-8")
        return markup
