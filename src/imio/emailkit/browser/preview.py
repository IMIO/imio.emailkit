"""``@@emailkit-preview`` -- every registered template, rendered.

Manager-only, deliberately plain, and made of two views rather than one:

``@@emailkit-preview``
    the chrome -- the template list, the language switcher, the theme-token
    panel and the send-test form.
``@@emailkit-preview-body``
    the rendered mail and nothing else, loaded by the chrome in an ``<iframe>``.

**Why two.** A transactional email carries a full stylesheet written for mail
clients -- ``body { }`` rules, table resets, ``!important`` utilities. Inlining
that markup into the chrome would let it restyle the Plone UI and let the Plone
UI flatter it, so the one thing this view exists to show would be the one thing
it shows wrongly. An iframe is the boring browser-level answer and costs one
extra registration.

**Fixtures.** The preview renders committed fixture data, which lives in
``tests/fixtures/<name>.py`` -- inside the *checkout* of whichever addon ships
the template, not inside the installed package (``tests/`` is not shipped, and
must not be: it is not importable from a released egg). So the fixture is
resolved by walking up from the template directory to find the checkout, and its
absence is reported as a plain fact rather than an error: an egg installed
without its source tree is the normal production case, and the preview simply
has nothing to show for that template there.

**Modes.** ``render()`` returns two things and the preview shows both -- the
HTML part in the iframe, the plaintext part beside it. A third mode shows the
committed ``.pt`` *itself*, served to the same iframe as ``text/html`` with no
``render()`` pass at all. It is the only one of the three that needs no fixture,
which is what it is for: a template being authored before its fixture exists, or
one installed from an egg with no source tree, is otherwise the one template
nobody can look at. Nothing is substituted in that mode -- ``${item/title}``
stands where the value would be and every ``tal:condition`` branch shows at once
-- so it answers "what does this layout look like", never "does this template
render".

**Send test.** The whole point here is that "browser previews lie, Outlook
doesn't". The button goes through the ``Email`` builder unchanged -- same
code path as a production mail -- and always to
``getAuthenticatedMember()``'s own address. There is deliberately no address
field: a Manager-only form that mails arbitrary rendered HTML to an
arbitrary address is a spam relay, and nothing about the feature needs one.
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

#: Languages the switcher offers. FR/NL/DE are first-class and the
#: package ships those three catalogs plus the English msgid defaults. A site's
#: own ``plone.available_languages`` is ``['en']`` on a stock install, which
#: would leave the language switcher with a single entry on exactly the
#: machine a developer previews on. Site languages are appended, not substituted.
PREVIEW_LANGUAGES = ("fr", "nl", "de", "en")

#: What the preview shows for the selected template. The first two are the two
#: halves of ``render()``'s return value; the third is the committed file itself.
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

#: How far above the template directory to look for that checkout.
#: ``src/imio/emailkit/templates`` -> repository root is four levels up; six
#: leaves room for a deeper namespace without turning this into a filesystem
#: crawl, and the walk stops at the first hit either way.
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
    """The ``Email`` builder, or ``None`` when it is not importable yet.

    Imported here rather than at module scope so a missing builder degrades to a
    disabled button instead of an unimportable view: this module is loaded by
    ZCML at startup, and swallowing an ``ImportError`` up there would hide a real
    breakage in the builder just as effectively as an absent one.
    """
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

    Resolved per *template*, not per repository: fixtures are a
    per-consumer-addon artifact, so a site with three addons shipping templates
    has three ``tests/fixtures`` directories and each template's own checkout is
    the only place its fixture can be.
    """
    directory = template.html_path.parent
    roots = (directory, *directory.parents)[: FIXTURE_SEARCH_DEPTH + 1]
    for root in roots:
        candidate = root.joinpath(*FIXTURE_SUBPATH, f"{template.basename}.py")
        if candidate.is_file():
            return candidate
    return None


def load_fixture(path):
    """Return a copy of the ``CONTEXT`` mapping defined by the fixture at ``path``.

    Executed by path rather than imported, because ``tests/fixtures/`` is a
    directory of data files and not a package -- the same reason, and the same
    mechanism, as the golden-file harness. Never cached: a developer who edits a
    fixture expects the next reload to show it.
    """
    spec = importlib.util.spec_from_file_location(
        f"_emailkit_preview_{path.stem}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return dict(module.CONTEXT)


class PreviewBase(BrowserView):
    """Selection parsing and rendering, shared by the chrome and the iframe body.

    Both views answer the same question -- "template X, in language Y, with its
    committed fixture" -- and they must answer it identically, or the page would
    describe one mail while the iframe showed another.
    """

    _state = None

    # -- the current selection ------------------------------------------------

    def templates(self):
        """Every registered template, sorted, verbatim from discovery."""
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
        """The one error that survives every mode: there is nothing to show."""
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
        """``{template, fixture, context, html, text, error}``, computed once.

        One dict rather than a method per value because every consumer needs the
        same slice of it and because ``render()`` must run once per request, not
        once per question asked about it.
        """
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
        """Whether the selection has no committed fixture. Source mode's cue."""
        return self.state()["fixture_missing"]

    def display_error(self):
        """What stops the *current mode* from showing anything, or ``None``.

        Not the same question as :meth:`error`, which is about the render.
        Source mode reads a file off disk and needs neither a fixture nor a
        successful render, so a fixture problem is a note beside it rather than
        a wall in front of it -- and a template that renders in no language at
        all is precisely one you want to look at the source of.
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

    #: A ``Products.Five`` template, so the preview page is itself jbot-overridable
    #: -- free, and consistent with how everything else in this package renders.
    index = ViewPageTemplateFile("templates/preview.pt")

    def __call__(self):
        if self.is_send_test():
            return self.send_test()
        return self.index()

    def is_send_test(self):
        """POST only.

        Not because the CSRF token in the form is insufficient, but because a URL
        that sends mail when merely *fetched* is a URL something eventually
        fetches -- a prefetcher, a link checker, somebody's browser history.
        """
        method = self.request.get("REQUEST_METHOD", "GET").upper()
        return method == "POST" and bool(self.request.form.get("form.button.send_test"))

    # -- panels ---------------------------------------------------------------

    def template_rows(self):
        """The template list, with everything the page shows about each entry.

        Assembled here rather than in the template: a page template that has to
        compute is a page template nobody can read, and the two flags below are
        the ones a developer actually wants at a glance -- whether a fixture
        exists (so the preview can render at all) and whether a plaintext twin
        exists (without one the text part is a deprecated fallback).
        """
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
        """The language switcher."""
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
        """The three things the page can show, as a switcher beside the languages."""
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
        """Source mode for the current selection -- the offer made when the
        fixture is missing and the other two modes have nothing to show."""
        return self.page_url(mode=MODE_SOURCE)

    def offer_source(self):
        """Whether the missing fixture is what is on screen instead of a mail.

        The one case where the page should say what to do next: source mode is
        right there, needs nothing, and is not obvious from an error about a
        directory that is not shipped.
        """
        return bool(self.display_error()) and self.fixture_missing()

    def show_iframe(self):
        """Both the HTML part and the raw ``.pt`` are markup, and go in the frame."""
        return not self.display_error() and self.mode() in (MODE_HTML, MODE_SOURCE)

    def show_text(self):
        """The plaintext part is text, and needs no frame to be shown safely."""
        return not self.display_error() and self.mode() == MODE_TEXT

    def theme_rows(self):
        """The theme-token panel: the theme tokens as they render now.

        Read through ``render.get_theme()`` -- the very function that injects
        them into the namespace -- so the panel cannot drift from what the iframe
        beside it is showing.
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
        """The registry control panel, filtered on our records."""
        return (
            f"{api.portal.get().absolute_url()}/portal_registry"
            f"?{urlencode({'q': THEME_REGISTRY_PREFIX})}"
        )

    def subject(self, template):
        """The registration's subject msgid, translated into the preview language.

        The registration keeps the subject and the builder translates it per
        recipient language at send time, which makes it the one part of a mail a
        browser preview would otherwise never show.
        """
        if template.subject is None:
            return "(none registered)"
        return zope_translate(template.subject, target_language=self.language())

    def text_part(self):
        """``render()``'s plaintext half. Half the output, and never looked at."""
        return self.state()["text"]

    def fixture(self):
        path = self.state()["fixture"]
        return str(path) if path is not None else ""

    def messages(self):
        """Status messages, as dicts.

        ``Products.statusmessages`` ``Message`` objects carry no security
        declarations, so ``message/type`` cannot be path-traversed from a
        template; dicts can, and need nothing.
        """
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
        """The language the sent mail will actually be rendered in.

        Not necessarily the one in the switcher, and this is where the preview and
        the builder pull against each other. The preview button is meant to mail
        "the currently previewed template + fixture + **language**"; the builder
        gives itself no language argument at all, and has ``.send()`` group
        recipients by *their own* resolved language, falling back to the site
        default. Both cannot be true, and the builder's behaviour is the frozen
        one.

        So rather than fake it -- an inert ``request['LANGUAGE']`` was tried and
        does nothing, because ``recipients.default_language()`` deliberately reads
        the site default and not the request -- the view computes the truth from
        the builder's own public contract (the ``IEmailRecipient`` adapter) and
        says so next to the button. A developer who wants the mail in Dutch sets
        Dutch as their own preferred language, which is the mechanism the builder
        actually provides. Mutating that property on their behalf was rejected: silently
        rewriting a user's preferences because they clicked a preview button is
        not a thing a developer tool gets to do.
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

        Redirect rather than render: the status message then survives a refresh
        without re-sending, which is Plone's ordinary post/redirect/get and the
        only sane behaviour for a button that puts mail on the wire.
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
            # The builder's contract verbatim, and nothing else. `.to(member)`
            # rather than `.to(address)` on purpose: it is the recipient the
            # builder resolves for itself, so no address this form received
            # can reach the wire.
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
    """The rendered mail alone, for the preview's ``<iframe>``.

    Returns the mail's own HTML unwrapped and unmodified: what a mail client
    would be handed, byte for byte, with none of the preview chrome's markup or
    CSS anywhere near it.
    """

    def __call__(self):
        if self.is_source():
            return self.source()
        state = self.state()
        response = self.request.response
        if state["error"]:
            # Plain text on purpose: a traceback is the payload here, and
            # wrapping it in markup would only invite the browser to reflow it.
            response.setHeader("Content-Type", "text/plain; charset=utf-8")
            return state["error"]
        response.setHeader("Content-Type", "text/html; charset=utf-8")
        return state["html"]

    def source(self):
        """The committed ``.pt``'s own bytes, served as HTML and nothing else.

        No ``render()`` and no fixture, which is the whole point: this is the
        one mode that works for a template being authored before its fixture
        exists. Served as ``text/html`` rather than escaped into a ``<pre>``
        because what a developer wants from a mail template is to *see* the
        layout -- the TAL attributes are simply unknown attributes to a browser,
        and it draws the markup around them.

        The path goes through ``render.resolved_path``, so a jbot-overridden
        template shows the override -- the file that would actually be compiled.
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
