"""The *"Send styled email"* content-rule action.

Four objects, which is what ``plone.contentrules`` asks any action for:

:class:`IStyledMailAction`
    what a manager configures: which registered template, and who receives it.
:class:`StyledMailAction`
    the configuration, stored in the rule. A data holder, like the builder it
    feeds.
:class:`StyledMailActionExecutor`
    the whole behaviour: build an :class:`~imio.emailkit.email.Email`, hand it
    the recipients and the render context, ``.send()``.
:class:`StyledMailAddForm` / :class:`StyledMailEditForm`
    the two z3c.form forms, subclassed from ``plone.app.contentrules``' own
    bases so the action looks and behaves like every other one in the panel.

Three things are deliberate and are the reason this module is short.

**The executor delegates and does not decide.** The builder is frozen and this
is a caller of it. There is no retry, no queue, no digest, no "skip if" -- a
content rule fires, and that is deliberately all it does. Per-language
rendering, subject translation, message assembly and transaction-bound delivery
are all the builder's, already, and reimplementing any of them here would be a
second code path for the mails somebody automated.

**Nothing is swallowed.** A content rule that quietly does not send is
indistinguishable from no rule at all, so every failure travels: an unknown
template raises ``TemplateNotFound``, an unresolvable recipient raises
``RecipientError``, an unset site sender raises ``EmailkitError``. The one
``except`` in this module logs which rule context, which template and which
recipients, and then re-raises. ``plone.contentrules``' executor does not catch
exceptions either, so the failure surfaces on the operation that triggered the
rule and the transaction rolls back -- which is also why the builder's queued
delivery means nothing was sent.

**Exactly two recipient sources**: the explicit list a manager types, and the
triggering content's owner. Both are handed to ``.to()`` as values, never
resolved here: the builder already accepts "an email string, a Plone member
object, a userid, or an iterable of those" through one adapter, and resolving
an address in this module would be the second implementation that eventually
disagrees with the first. The owner is passed as a **userid** for that
reason -- the member adapter then supplies the display name *and* the preferred
language, which is what makes the builder's per-language sending work from a
rule.

The render context, for template authors
----------------------------------------

Nothing says what a rule-triggered mail renders against, and a content
rule cannot know what an arbitrary template wants -- so the set is **fixed, small
and closed**, and this is its authoritative definition. It is
:data:`RENDER_CONTEXT_NAMES`, built by :func:`render_context`:

==============  =============================================================
``item``        the triggering content object (``event.object``, or the rule's
                own context for the few events that carry none). Path
                traversable, so a template needing more than the scalars below
                writes ``${item/Creator}`` and nothing has to be added here.
``title``       ``item.Title()``
``intro``       ``item.Description()``
``cta_label``   the label of the call-to-action button -- an i18n **msgid**
``cta_url``     ``item.absolute_url()``
==============  =============================================================

Those are exactly the four scalars the kit's own ``notification`` template
consumes, plus the object. A template that wants a name this does not supply
fails loudly at render time, which is the right outcome: the fix is to pick a
template written for a content rule, not to have the rule invent data.

**Why ``cta_label`` is a msgid and not a string.** ``.with_context()`` is called
once, *before* ``.send()`` groups recipients by language, so a value
translated in this module would be one language for every group -- a Dutch
recipient would get a French button. A ``zope.i18nmessageid`` message is left
untranslated in the context and translated by the page template at render time,
against the ``target_language`` ``render()`` injects, so the single context
value yields the right label in each language group. Anything else a future
context name needs to say in the recipient's language must be a msgid for the same
reason; a plain string here is a silent per-language bug.
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

#: The rule element's name: the key the stored action carries in its ``element``
#: attribute, the name of the ``IRuleAction`` utility, and the name of the add
#: view. All three are the same string in every ``plone.contentrules`` action,
#: and a rule already stored in a database holds it -- so it is API and does not
#: get renamed. ``configure.zcml`` spells it again, because a ZCML attribute
#: cannot reference a Python constant; ``tests/test_contentrules.py`` asserts the
#: registered element's ``addview`` equals this, so the two cannot drift silently.
ELEMENT_NAME = "imio.emailkit.actions.StyledMail"

#: The edit view's name. ``"edit"`` for every action in Plone, because the
#: registration is ``for`` the action's own schema and the name only has to be
#: unique per interface.
EDIT_VIEW_NAME = "edit"

#: The label of the CTA button in the kit's ``notification`` template, as an i18n
#: **msgid** rather than a translated string. That is not a detail: ``.send()``
#: renders once per language group and ``.with_context()`` is called once,
#: before any grouping, so a string translated here would reach a Dutch recipient
#: in French. A message object is translated by the page template at render time,
#: against the ``target_language`` ``render()`` injects -- so one context
#: value yields the right label in every group.
CTA_LABEL = _("email_cta_view_item", default="View this item")


class IStyledMailAction(Interface):
    """The action's configuration: one template, and who gets it.

    Deliberately **no body field**. TTW template markup editing is out of scope
    and the markup is dev-owned and versioned in git; choosing a registered
    template from a vocabulary is a selection, not an edit. Deliberately no
    subject field either: the template's registration keeps the subject as a
    msgid so it is translated per recipient language, and a subject typed into a
    rule would be one language for every commune.
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

    Class attributes are the defaults for an action stored before a field
    existed; ``recipients`` is an empty **tuple** because a mutable class
    attribute shared by every instance is how one rule's recipients end up in
    another's.
    """

    template = ""
    recipients = ()
    send_to_owner = False

    element = ELEMENT_NAME

    @property
    def summary(self):
        """The one-line description the rule's element list shows.

        Three msgids rather than one sentence with an interpolated owner label:
        a mapping value is ``str()``-ed during interpolation, so a message object
        put there would render as its bare msgid. Each of the three configurations
        the form allows therefore gets a whole, translatable sentence, and the
        placeholders travel into the catalogs where translators can move them.
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
    """The executor delegates to ``Email(...)`` and decides nothing else.

    That is the whole specification of this class, and the body of
    :meth:`__call__` is meant to read as one statement plus a log line.
    """

    def __init__(self, context, element, event):
        self.context = context
        self.element = element
        self.event = event

    def __call__(self):
        """Send the configured template. Returns ``True``; raises on any failure.

        ``plone.contentrules`` stops executing a rule when an element returns
        ``False``, which makes ``False`` the quiet way to fail -- so this method
        never returns it. A problem is an exception, it reaches the operation
        that triggered the rule, and the transaction that would have delivered
        the mail rolls back.
        """
        item = self.triggering_object()
        recipients = self.recipient_values(item)
        try:
            # The builder's contract, and nothing else. Note the absence of
            # `.subject()`: the registration keeps the subject so it is
            # translated per recipient language, and a rule has no business
            # overriding that.
            messages = (
                Email(self.element.template)
                .to(recipients)
                .with_context(**render_context(item))
                .send()
            )
        except Exception:
            # Logged then re-raised, never handled: the log line is what a
            # sysadmin reads, the exception is what stops the transaction.
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
        """The content the mail is about.

        ``event.object`` for every content event, which is all of them that
        matter here. The rule's own context is the documented fallback for the
        handful of events that carry no object at all (a login, a user created),
        where ``plone.app.contentrules`` executes rules assigned to the site
        root -- so the fallback is the site, not a guess.
        """
        item = getattr(self.event, "object", None)
        if item is None:
            item = self.context
        return aq_inner(item)

    def recipient_values(self, item):
        """The action's two recipient sources, as values for ``.to()``.

        Not resolved, not validated, not deduplicated: ``.to()`` accepts exactly
        these shapes and ``.send()`` reports every one it cannot resolve in a
        single ``RecipientError``. Doing any of it here would mean two
        implementations of one rule.
        """
        values = list(self.element.recipients or ())
        if self.element.send_to_owner:
            values.append(owner_userid(item))
        return values


def owner_userid(item):
    """The userid of ``item``'s owner, as a ``.to()`` value.

    A **userid** rather than an address on purpose: the member adapter then
    supplies the display name and the preferred language too, so a rule
    that mails owners mails a Dutch owner in Dutch with no configuration.

    :raises RecipientError: when no owner userid can be found.

    Raising rather than returning nothing is the whole point. Silently dropping
    this recipient would send the mail to everyone *else* the rule names, and the
    manager who ticked the box would have no way to notice.
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


#: The names :func:`render_context` supplies, i.e. the context a template must be
#: written against to be usable from a content rule. Stated as a constant because
#: it is the action's contract with template authors, and because widening it
#: silently is how a set like this stops being documentable.
RENDER_CONTEXT_NAMES = ("item", "title", "intro", "cta_label", "cta_url")


def render_context(item):
    """The names this action puts in the render namespace.

    Nothing says what a rule-triggered mail renders against, and a content
    rule cannot know what an arbitrary template wants -- so the set is fixed and
    small (:data:`RENDER_CONTEXT_NAMES`). It is exactly the four scalars the
    kit's own ``notification`` template consumes, plus the object:

    ``item``
        the triggering content object. Path-traversable, so a template that
        needs more than the four scalars writes ``${item/Creator}`` and needs
        nothing added here.
    ``title`` / ``intro``
        the object's title and description.
    ``cta_label`` / ``cta_url``
        the button. ``cta_label`` is a **msgid**, translated per language group
        at render time; see :data:`CTA_LABEL`.

    A template that wants a name this does not supply fails loudly at render
    time, which is the correct outcome: the fix is to pick a template written for
    a content rule, not to have the rule invent data.
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
# The forms
# ---------------------------------------------------------------------------
#
# Subclassed from `plone.app.contentrules`' own bases rather than from z3c.form
# directly: they carry the Save/Cancel buttons, the redirect back to the rule's
# element list, and the panel's form chrome. There is no custom template -- the
# stock mail action ships one only to explain `plone.stringinterp`
# substitutions, which this action deliberately does not have.


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
# The rule element itself is registered by `configure.zcml`'s `plone:ruleAction`
# directive, which builds the `IRuleAction` utility from its own arguments. There
# is deliberately no element class here: `plone.contentrules` owns that object,
# and the directive is how every Plone add-on hands it the title, description,
# schema, factory and view names.
#
# One consequence worth knowing before somebody "fixes" it: the directive's
# `title` and `description` are `schema.TextLine`/`schema.Text`, not
# `zope.configuration.fields.MessageID`, so those two strings cannot be msgids and
# the action's entry in the content-rules panel is English. That is what every
# stock Plone action does ("Send email", "Notify user"). Everything this action
# shows *inside* its own forms -- labels, help text, the summary line -- goes
# through `_()` and is translated FR/NL/DE.
# ---------------------------------------------------------------------------
