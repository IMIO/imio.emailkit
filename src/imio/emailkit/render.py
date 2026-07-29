"""SPEC §6.1 ``render()`` -- the one way a registered template becomes text.

``html, text = render(name, context={...}, language=None)``

Pure function of (template, context, registry state): no request faking, no
site, no database. Previews (§6.3), golden-file tests (§7) and the ``Email``
builder (§6.2) all go through this one door.

Two Phase 0 findings are load-bearing here and are not negotiable:

* Templates load through ``Products.PageTemplates.PageTemplateFile``, never
  through bare ``chameleon.PageTemplateFile``. Bare Chameleon has no TAL path
  expressions -- ``${member/fullname}`` raises ``NameError`` -- and z3c.jbot
  patches only the Zope classes, so jbot overridability of our own templates
  (§4) depends on this class specifically.
* Without the ``IPageTemplateEngine`` utility, zope.pagetemplate falls back to
  zope.tal, where ``${...}`` passes through **verbatim with no error** while
  ``tal:repeat`` still works. Any test over this module must assert on
  substituted *values*, never on marker strings.

Two things worth knowing before you import from here:

* ``imio.emailkit.__init__`` rebinds the name ``render`` on the package to the
  *function*, because that is the API §6.1 documents. So
  ``from imio.emailkit import render`` gives the function and
  ``import imio.emailkit.render as m`` gives the function **too**. To reach this
  module, use ``from imio.emailkit.render import <name>``.
* The formatting helpers are callables in the template namespace, and TAL's
  default expression type is a *path*, which cannot call anything with an
  argument. Templates therefore write ``${python: format_date(item/created)}``,
  not ``${format_date(...)}``, which silently reads as an invalid variable name.
"""

from Acquisition import aq_get
from html import unescape
from imio.emailkit.discovery import get_template
from imio.emailkit.discovery import TEXT_SUFFIX
from imio.emailkit.helpers import bind as bind_locale_helpers
from imio.emailkit.helpers import FALLBACK_LANGUAGE
from imio.emailkit.interfaces import IEmailkitTheme
from imio.emailkit.interfaces import THEME_REGISTRY_PREFIX
from plone.registry.interfaces import IRegistry
from Products.PageTemplates.PageTemplateFile import PageTemplateFile
from zope.component import queryUtility
from zope.component.hooks import getSite
from zope.globalrequest import getRequest
from zope.i18n import translate as zope_translate

import logging
import re


logger = logging.getLogger("imio.emailkit.render")


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
    namespace = build_namespace(template, context, language)

    html = render_file(template.html_path, namespace)
    # `text_path` comes from the cached startup scan, so it can name a file that
    # has since gone -- a rebuild that dropped the twin, or a checkout switch.
    # SPEC §4 asks for a warning and a fallback when the twin is missing, and it
    # is the same situation whether it was never there or vanished afterwards.
    # Without the existence re-check this raised FileNotFoundError instead.
    if template.text_path is None or not template.text_path.exists():
        text = _fallback_text(template, html)
    else:
        text = render_file(template.text_path, namespace)
    return html, text


def build_namespace(template, context, language):
    """Assemble the namespace ``render()`` hands to both compiled templates.

    Precedence, low to high: the registration's ``preheader``, then the caller's
    ``context``, then the names this package injects. The injected names win
    because the kit layout uses them unconditionally -- a caller who shadowed
    ``theme`` or ``lang`` would break the shell, not just their own template.
    """
    namespace = {}
    if template.preheader is not None:
        namespace["preheader"] = zope_translate(
            template.preheader, target_language=language
        )
    if context:
        namespace.update(context)

    namespace.update(locale_helpers(language))
    namespace.update({
        "lang": language,
        "theme": get_theme(),
        "portal_url": portal_url(),
        "translate": _translate_helper(language),
        # Zope's page-template i18n machinery reads the render language from
        # this name. Without it `i18n:translate` negotiates from the request --
        # i.e. renders the wrong language, silently, whenever `language` was
        # passed explicitly.
        "target_language": language,
    })
    return namespace


def locale_helpers(language):
    """SPEC §6.1's formatting helpers, bound to ``language``.

    A thin re-export of :func:`imio.emailkit.helpers.bind`, kept here because the
    namespace assembly above is the only caller and because "what does render()
    put in the namespace" should be answerable from this file alone.
    """
    return bind_locale_helpers(language)


def get_theme():
    """Return SPEC §3's theme tokens, read from ``plone.app.registry``.

    Missing registry, missing record and ``None`` all collapse to the empty
    string: a token is interpolated straight into markup, and the string
    ``"None"`` in a mail header is worse than nothing. The token *names* come
    from :class:`~imio.emailkit.interfaces.IEmailkitTheme`, which is also what
    ``profiles/base`` builds the records from -- one source of truth.
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

    Same order as ``plone.api.portal.get_current_language``, minus its two ways
    of raising outside a request: the request's negotiated language, then the
    site's default, then English.
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

    ``absolute_url()`` needs a REQUEST to know the server part, so the guard is
    on the REQUEST rather than a bare ``except``: a preview or unit test with no
    request gets an empty string instead of a traceback, and everything else
    gets the real URL.
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

    Instances are cached for two reasons: ``PageTemplateFile`` re-cooks itself
    when the file's mtime changes, so caching costs no freshness; and z3c.jbot
    keys its own registry on the template object, so a fresh instance per render
    would leak an entry per mail sent.

    z3c.jbot's patches turn ``PageTemplateFile`` into a *descriptor*, which is
    how an override is substituted -- but a descriptor only fires through
    attribute access on a class, and we hold ours in a dict. Invoking ``__get__``
    by hand is therefore what makes SPEC §4's "z3c.jbot works on the resolved
    ``.pt`` files" true for our own templates. ``__get__`` is absent until
    ``z3c.jbot.patches`` is imported, hence the guard rather than a bare call.
    """
    key = str(path)
    template = _page_templates.get(key)
    if template is None:
        template = _page_templates[key] = PageTemplateFile(key)
    bind = getattr(template, "__get__", None)
    return template if bind is None else bind(None, None)


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
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_LINE_BREAK = re.compile(
    r"<br\s*/?>|</(?:p|div|tr|li|h[1-6]|table|blockquote)\s*>", re.IGNORECASE
)
_TAG = re.compile(r"<[^>]+>")
_BLANK_RUN = re.compile(r"\n{3,}")

# Elements hidden from sighted readers must not survive into the plaintext part.
# The preheader is the one that matters: the kit pads it to fill the inbox
# preview budget, so keeping it makes every plaintext mail open with the preview
# line followed by a run of invisible filler (U+2007, U+FEFF, U+034F). Naive
# single-level match, in keeping with the rest of this function -- the preheader
# holds text, not nested blocks.
_HIDDEN_ELEMENT = re.compile(
    r"<(?P<tag>\w+)[^>]*style=\"[^\"]*display:\s*none[^\"]*\"[^>]*>"
    r".*?</(?P=tag)\s*>",
    re.IGNORECASE | re.DOTALL,
)

# Zero-width characters are layout tricks for HTML mail and are noise -- or worse,
# mojibake -- in a plaintext part. The kit emits them around the preheader and to
# keep Outlook from collapsing empty cells.
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
    """SPEC §4's documented fallback when a template ships no ``.txt.pt`` twin.

    Logged once per template per process rather than per render: a mail loop
    would otherwise bury the rest of the log, and the point of the message is
    that a file is missing, which is not going to change mid-process.
    """
    if template.name not in _warned_missing_twin:
        _warned_missing_twin.add(template.name)
        logger.warning(
            "DEPRECATION: %s ships no %s twin, so its plaintext part comes from "
            "naive extraction of the HTML. Ship a plaintext twin (SPEC §4).",
            template.name,
            TEXT_SUFFIX,
        )
    return naive_text(html)


def naive_text(html):
    """Strip ``html`` down to something readable. Naive by design, per SPEC §4."""
    text = _SCRIPT_OR_STYLE.sub("", html)
    text = _COMMENT.sub("", text)
    text = _HIDDEN_ELEMENT.sub("", text)
    text = _LINE_BREAK.sub("\n", text)
    text = _TAG.sub("", text)
    text = unescape(text)
    text = _ZERO_WIDTH.sub("", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_RUN.sub("\n\n", text).strip() + "\n"
