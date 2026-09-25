"""The *"Send styled email"* content-rule action.

Four objects, what ``plone.contentrules`` asks any action for:

:class:`IStyledMailAction`
    what a manager configures: which registered template, and who receives it.
:class:`StyledMailAction`
    the configuration, stored in the rule.
:class:`StyledMailActionExecutor`
    build an :class:`~imio.emailkit.email.Email`, hand it the recipients and
    render context, ``.send()``.
:class:`StyledMailAddForm` / :class:`StyledMailEditForm`
    the two z3c.form forms, subclassed from ``plone.app.contentrules``.

The executor decides nothing else and swallows nothing: an unknown template,
an unresolvable recipient or an unset site sender all raise, after the one
``except`` here logs the rule context, template and recipients.

There are exactly two recipient sources, both handed to ``.to()`` unresolved:
the explicit list a manager types, and the triggering content's owner, passed
as a userid so the member adapter also supplies the preferred language.

The render context, for template authors
----------------------------------------

A content rule cannot know what an arbitrary template wants, so the render
context is fixed and small: :data:`RENDER_CONTEXT_NAMES`, built by
:func:`render_context`.

==============  =============================================================
``item``        the triggering content object (``event.object``, or the
                rule's own context). Path traversable.
``title``       ``item.Title()``
``intro``       ``item.Description()``
``cta_label``   the label of the call-to-action button, an i18n msgid
``cta_url``     ``item.absolute_url()``
==============  =============================================================

These are the four scalars the kit's own ``notification`` template consumes,
plus the object. A template needing a name this does not supply fails loudly
at render time.

``cta_label`` is a msgid, not a string: ``.send()`` groups recipients by
language after ``.with_context()`` already ran once, so a translated string
would reach every group the same way. The page template translates the msgid
at render time instead.
"""

from Acquisition import aq_inner
from imio.emailkit import _
from imio.emailkit import Email
from imio.emailkit.interfaces import RecipientError
from imio.emailkit.vocabularies import TEMPLATES as TEMPLATES_VOCABULARY
from OFS.SimpleItem import SimpleItem
from plone.app.contentrules.actions import ActionAddForm
from plone.app.contentrules.actions import ActionEditForm
from plone.app.contentrules.browser.formhelper import ContentRuleFormWrapper
from plone.contentrules.rule.interfaces import IExecutable
from plone.contentrules.rule.interfaces import IRuleElementData
from zope import schema
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface

import logging


logger = logging.getLogger("imio.emailkit.contentrules")

#: The rule element's name, also the ``IRuleAction`` utility and add-view
#: names. A stored rule holds this string, so it does not get renamed.
#: ``configure.zcml`` spells it again; ``tests/test_contentrules.py`` asserts
#: they match.
ELEMENT_NAME = "imio.emailkit.actions.StyledMail"

#: The edit view's name. ``"edit"`` for every action in Plone.
EDIT_VIEW_NAME = "edit"

#: The label of the CTA button in the kit's ``notification`` template, as an
#: i18n msgid rather than a translated string: see the module docstring.
CTA_LABEL = _("email_cta_view_item", default="View this item")


class IStyledMailAction(Interface):
    """The action's configuration: one template, and who gets it.

    No body field: the markup is dev-owned and versioned in git; choosing a
    registered template is a selection, not an edit. No subject field either:
    the template's registration keeps the subject as a msgid, translated per
    recipient language.
    """

    template = schema.Choice(
        title=_("label_styledmail_template", default="Email template"),
        description=_(
            "help_styledmail_template",
            default=(
                "The styled template this rule sends. The list holds every "
                "template registered by every installed add-on; a template's "
                "name is <package>:<template>, because three add-ons may each "
                "ship one called 'notification'."
            ),
        ),
        vocabulary=TEMPLATES_VOCABULARY,
        required=True,
    )

    recipients = schema.List(
        title=_("label_styledmail_recipients", default="Email recipients"),
        description=_(
            "help_styledmail_recipients",
            default=(
                "One entry per recipient: an email address, or the id of a "
                "Plone user. Prefer the user id where you can, because the "
                "mail is then rendered and its subject translated in that "
                "user's own preferred language."
            ),
        ),
        value_type=schema.TextLine(),
        required=False,
        missing_value=None,
    )

    send_to_owner = schema.Bool(
        title=_(
            "label_styledmail_send_to_owner",
            default="Also send to the owner of the content",
        ),
        description=_(
            "help_styledmail_send_to_owner",
            default=(
                "Send to the owner of the content that triggered the rule, in "
                "addition to the recipients above. The rule fails loudly rather "
                "than sending to fewer people if the owner cannot be resolved."
            ),
        ),
        required=False,
        default=False,
    )


@implementer(IStyledMailAction, IRuleElementData)
class StyledMailAction(SimpleItem):
    """The stored configuration of one *"Send styled email"* action.

    ``recipients`` is an empty tuple, not a list: a mutable class attribute
    shared by every instance would let one rule's recipients leak into
    another's.
    """

    template = ""
    recipients = ()
    send_to_owner = False

    element = ELEMENT_NAME

    @property
    def summary(self):
        """The one-line description the rule's element list shows.

        Three msgids, not an interpolated owner label: a mapping value is
        ``str()``-ed, so a message object there would show its bare msgid.
        """
        mapping = {
            "template": self.template,
            "recipients": ", ".join(self.recipients or ()),
        }
        if not self.send_to_owner:
            return _(
                "summary_styledmail",
                default='Send the styled email "${template}" to ${recipients}',
                mapping=mapping,
            )
        if not self.recipients:
            return _(
                "summary_styledmail_owner_only",
                default=(
                    'Send the styled email "${template}" to the owner of the content'
                ),
                mapping=mapping,
            )
        return _(
            "summary_styledmail_and_owner",
            default=(
                'Send the styled email "${template}" to ${recipients} and to '
                "the owner of the content"
            ),
            mapping=mapping,
        )


@implementer(IExecutable)
@adapter(Interface, IStyledMailAction, Interface)
class StyledMailActionExecutor:
    """The executor delegates to ``Email(...)`` and decides nothing else."""

    def __init__(self, context, element, event):
        self.context = context
        self.element = element
        self.event = event

    def __call__(self):
        """Send the configured template. Returns ``True``; raises on failure.

        ``plone.contentrules`` stops a rule when an element returns
        ``False``, so this never returns it: a problem is always an exception.
        """
        item = self.triggering_object()
        recipients = self.recipient_values(item)
        try:
            # No `.subject()`: the registration keeps the subject so it is
            # translated per recipient language.
            messages = (
                Email(self.element.template)
                .to(recipients)
                .with_context(**render_context(item))
                .send()
            )
        except Exception:
            # The log line is for a sysadmin; the exception stops the transaction.
            logger.exception(
                "Content rule action %s failed on %s: template=%r, "
                "recipients=%r (send_to_owner=%r)",
                ELEMENT_NAME,
                path_of(item),
                self.element.template,
                recipients,
                self.element.send_to_owner,
            )
            raise
        logger.info(
            "Content rule action %s queued %s message(s) of %r for %s, recipients=%r",
            ELEMENT_NAME,
            len(messages),
            self.element.template,
            path_of(item),
            recipients,
        )
        return True

    def triggering_object(self):
        """The content the mail is about: ``event.object``, or the rule's own
        context for the events (such as a login) that carry no object."""
        item = getattr(self.event, "object", None)
        if item is None:
            item = self.context
        return aq_inner(item)

    def recipient_values(self, item):
        """The action's two recipient sources, unresolved, as values for
        ``.to()``: ``.to()`` and ``.send()`` already resolve and validate."""
        values = list(self.element.recipients or ())
        if self.element.send_to_owner:
            values.append(owner_userid(item))
        return values


def owner_userid(item):
    """The userid of ``item``'s owner, as a ``.to()`` value.

    A userid, not an address: the member adapter then also supplies the
    preferred language.

    :raises RecipientError: when no owner userid can be found, rather than
        silently mailing fewer people than the rule asks for.
    """
    get_owner = getattr(item, "getOwner", None)
    owner = get_owner() if callable(get_owner) else None
    userid = owner.getId() if owner is not None else None
    if not userid:
        raise RecipientError([
            f"{path_of(item)} has no resolvable owner, so "
            f"'{ELEMENT_NAME}' cannot name the recipient it was configured to "
            f"send to. Refusing to send to fewer people than the rule asks for."
        ])
    return userid


#: The context names a template must be written against to be usable from a
#: content rule. This is the action's contract with template authors.
RENDER_CONTEXT_NAMES = ("item", "title", "intro", "cta_label", "cta_url")


def render_context(item):
    """The names this action puts in the render namespace.

    ``item``
        the triggering content object. Path-traversable, so a template that
        needs more writes ``${item/Creator}``.
    ``title`` / ``intro``
        the object's title and description.
    ``cta_label`` / ``cta_url``
        the button. ``cta_label`` is a msgid; see :data:`CTA_LABEL`.

    A template that wants a name this does not supply fails loudly at render
    time: pick a template written for a content rule instead.
    """
    return {
        "item": item,
        "title": item.Title(),
        "intro": item.Description(),
        "cta_label": CTA_LABEL,
        "cta_url": item.absolute_url(),
    }


def path_of(item):
    """``item``'s physical path, for a log line. Never raises."""
    get_path = getattr(item, "getPhysicalPath", None)
    if not callable(get_path):
        return repr(item)
    return "/".join(get_path())


# ---------------------------------------------------------------------------
# The forms: subclassed from `plone.app.contentrules`, which supplies the
# Save/Cancel buttons and the panel's form chrome. No custom template.
# ---------------------------------------------------------------------------


class StyledMailAddForm(ActionAddForm):
    """Add form for the styled-mail action."""

    schema = IStyledMailAction
    label = _("label_add_styledmail_action", default="Add Send styled email action")
    description = _(
        "help_add_styledmail_action",
        default=(
            "Send one of the styled email templates shipped by the installed "
            "add-ons. The template owns the markup and the subject; this form "
            "chooses which one and who receives it."
        ),
    )
    form_name = _("legend_styledmail_configure", default="Configure element")
    Type = StyledMailAction


class StyledMailAddFormView(ContentRuleFormWrapper):
    form = StyledMailAddForm


class StyledMailEditForm(ActionEditForm):
    """Edit form for the styled-mail action."""

    schema = IStyledMailAction
    label = _("label_edit_styledmail_action", default="Edit Send styled email action")
    description = StyledMailAddForm.description
    form_name = StyledMailAddForm.form_name


class StyledMailEditFormView(ContentRuleFormWrapper):
    form = StyledMailEditForm


# ---------------------------------------------------------------------------
# `configure.zcml`'s `plone:ruleAction` directive registers the rule element
# and builds the `IRuleAction` utility; there is no element class here. Its
# `title`/`description` are plain strings, not msgids, so the action's entry
# in the content-rules panel is English, like every stock Plone action.
# Everything inside its own forms goes through `_()` and ships FR/NL/DE.
# ---------------------------------------------------------------------------
