"""Phase 0 assumption (d): a Maizzle-compiled ``.pt`` wins as a ``z3c.jbot``
override of a stock Plone mail template, and its ``${...}`` placeholders really
resolve (as opposed to being passed through verbatim).

The override file under ``emailkit_spike/overrides/`` is a **byte-identical copy**
of ``spike/maizzle/dist/mail_password.pt`` -- real Maizzle 6 build output. It is
never hand-edited; that is the whole point of the test.

Two findings are pinned down as tests rather than papered over:

* ``test_override_wins_at_lookup`` / ``test_stock_view_call_renders_the_override``
  -- the override wins, and ``${...}`` is genuinely *evaluated* by the Chameleon
  engine. The evaluation blows up because the compiled template's placeholder
  names (``member``, ``reset_url``, ``lang``) do not exist in the stock
  ``PasswordResetToolView`` namespace -- keyword arguments passed to a
  ``Products.Five`` ``ViewPageTemplateFile`` land in ``options``, not at the top
  level. A verbatim pass-through would have rendered silently instead.
* ``test_member_data_is_not_path_traversable`` -- even bound at top level,
  ``member/email`` cannot traverse a Plone ``MemberData``; that is why the stock
  template writes ``python:member.getProperty('email')``.
"""

from emailkit_spike.interfaces import IEmailkitSpikeLayer
from plone.app.testing import TEST_USER_ID
from zope.component import getMultiAdapter
from zope.component import queryUtility
from zope.interface import alsoProvides
from zope.location.interfaces import LocationError
from zope.pagetemplate.interfaces import IPageTemplateEngine

import os
import pytest


# Marker attribute that exists only in the Maizzle build output.
OVERRIDE_MARKER = 'data-emailkit-override="mail_password"'

# Content that exists only in the stock CMFPlone template.
STOCK_MARKERS = (
    "mailtemplate_text_linkreset",
    "mailtemplate_reset_information",
    "mailtemplate_text_expirationdate_linkreset",
    "Precedence: bulk",
    "Content-Type: text/plain",
)

OVERRIDE_FILENAME = (
    "Products.CMFPlone.browser.login.templates.mail_password_template.pt"
)

FULLNAME = "Zoe Testeuse"
EMAIL = "zoe.testeuse@example.be"
RESET_URL = "http://nohost/plone/passwordreset/deadbeefdeadbeef"


@pytest.fixture
def member(portal):
    mtool = portal.portal_membership
    mtool.getMemberById(TEST_USER_ID).setMemberProperties(
        {"fullname": FULLNAME, "email": EMAIL}
    )
    return mtool.getMemberById(TEST_USER_ID)


@pytest.fixture
def request_with_layer(portal):
    # This throwaway addon has no GS profile / browserlayer.xml, so mark the
    # request by hand. z3c.jbot derives its layer from providedBy(request).
    request = portal.REQUEST
    alsoProvides(request, IEmailkitSpikeLayer)
    return request


@pytest.fixture
def view(portal, request_with_layer):
    return getMultiAdapter(
        (portal, request_with_layer), name="mail_password_template"
    )


@pytest.fixture
def template(view):
    """The jbot-resolved ViewPageTemplateFile behind the view."""
    return view.index.__func__


@pytest.fixture
def rendered(template, view, request_with_layer, member):
    """Render the *jbot-resolved override file* with the placeholder names bound.

    See the module docstring: the stock view namespace does not provide
    ``member`` / ``reset_url`` / ``lang``, and ``MemberData`` is not path
    traversable. So the names are bound explicitly, in the shape SPEC §6.1's
    ``render(template, context)`` will provide -- a flat context mapping, whose
    values are read off the real fixture member.
    """
    namespace = template.pt_getContext(
        instance=view, request=request_with_layer, args=(), options={}
    )
    namespace.update(
        member={
            "fullname": member.getProperty("fullname"),
            "email": member.getProperty("email"),
        },
        reset_url=RESET_URL,
        lang="fr",
    )
    return template.pt_render(namespace)


# --------------------------------------------------------------------------
# (d) the override wins
# --------------------------------------------------------------------------


def test_override_wins_at_lookup(template):
    """jbot swapped the template file for the Maizzle build output."""
    assert os.path.basename(template.filename) == OVERRIDE_FILENAME
    assert template.filename.endswith(
        os.path.join("emailkit_spike", "overrides", OVERRIDE_FILENAME)
    )
    # jbot stashes the shadowed original here -- it is the real CMFPlone file.
    assert template._filename.endswith(
        os.path.join(
            "Products", "CMFPlone", "browser", "login", "templates",
            "mail_password_template.pt",
        )
    )


def test_page_template_engine_is_chameleon(portal):
    """Guard against the plain zope.tal fallback, under which ``${...}`` would
    pass through verbatim and a green "override won" test would be a lie.

    (``portal`` is requested only to force the layer -- and therefore the ZCA
    registry it pushes -- to be set up.)"""
    engine = queryUtility(IPageTemplateEngine)
    assert engine is not None
    assert engine.__module__ == "Products.PageTemplates.engine"


def test_stock_view_call_renders_the_override(view, member, portal):
    """Calling the view exactly the way RegistrationTool does proves two things
    at once: it is the *override* that renders, and ``${...}`` is really
    evaluated rather than emitted verbatim."""
    reset = portal.portal_password_reset.requestReset(TEST_USER_ID)
    with pytest.raises(KeyError) as exc_info:
        # Mirrors Products/CMFPlone/RegistrationTool.py:391-394
        view(
            member=member,
            reset=reset,
            password=member.getPassword(),
            charset="utf-8",
        )
    # The compiled template's placeholder names are not in the view namespace:
    # ViewPageTemplateFile puts keyword arguments in ``options``, not top level.
    assert exc_info.value.args[0] == "member"
    # Chameleon annotates the error with the expression it was evaluating.
    # ``member/email`` exists *only* in the Maizzle override -- the stock
    # template writes ``python:member.getProperty('email')`` -- so this pins
    # both facts: the override rendered, and its ``${...}`` was evaluated.
    annotated = str(exc_info.value)
    assert 'Expression: "member/email"' in annotated
    # Chameleon truncates the filename to its tail, so match on that.
    assert "mail_password_template.pt" in annotated


def test_member_data_is_not_path_traversable(template, view, request_with_layer, member):
    """``${member/email}`` cannot traverse a Plone MemberData even when
    ``member`` *is* bound -- hence the stock template's ``python:`` expression."""
    namespace = template.pt_getContext(
        instance=view, request=request_with_layer, args=(), options={}
    )
    namespace.update(member=member, reset_url=RESET_URL, lang="fr")
    with pytest.raises(LocationError):
        template.pt_render(namespace)


# --------------------------------------------------------------------------
# the rendered output of the Maizzle build
# --------------------------------------------------------------------------


def test_rendered_output_is_the_override_not_the_stock_template(rendered):
    assert OVERRIDE_MARKER in rendered
    for stock in STOCK_MARKERS:
        assert stock not in rendered, f"stock template leaked: {stock!r}"


def test_placeholders_resolved(rendered):
    """``${...}`` was substituted, not passed through."""
    assert FULLNAME in rendered
    assert EMAIL in rendered
    assert RESET_URL in rendered
    assert 'lang="fr"' in rendered
    assert "${" not in rendered, "unsubstituted Chameleon placeholder in output"
    assert "member/fullname" not in rendered


def test_inlined_css_survived(rendered):
    """Maizzle's CSS inlining survived compilation, jbot and Chameleon."""
    assert 'style="font-size: 16px; line-height: 24px; color: #374151;"' in rendered
    assert "max-width: 576px" in rendered


def test_i18n_translate_processed(rendered):
    """The i18n:translate in the mail's Subject header was processed."""
    assert "Subject:" in rendered
    assert "i18n:translate" not in rendered
    assert "Reset your password" in rendered


def test_mso_conditional_comments_survived(rendered):
    """Outlook conditional comments are not eaten by the TAL parser."""
    assert "<!--[if mso]>" in rendered
    assert "o:PixelsPerInch" in rendered


def test_write_evidence_artifact(rendered):
    """Commit the render as Phase 0 evidence for (d)."""
    target = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "rendered",
        "mail_password.jbot.html",
    )
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(rendered)
    assert os.path.getsize(target) > 0


# --------------------------------------------------------------------------
# negative control: the override must be gated on the browser layer
# --------------------------------------------------------------------------


def test_without_the_layer_the_stock_template_wins(portal):
    """Unmarked request -> jbot must not swap the template."""
    request = portal.REQUEST
    assert not IEmailkitSpikeLayer.providedBy(request), (
        "request leaked the layer from another test"
    )
    view = getMultiAdapter((portal, request), name="mail_password_template")
    assert view.index.__func__.filename.endswith(
        os.path.join(
            "CMFPlone", "browser", "login", "templates",
            "mail_password_template.pt",
        )
    )
