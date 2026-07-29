"""SPEC §6.3 ``@@emailkit-preview`` -- every registered template, rendered.

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

**Fixtures.** §6.3 renders "committed fixture data (see §7)", and §7 puts it in
``tests/fixtures/<name>.py`` -- inside the *checkout* of whichever addon ships
the template, not inside the installed package (``tests/`` is not shipped, and
must not be: it is not importable from a released egg). So the fixture is
resolved by walking up from the template directory to find the checkout, and its
absence is reported as a plain fact rather than an error: an egg installed
without its source tree is the normal production case, and the preview simply
has nothing to show for that template there.

**Send test.** §6.3's whole point is that "browser previews lie, Outlook
doesn't". The button goes through the §6.2 ``Email`` builder unchanged -- same
code path as a production mail -- and always to
``getAuthenticatedMember()``'s own address. There is deliberately no address
field: a Manager-only form that mails arbitrary rendered HTML to an
arbitrary address is a spam relay, and nothing about the feature needs one.
"""

from imio.emailkit.discovery import get_templates
from imio.emailkit.interfaces import IEmailkitTheme
from imio.emailkit.interfaces import THEME_REGISTRY_PREFIX
from imio.emailkit.render import get_theme
from imio.emailkit.render import negotiated_language
from imio.emailkit.render import render
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

#: Languages the switcher offers. SPEC §1 makes FR/NL/DE first-class and the
#: package ships those three catalogs plus the English msgid defaults. A site's
#: own ``plone.available_languages`` is ``['en']`` on a stock install, which
#: would leave §6.3's language switcher with a single entry on exactly the
#: machine a developer previews on. Site languages are appended, not substituted.
PREVIEW_LANGUAGES = ("fr", "nl", "de", "en")

#: Where SPEC §7 puts a fixture, relative to the checkout root of the addon that
#: ships the template.
FIXTURE_SUBPATH = ("tests", "fixtures")

#: How far above the template directory to look for that checkout.
#: ``src/imio/emailkit/templates`` -> repository root is four levels up; six
#: leaves room for a deeper namespace without turning this into a filesystem
#: crawl, and the walk stops at the first hit either way.
FIXTURE_SEARCH_DEPTH = 6

NO_FIXTURE = (
    "No committed fixture for {name}. SPEC §7 puts it at "
    "tests/fixtures/{basename}.py in the checkout of the addon that ships the "
    "template, and tests/ is not part of the installed distribution -- so this "
    "is expected when {package} is installed as a released egg rather than as a "
    "source checkout. Searched upwards from {directory}."
)

NO_BUILDER = (
    "Cannot send: imio.emailkit.Email is not importable. SPEC §6.2's builder is "
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
    "Delivery is a queued IMailHost send (SPEC §6.2), so it leaves with this "
    "transaction."
)


def email_builder():
    """SPEC §6.2's ``Email``, or ``None`` when it is not importable yet.

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

    Resolved per *template*, not per repository: §7 makes fixtures a
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
        """Every registered template, sorted. SPEC §4's discovery, verbatim."""
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
            "context": None,
            "html": None,
            "text": None,
            "error": None,
        }
        template = state["template"] = self.template()
        if template is None:
            state["error"] = (
                f"No email template is registered as {self.selected_name()!r}. "
                f"Registered: {', '.join(sorted(get_templates())) or '(none)'}."
            )
            return state

        path = state["fixture"] = fixture_path(template)
        if path is None:
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

    # -- urls -----------------------------------------------------------------

    def view_url(self, name, **overrides):
        """A URL for ``name`` carrying the current selection, with overrides."""
        query = {"template": self.selected_name(), "language": self.language()}
        query.update(overrides)
        return f"{self.context.absolute_url()}/{name}?{urlencode(query)}"

    def page_url(self, **overrides):
        return self.view_url("emailkit-preview", **overrides)

    def body_url(self, **overrides):
        return self.view_url("emailkit-preview-body", **overrides)


class EmailkitPreview(PreviewBase):
    """SPEC §6.3's preview page. Registered Manager-only on ``IEmailkitLayer``."""

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
        exists (SPEC §4: without one the text part is a deprecated fallback).
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
                "fixture": str(path) if path is not None else "",
                "twin": template.text_path is not None and template.text_path.exists(),
            })
        return rows

    def language_rows(self):
        """SPEC §6.3's language switcher."""
        current = self.language()
        return [
            {
                "code": language,
                "url": self.page_url(language=language),
                "css": "selected" if language == current else "",
            }
            for language in self.languages()
        ]

    def theme_rows(self):
        """SPEC §6.3's theme-token panel: the three §3 tokens as they render now.

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
        """The registry control panel, filtered on our records -- §8.2 level 2."""
        return (
            f"{api.portal.get().absolute_url()}/portal_registry"
            f"?{urlencode({'q': THEME_REGISTRY_PREFIX})}"
        )

    def subject(self, template):
        """The registration's subject msgid, translated into the preview language.

        SPEC §4 keeps the subject in the registration and §6.2 translates it per
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
        language = self.language()
        address = self.user_address()

        # SPEC §6.2 groups recipients by their *own* resolved language, and the
        # builder has no language argument -- correctly, it holds data and does
        # not grow behaviour. So the switcher is honoured the only way that does
        # not touch the frozen API: the request's negotiated language, which is
        # what the builder falls back to for a recipient expressing no
        # preference. A member who *has* set a language preference gets that
        # instead, which is §6.2 working as specified rather than a bug here.
        previous = self.request.get("LANGUAGE")
        self.request["LANGUAGE"] = language
        try:
            email_builder()(template.name).to(self.member()).subject(
                f"[emailkit test] {template.name}"
            ).with_context(**dict(state["context"])).send()
        except Exception:
            logger.exception("Send test of %s failed", template.name)
            return "error", (
                f"Email({template.name!r}).send() raised:\n\n{traceback.format_exc()}"
            )
        finally:
            if previous is None:
                self.request.other.pop("LANGUAGE", None)
            else:
                self.request["LANGUAGE"] = previous

        return "info", SENT.format(
            name=template.name, language=language, address=address
        )


class EmailkitPreviewBody(PreviewBase):
    """The rendered mail alone, for the ``<iframe>`` of SPEC §6.3.

    Returns the mail's own HTML unwrapped and unmodified: what a mail client
    would be handed, byte for byte, with none of the preview chrome's markup or
    CSS anywhere near it.
    """

    def __call__(self):
        state = self.state()
        response = self.request.response
        if state["error"]:
            # Plain text on purpose: a traceback is the payload here, and
            # wrapping it in markup would only invite the browser to reflow it.
            response.setHeader("Content-Type", "text/plain; charset=utf-8")
            return state["error"]
        response.setHeader("Content-Type", "text/html; charset=utf-8")
        return state["html"]
