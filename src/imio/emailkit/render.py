"""``render()`` -- the one way a registered template becomes text.

``html, text = render(name, context={...}, language=None)``

Its sibling, for a mail body that already exists as HTML:

``html, text = render_shell(subject, body_html, language=None)``

A pure function of (template, context, registry state). Neither is a
builder method: the ``Email`` API is frozen.

Hazards:

* Templates load through ``Products.PageTemplates.PageTemplateFile``,
  the only class with TAL paths and z3c.jbot support.
* Without ``IPageTemplateEngine``, ``${...}`` passes through verbatim.
* ``imio.emailkit.__init__`` rebinds ``render``; import this module with
  ``from imio.emailkit.render import <name>``.
* Templates write ``${python: format_date(item/created)}``, not
  ``${format_date(...)}``.
"""

from Acquisition import aq_get
from html import unescape
from imio.emailkit.discovery import get_template
from imio.emailkit.discovery import TEXT_SUFFIX
from imio.emailkit.helpers import bind as bind_locale_helpers
from imio.emailkit.helpers import FALLBACK_LANGUAGE
from imio.emailkit.interfaces import EmailkitError
from imio.emailkit.interfaces import IEmailkitTheme
from imio.emailkit.interfaces import THEME_REGISTRY_PREFIX
from pathlib import Path
from plone.registry.interfaces import IRegistry
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from zope.component import queryUtility
from zope.component.hooks import getSite
from zope.globalrequest import getRequest
from zope.i18n import translate as zope_translate

import logging
import re


logger = logging.getLogger("imio.emailkit.render")

#: The kit layout with no content. :func:`render_shell` fills its body
#: with ``body_html``.
#:
#: Resolved by path, not the template registry: there is no name to look
#: up. Still loads through :func:`_page_template`, so jbot overrides apply.
SHELL_TEMPLATE = Path(__file__).parent / "templates" / "shell.pt"


def render(name, context=None, language=None):
    """Render the template registered as ``name`` and return ``(html, text)``.

    :param name: namespaced name, e.g. ``"imio.emailkit:mail_password_template"``
    :param context: mapping injected into the template namespace as top-level
        names, so a template reads ``${item/title}`` and not ``${options/item}``
    :param language: language to render in; the negotiated language when omitted
    :raises TemplateNotFound: when nothing is registered under ``name``
    """
    template = get_template(name)
    language = language or negotiated_language()
    namespace = build_namespace(context, language, preheader=template.preheader)

    html = render_file(template.html_path, namespace)
    # `text_path` may point to a file that no longer exists, for example
    # after a rebuild dropped the twin. Without this check, that raises
    # FileNotFoundError instead of falling back.
    if template.text_path is None or not template.text_path.exists():
        text = _fallback_text(template, html)
    else:
        text = render_file(template.text_path, namespace)
    return html, text


def render_shell(subject, body_html, language=None):
    """Wrap an *existing* HTML mail body in the kit shell; return ``(html, text)``.

    For a mail body that already exists as HTML and will not be
    re-authored as a kit template. A ``render()`` sibling, not a builder
    method.

    :param subject: an i18n msgid or literal string, like ``.subject()``.
        Required: raises rather than producing an untitled mail.
    :param body_html: the existing body, inserted verbatim with
        ``structure``. Not sanitised or re-parsed as a template.
    :param language: as ``render()``.
    :raises EmailkitError: when the compiled shell is absent from the egg.

    The plaintext part comes from :func:`naive_text`, since a plaintext
    twin could only repeat the already-HTML ``body_html``. No preheader
    is injected: the hidden div collapses.
    """
    language = language or negotiated_language()
    # `zope.i18n.translate` returns a plain string unchanged. This is the
    # same call `.subject()` uses, so the heading and the mail header agree.
    subject = zope_translate(subject, target_language=language)
    namespace = build_namespace(
        {"subject": subject, "body_html": body_html},
        language,
    )
    html = render_file(_shell_path(), namespace)
    return html, naive_text(html)


def _shell_path():
    """:data:`SHELL_TEMPLATE`, checked to exist. Fail loud, never silent.

    Missing means the egg lacks its build output. Unchecked, this would
    raise a bare ``FileNotFoundError`` pointing at Zope, not the real cause.
    """
    if not SHELL_TEMPLATE.exists():
        raise EmailkitError(
            f"The compiled kit shell is missing: {SHELL_TEMPLATE}. "
            f"render_shell() needs the committed Maizzle build output; run "
            f"`make build-emails`."
        )
    return SHELL_TEMPLATE


def build_namespace(context, language, preheader=None):
    """Assemble the namespace ``render()`` hands to both compiled templates.

    Shared with :func:`render_shell`. Precedence, low to high: the
    registration's ``preheader``, the caller's ``context``, then the
    names this package injects, which always win.
    """
    namespace = {}
    if preheader is not None:
        namespace["preheader"] = zope_translate(preheader, target_language=language)
    if context:
        namespace.update(context)

    namespace.update(locale_helpers(language))
    namespace.update({
        "lang": language,
        "theme": get_theme(),
        "portal_url": portal_url(),
        "translate": _translate_helper(language),
        # Zope's `i18n:translate` reads the language from this name;
        # without it, it silently uses the request language instead.
        "target_language": language,
    })
    return namespace


def locale_helpers(language):
    """The formatting helpers, bound to ``language``.

    Re-exports :func:`imio.emailkit.helpers.bind`.
    """
    return bind_locale_helpers(language)


def get_theme():
    """Return the theme tokens, read from ``plone.app.registry``.

    A missing registry, record, or value collapses to the empty string,
    not the literal ``"None"`` interpolated into markup.
    """
    registry = queryUtility(IRegistry)
    theme = {}
    for token in IEmailkitTheme.names():
        value = None
        if registry is not None:
            value = registry.get(f"{THEME_REGISTRY_PREFIX}.{token}")
        theme[token] = "" if value is None else value
    return theme


def negotiated_language():
    """The language ``render()`` uses when the caller passes none.

    In order: the request's negotiated language, then the site's default,
    then English.
    """
    request = getRequest()
    if request is not None:
        language = request.get("LANGUAGE", None)
        if language:
            return language
    registry = queryUtility(IRegistry)
    if registry is not None:
        language = registry.get("plone.default_language", None)
        if language:
            return language
    return FALLBACK_LANGUAGE


def portal_url():
    """The portal's absolute URL, or ``""`` when there is no request to build it.

    ``absolute_url()`` needs a REQUEST for the server part.
    """
    site = getSite()
    if site is None or aq_get(site, "REQUEST", None) is None:
        return ""
    return site.absolute_url()


_page_templates = {}


def render_file(path, namespace):
    """Render one compiled ``.pt`` with ``namespace`` as top-level names."""
    return _page_template(path).pt_render(extra_context=namespace)


def _page_template(path):
    """Return the (cached) ``PageTemplateFile`` for ``path``, jbot-resolved.

    Caching avoids leaking one z3c.jbot registry entry per render. jbot
    patches ``PageTemplateFile`` into a descriptor, which only fires via
    attribute access on a class, so ``__get__`` is called by hand here.
    """
    key = str(path)
    template = _page_templates.get(key)
    if template is None:
        template = _page_templates[key] = PageTemplateFile(key)
    bind = getattr(template, "__get__", None)
    return template if bind is None else bind(None, None)


def resolved_path(path):
    """The file :func:`render_file` would actually compile for ``path``.

    ``path`` itself, or a z3c.jbot override when one is registered.
    """
    return Path(getattr(_page_template(path), "filename", None) or path)


def invalidate_cache():
    """Drop the cached ``PageTemplateFile`` instances. For tests."""
    _page_templates.clear()
    _warned_missing_twin.clear()


def _translate_helper(language):
    def translate(message, domain=None, mapping=None, default=None):
        """Translate ``message`` into the render language."""
        return zope_translate(
            message,
            domain=domain,
            mapping=mapping,
            target_language=language,
            default=default,
        )

    return translate


_SCRIPT_OR_STYLE = re.compile(
    r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
# A nested `<head>` can glue its `<title>` onto the plaintext body.
_HEAD = re.compile(r"<head\b.*?</head\s*>", re.IGNORECASE | re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# A visible separator keeps a table row on one line, not concatenated.
_CELL_BREAK = re.compile(r"</(?:td|th)\s*>", re.IGNORECASE)
# Swallows a trailing newline after the separator, keeping rows adjacent.
_TRAILING_CELL = re.compile(r"[ \t]*\|\s*$", re.MULTILINE)

# A heading ends a block, not a line, so its title stays separate.
_HEADING_BREAK = re.compile(r"</h[1-6]\s*>", re.IGNORECASE)

_LINE_BREAK = re.compile(
    r"<br\s*/?>|</(?:p|div|tr|li|table|blockquote)\s*>", re.IGNORECASE
)
_TAG = re.compile(r"<[^>]+>")
_BLANK_RUN = re.compile(r"\n{3,}")

# Hidden elements, especially the padded preheader, must not reach plaintext.
_HIDDEN_ELEMENT = re.compile(
    r"<(?P<tag>\w+)[^>]*style=\"[^\"]*display:\s*none[^\"]*\"[^>]*>"
    r".*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)

# Zero-width layout tricks for HTML mail; noise in a plaintext part.
_ZERO_WIDTH = re.compile(
    "["
    "\u200b"  # zero-width space
    "\u200c"  # zero-width non-joiner
    "\u200d"  # zero-width joiner
    "\u2007"  # figure space -- the kit's preheader filler
    "\ufeff"  # zero-width no-break space
    "\u034f"  # combining grapheme joiner -- also preheader filler
    "]"
)

_warned_missing_twin = set()


def _fallback_text(template, html):
    """Fallback text for a template that ships no ``.txt.pt`` twin.

    Logs once per template per process, not per render, so a mail loop
    does not flood the log.
    """
    if template.name not in _warned_missing_twin:
        _warned_missing_twin.add(template.name)
        logger.warning(
            "DEPRECATION: %s ships no %s twin, so its plaintext part comes from "
            "naive extraction of the HTML. Ship a plaintext twin.",
            template.name,
            TEXT_SUFFIX,
        )
    return naive_text(html)


def naive_text(html):
    """Strip ``html`` down to something readable. Naive by design."""
    text = _HEAD.sub("", html)
    text = _SCRIPT_OR_STYLE.sub("", text)
    text = _COMMENT.sub("", text)
    text = _HIDDEN_ELEMENT.sub("", text)
    text = _CELL_BREAK.sub(" | ", text)
    text = _HEADING_BREAK.sub("\n\n", text)
    text = _LINE_BREAK.sub("\n", text)
    text = _TAG.sub("", text)
    text = unescape(text)
    text = _ZERO_WIDTH.sub("", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    # The separator the last cell of a row left behind, now at end of line.
    text = _TRAILING_CELL.sub("", text)
    return _BLANK_RUN.sub("\n\n", text).strip() + "\n"
