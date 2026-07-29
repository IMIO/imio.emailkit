"""SPEC §8.3 -- the *"Send styled email"* content-rule action.

> **Content rules:** a new action type *"Send styled email"* -- edit form offers
> the registered template names (vocabulary from discovery) + recipient sources;
> executor delegates to ``Email(...)``. The stock mail action is left untouched.

The nine gates of ``docs/plans/phase-5.md`` §4, one class each, in order.

Three things shape every assertion here.

**A content rule that quietly does not send is indistinguishable from no rule at
all.** So the error gates are not "an exception is raised somewhere": each one
also asserts that *nothing was delivered*, and the happy-path gates assert that
something *was* -- otherwise "no mail arrived" would pass every test in the
module for the wrong reason.

**Never assert on a marker string.** Without the ``IPageTemplateEngine`` utility
zope.pagetemplate falls back to zope.tal, where ``${...}`` reaches the inbox
verbatim and nothing raises (``docs/DECISIONS.md``). Gate 5 therefore asserts on
*substituted values* -- the triggering object's real title, its real URL, and a
CTA label whose FR and NL translations differ -- and runs
``support.assert_message_is_clean`` over both MIME parts.

**The registration is checked in both registries.** Everything here -- element,
executor, forms -- is plain global ZCML, exactly like every other Plone
content-rule action, and gate 1 asserts that in the global registry *and* that the
site adds no registration of its own. A per-site local utility installed by the
``:default`` profile was built and then deliberately reverted: it looks identical
from inside the site, and it stores a copy of the element that drifts from the ZCML
with no symptom. The last class in this module states the consequence -- a
``:base`` site has the action type too -- and why that is correct rather than a
leak.
"""

from plone.app.contentrules import api as contentrules_api
from plone.app.contentrules.actions.mail import MailAction
from plone.app.contentrules.browser.elements import ManageElements
from plone.app.contentrules.rule import Rule
from plone.contentrules.engine.interfaces import IRuleStorage
from plone.contentrules.engine.utils import allAvailableActions
from plone.contentrules.rule.interfaces import IExecutable
from plone.contentrules.rule.interfaces import IRuleAction
from zope.component import getGlobalSiteManager
from zope.component import getMultiAdapter
from zope.component import getSiteManager
from zope.component import getUtility
from zope.component.hooks import site as current_site
from zope.interface import implementer
from zope.interface.interfaces import IObjectEvent
from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.schema.interfaces import IVocabularyFactory

import dummyaddons
import logging
import pytest
import support
import transaction


support.require_runtime()

from imio.emailkit.contentrules.mail import CTA_LABEL  # noqa: E402
from imio.emailkit.contentrules.mail import EDIT_VIEW_NAME  # noqa: E402
from imio.emailkit.contentrules.mail import ELEMENT_NAME  # noqa: E402
from imio.emailkit.contentrules.mail import IStyledMailAction  # noqa: E402
from imio.emailkit.contentrules.mail import render_context  # noqa: E402
from imio.emailkit.contentrules.mail import RENDER_CONTEXT_NAMES  # noqa: E402
from imio.emailkit.contentrules.mail import StyledMailAction  # noqa: E402
from imio.emailkit.contentrules.mail import StyledMailActionExecutor  # noqa: E402
from imio.emailkit.contentrules.mail import StyledMailAddFormView  # noqa: E402
from imio.emailkit.contentrules.mail import StyledMailEditFormView  # noqa: E402
from imio.emailkit.interfaces import RecipientError  # noqa: E402
from imio.emailkit.interfaces import TemplateNotFound  # noqa: E402
from imio.emailkit.vocabularies import TEMPLATES as TEMPLATES_VOCABULARY  # noqa: E402


Email = support.require_builder()

#: The one template this package registers (§4), which is what a rule points at.
TEMPLATE = support.qualified(support.NOTIFICATION)

#: A name nothing is registered under. Gate 7: a rule may hold a template name
#: whose add-on has since been uninstalled, and that must not be a silent skip.
STALE_TEMPLATE = "imio.emailkit:template_that_was_removed"

#: The rule's id in ``IRuleStorage``, and the folder the rule is assigned to.
RULE_ID = "styled-mail-rule"
FOLDER_ID = "dossiers"

#: The triggering content. Title and description are what gate 5 looks for in the
#: rendered mail, so they are distinctive and accented: a charset regression
#: anywhere between ``Title()`` and the MIME part shows up here.
ITEM_ID = "urb-2026-0417"
ITEM_TITLE = "Permis d'urbanisme URB-2026-0417"
ITEM_DESCRIPTION = "L'enquête publique est clôturée; le dossier passe au collège."


@implementer(IObjectEvent)
class Triggered:
    """The minimal object event a rule executor reads.

    ``plone.app.contentrules``' own tests use exactly this: the executor only
    ever looks at ``event.object``, and building a real event would mean picking
    one of the fifteen the panel offers for no gain.
    """

    def __init__(self, obj):
        self.object = obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def as_manager(mail_portal, grant_roles):
    """Content rules are a Manager feature, and creating content needs the role."""
    grant_roles(mail_portal, ["Manager"])
    return mail_portal


@pytest.fixture
def folder(mail_portal, as_manager):
    """The folder a rule gets assigned to.

    Created *before* any rule exists, so its own ``IObjectAddedEvent`` cannot
    trigger the rule under test and inflate the message count.
    """
    from plone import api

    return api.content.create(
        container=mail_portal, type="Folder", id=FOLDER_ID, title="Dossiers"
    )


@pytest.fixture
def storage(mail_portal):
    with current_site(mail_portal):
        return getUtility(IRuleStorage)


@pytest.fixture
def make_action():
    """``make_action(recipients=[...], send_to_owner=True)`` -> a stored action."""

    def make(template=TEMPLATE, recipients=(), send_to_owner=False):
        action = StyledMailAction()
        action.template = template
        action.recipients = list(recipients)
        action.send_to_owner = send_to_owner
        return action

    return make


@pytest.fixture
def make_rule(mail_portal, folder, storage):
    """``make_rule(action)`` -> a rule holding ``action``, assigned to ``folder``.

    The whole chain a manager builds through the panel: a rule in the storage, an
    action in the rule, an assignment on a folder. Nothing here is a shortcut
    past the machinery -- gate 4 needs the real dispatch, not a direct call.

    Returned **traversed** rather than straight out of the storage, because the
    panel views walk up from the rule to build URLs and the storage is not a
    ``getPhysicalPath``-able container. The ``++rule++`` namespace is how Plone's
    own UI reaches a rule, so this is the object the panel actually has.
    """

    def make(action, event=IObjectAddedEvent):
        rule = Rule()
        rule.title = "Send a styled email on add"
        rule.event = event
        rule.actions.append(action)
        storage[RULE_ID] = rule
        contentrules_api.assign_rule(folder, RULE_ID)
        return mail_portal.restrictedTraverse(f"++rule++{RULE_ID}")

    return make


@pytest.fixture
def fire(folder):
    """``fire()`` -> create content in the watched folder, i.e. trigger the rule."""
    from plone import api

    def trigger(**kwargs):
        options = {
            "type": "Document",
            "id": ITEM_ID,
            "title": ITEM_TITLE,
            "description": ITEM_DESCRIPTION,
        }
        options.update(kwargs)
        return api.content.create(container=folder, **options)

    return trigger


@pytest.fixture
def item(folder, as_manager):
    """The triggering object, created with *no* rule assigned.

    For the gates that call the executor directly: they are about what the
    executor does with an object, not about the dispatch that found it.
    """
    from plone import api

    return api.content.create(
        container=folder,
        type="Document",
        id=ITEM_ID,
        title=ITEM_TITLE,
        description=ITEM_DESCRIPTION,
    )


@pytest.fixture
def execute(folder):
    """``execute(action, item)`` -> run the action's executor on ``item``."""

    def run(action, obj):
        executor = getMultiAdapter((folder, action, Triggered(obj)), IExecutable)
        return executor()

    return run


@pytest.fixture
def rule_view(mail_request):
    """``rule_view(rule)`` -> the ``@@manage-elements`` view of a rule.

    The panel page that lists a rule's actions and offers the addable ones. Used
    rather than a raw utility lookup for gate 1, because "appears in the content
    rules control panel" is a statement about that list.
    """

    def make(rule):
        return ManageElements(rule, mail_request)

    return make


# ---------------------------------------------------------------------------
# Gate 1 -- the action type is registered and appears in the panel
# ---------------------------------------------------------------------------


class TestTheActionTypeIsRegistered:
    def test_the_element_is_a_named_rule_action_utility(self, mail_portal):
        element = getUtility(IRuleAction, name=ELEMENT_NAME)

        assert element.schema is IStyledMailAction
        assert element.factory is StyledMailAction
        assert element.addview == ELEMENT_NAME, (
            "the add view name in configure.zcml drifted from ELEMENT_NAME; ZCML "
            "cannot reference the Python constant, so this assertion is what "
            "keeps the two spellings equal"
        )
        assert element.editview == EDIT_VIEW_NAME

    def test_it_is_titled_the_way_SPEC_8_3_names_it(self, mail_portal):
        """§8.3 names the action type verbatim: *"Send styled email"*. That string
        is what a Manager picks out of the panel's list, so it is spec text rather
        than a label somebody chose."""
        element = getUtility(IRuleAction, name=ELEMENT_NAME)

        assert element.title == "Send styled email"
        assert element.description

    def test_it_is_registered_in_zcml_like_every_other_plone_action(self, mail_portal):
        """A plain global ``plone:ruleAction``, and no GenericSetup step.

        Asserted rather than assumed, in both registries, because the alternative
        that was tried and rejected -- a local utility installed by the
        ``:default`` profile -- looks identical from inside the site and stores a
        copy that drifts from the ZCML with no symptom. If this ever becomes a
        local registration again, this is the test that says so.
        """
        globally = getGlobalSiteManager().queryUtility(IRuleAction, name=ELEMENT_NAME)
        locally = getSiteManager(mail_portal).queryUtility(
            IRuleAction, name=ELEMENT_NAME
        )

        assert globally is not None, (
            f"no global IRuleAction utility named {ELEMENT_NAME!r}; SPEC §8.3's "
            f"action type is not registered in ZCML"
        )
        assert locally is globally, (
            "the site has its own registration of the action element, shadowing "
            "the ZCML one"
        )
        assert ELEMENT_NAME not in {
            registration.name
            for registration in getSiteManager(mail_portal).registeredUtilities()
        }, "the action element is registered per site rather than in ZCML"

    @pytest.mark.parametrize(
        "event", [IObjectEvent, IObjectAddedEvent], ids=["any", "added"]
    )
    def test_it_is_offered_for_any_event(self, mail_portal, event):
        """The directive's ``event="*"``: a styled mail is worth sending on any
        trigger, so the action must not disappear depending on the rule's event.

        Matched on ``addview``, because the element objects
        ``allAvailableActions`` returns are all plain ``RuleAction`` instances
        built by the directive and carry no name.
        """
        with current_site(mail_portal):
            offered = {element.addview for element in allAvailableActions(event)}

        assert ELEMENT_NAME in offered, sorted(offered)

    def test_it_appears_in_the_rules_panel(
        self, mail_portal, make_action, make_rule, rule_view
    ):
        rule = make_rule(make_action())

        with current_site(mail_portal):
            addable = rule_view(rule).addable_actions()

        assert ELEMENT_NAME in {entry["addview"] for entry in addable}, (
            "the action is not offered in the rule's 'add action' list: "
            f"{sorted(entry['addview'] for entry in addable)}"
        )

    def test_the_configured_action_is_listed_on_its_rule(
        self, mail_portal, make_action, make_rule, rule_view
    ):
        """The other half of the panel: a *configured* action has to render its
        own summary. ``ManageElements`` looks the element up by name to do it, so
        this fails outright if the element and the stored ``element`` attribute
        ever disagree."""
        rule = make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        with current_site(mail_portal):
            listed = rule_view(rule).actions()

        assert len(listed) == 1
        summary = support.translated(listed[0]["summary"], "en")
        assert TEMPLATE in summary, summary
        assert support.PLAIN_ADDRESS in summary, summary

    @pytest.mark.parametrize("language", ["en", "fr", "nl", "de"])
    def test_the_summary_says_which_recipient_sources_are_configured(
        self, make_action, language
    ):
        """Three configurations, three whole sentences, all four languages. A
        summary that under-reported the owner would let a manager believe the
        content's owner is not mailed when they are, which is the one thing this
        line exists to prevent."""
        addresses = support.translated(
            make_action(recipients=[support.PLAIN_ADDRESS]).summary, language
        )
        owner_only = support.translated(
            make_action(send_to_owner=True).summary, language
        )
        both = support.translated(
            make_action(recipients=[support.PLAIN_ADDRESS], send_to_owner=True).summary,
            language,
        )

        assert TEMPLATE in addresses and support.PLAIN_ADDRESS in addresses
        assert TEMPLATE in owner_only and support.PLAIN_ADDRESS not in owner_only
        assert TEMPLATE in both and support.PLAIN_ADDRESS in both
        assert len({addresses, owner_only, both}) == 3, (
            f"the three summaries are not distinct in {language!r}: "
            f"{sorted({addresses, owner_only, both})}"
        )
        assert "${" not in both, (
            f"an unsubstituted placeholder survived into the {language!r} "
            f"summary: {both!r}"
        )

    def test_the_add_and_edit_views_are_registered(
        self, mail_portal, mail_request, make_action, make_rule
    ):
        """Registered *globally*, unlike the element: a rule stored on a site
        that later opted out of ``:default`` still has to be editable and
        deletable."""
        make_rule(make_action())
        rule = mail_portal.restrictedTraverse(f"++rule++{RULE_ID}")

        adding = getMultiAdapter((rule, mail_request), name="+action")
        addview = getMultiAdapter((adding, mail_request), name=ELEMENT_NAME)
        editview = getMultiAdapter((rule.actions[0], mail_request), name=EDIT_VIEW_NAME)

        assert isinstance(addview, StyledMailAddFormView)
        assert isinstance(editview, StyledMailEditFormView)


# ---------------------------------------------------------------------------
# Gate 2 -- the vocabulary lists every discovered template
# ---------------------------------------------------------------------------


class TestTheVocabularyComesFromDiscovery:
    @pytest.fixture
    def vocabulary(self, mail_portal):
        """The named utility, looked up the way ``schema.Choice`` looks it up."""

        def build():
            factory = getUtility(IVocabularyFactory, name=TEMPLATES_VOCABULARY)
            return factory(mail_portal)

        return build

    def test_it_is_registered_under_the_name_the_schema_uses(self, vocabulary):
        assert IStyledMailAction["template"].vocabularyName == TEMPLATES_VOCABULARY
        assert vocabulary() is not None

    def test_it_lists_exactly_what_discovery_lists(self, vocabulary):
        from imio.emailkit.discovery import available_templates

        assert [term.value for term in vocabulary()] == available_templates()

    def test_the_token_and_the_title_are_the_namespaced_name(self, vocabulary):
        term = vocabulary().getTermByToken(TEMPLATE)

        assert term.value == TEMPLATE
        assert term.title == TEMPLATE

    def test_a_template_from_another_addon_appears_without_touching_this_package(
        self, vocabulary
    ):
        """§8.3's point, and the reason the vocabulary reads discovery rather than
        a list: two unrelated add-ons' templates have to show up in the form of a
        package that has never heard of them."""
        outside = set(vocabulary().by_token)
        assert not (set(dummyaddons.all_qualified_names()) & outside), (
            "the dummy add-ons are discoverable outside their fixture, so this "
            "test cannot tell 'appears because it is registered' from 'was "
            "already there'"
        )

        with dummyaddons.installed():
            inside = set(vocabulary().by_token)

        assert set(dummyaddons.all_qualified_names()) <= inside, (
            f"templates registered by another add-on are missing from the "
            f"vocabulary: {sorted(set(dummyaddons.all_qualified_names()) - inside)}"
        )

    def test_it_is_not_cached_behind_discovery(self, vocabulary):
        """A second cache here would survive ``discovery.invalidate_cache()`` and
        make this the one place in the package that still believes in a template
        nobody registers any more."""
        with dummyaddons.installed():
            assert (
                dummyaddons.COMPLETE.qualified("convocation") in vocabulary().by_token
            )

        assert (
            dummyaddons.COMPLETE.qualified("convocation") not in vocabulary().by_token
        )


# ---------------------------------------------------------------------------
# Gate 3 -- adding the action through the form stores template + recipients
# ---------------------------------------------------------------------------


class TestTheAddAndEditForms:
    """Reached by **traversal**, not by ``getMultiAdapter``.

    Both forms are ``plone.z3cform`` wrappers, and a wrapper renders its form
    against its own ``context`` -- the ``+action`` adding view for the add form,
    the stored element for the edit form. Adapted by hand those are unwrapped, so
    ``absolute_url()`` and ``restrictedTraverse('portal_membership')`` inside the
    page chrome fail on the acquisition chain and the render blows up for a reason
    that has nothing to do with this action. ``portal.restrictedTraverse(...)`` is
    the path Plone's own UI takes and gives properly wrapped views.
    """

    @pytest.fixture
    def empty_rule(self, mail_portal, storage, as_manager):
        """A rule with no elements yet, i.e. what the add form is reached from."""
        storage[RULE_ID] = Rule()
        return mail_portal.restrictedTraverse(f"++rule++{RULE_ID}")

    @pytest.fixture
    def addview(self, mail_portal, empty_rule):
        return mail_portal.restrictedTraverse(
            f"++rule++{RULE_ID}/+action/{ELEMENT_NAME}"
        )

    @pytest.fixture
    def stored_action(self, mail_portal, storage, make_action, as_manager):
        rule = Rule()
        rule.actions.append(make_action(recipients=[support.PLAIN_ADDRESS]))
        storage[RULE_ID] = rule
        return mail_portal.restrictedTraverse(f"++rule++{RULE_ID}").actions[0]

    @pytest.fixture
    def editview(self, mail_portal, stored_action):
        return mail_portal.restrictedTraverse(
            f"++rule++{RULE_ID}/++action++0/{EDIT_VIEW_NAME}"
        )

    def test_the_add_form_renders_its_three_widgets(self, addview):
        """Rendered, not merely constructed. A ``Choice`` over a named vocabulary
        and a ``List`` of ``TextLine`` are both widgets that fail at *render*
        time -- an unregistered vocabulary name, a missing multi-widget template
        -- and a form that only ever has ``create()`` called on it in tests would
        ship broken."""
        addview.update()
        rendered = addview.contents

        for name in ("template", "recipients", "send_to_owner"):
            assert f"form.widgets.{name}" in rendered, (
                f"the {name} widget did not render:\n{rendered[:2000]}"
            )
        assert TEMPLATE in rendered, "the template vocabulary rendered no options"

    def test_saving_the_add_form_stores_the_template_and_the_recipients(
        self, addview, empty_rule
    ):
        form = addview.form_instance
        addview.update()

        content = form.create(
            data={
                "template": TEMPLATE,
                "recipients": [support.PLAIN_ADDRESS, support.OTHER_ADDRESS],
                "send_to_owner": True,
            }
        )
        form.add(content)

        stored = empty_rule.actions[0]
        assert isinstance(stored, StyledMailAction)
        assert stored.template == TEMPLATE
        assert list(stored.recipients) == [support.PLAIN_ADDRESS, support.OTHER_ADDRESS]
        assert stored.send_to_owner is True
        assert stored.element == ELEMENT_NAME

    def test_the_edit_form_shows_what_is_stored(self, editview):
        editview.update()
        rendered = editview.contents

        assert support.PLAIN_ADDRESS in rendered, rendered[:2000]
        assert f'value="{TEMPLATE}"' in rendered, rendered[:2000]

    def test_the_edit_form_changes_what_is_stored(self, editview, stored_action):
        editview.update()

        editview.form_instance.applyChanges({
            "template": TEMPLATE,
            "recipients": [support.OTHER_ADDRESS],
            "send_to_owner": True,
        })

        assert list(stored_action.recipients) == [support.OTHER_ADDRESS]
        assert stored_action.send_to_owner is True

    def test_an_empty_recipients_field_stores_the_missing_value(
        self, addview, empty_rule
    ):
        """``recipients`` is optional, so leaving it blank stores the field's
        ``missing_value`` -- ``None``, not ``[]``. Worth an assertion because the
        executor and the summary both have to survive it, and "mail the owner and
        nobody else" is a perfectly ordinary rule."""
        form = addview.form_instance
        addview.update()

        form.add(
            form.create(
                data={"template": TEMPLATE, "recipients": None, "send_to_owner": True}
            )
        )

        stored = empty_rule.actions[0]
        assert stored.recipients is None
        assert list(stored.recipients or ()) == []
        assert support.translated(stored.summary, "fr")

    def test_the_schema_has_no_body_and_no_subject_field(self):
        """§1 rules out TTW template markup editing and §4 puts the subject in
        the registration so it is translated per recipient language. Both would
        be tempting fields on this form, and both are the wrong answer."""
        names = set(IStyledMailAction.names())

        assert names == {"template", "recipients", "send_to_owner"}, sorted(names)


# ---------------------------------------------------------------------------
# Gate 4 -- firing the rule sends one mail per language group, through Email
# ---------------------------------------------------------------------------


class TestFiringTheRuleSends:
    def test_one_recipient_gets_one_mail(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        deliver()

        record = support.sole(mailhost.sent)
        assert support.envelope(record) == [support.PLAIN_ADDRESS]

    def test_nothing_is_sent_until_the_rule_fires(
        self, make_action, make_rule, mailhost, site_sender, deliver
    ):
        """The non-vacuity control for the whole class: assigning a rule must not
        mail anybody, or every count below would be meaningless."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        deliver()

        assert mailhost.sent == []

    def test_one_message_per_language_group(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        deliver,
        fr_member,
        nl_member,
    ):
        """§6.2's per-language sending, reached from a rule.

        The recipients are **userids**, which is why the action takes them: a
        bare address resolves with no language and lands in the site-default
        group, while a userid carries the member's own preference.
        """
        make_rule(
            make_action(
                recipients=[
                    support.FR_MEMBER["userid"],
                    support.NL_MEMBER["userid"],
                ]
            )
        )

        fire()
        deliver()

        assert len(mailhost.sent) == 2, (
            f"{len(mailhost.sent)} message(s) for two recipients in two "
            "languages; SPEC §6.2 emits one message per language group"
        )
        # Keyed by language rather than by position: several queued deliveries
        # are separate transaction data managers and the order `tpc_finish`
        # visits them in is not the order they were queued.
        by_language = {
            support.lang_of(record.message): support.envelope(record)
            for record in mailhost.sent
        }
        assert by_language == {
            "fr": [support.FR_MEMBER["email"]],
            "nl": [support.NL_MEMBER["email"]],
        }

    def test_the_subject_is_the_registration_msgid_per_language(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        deliver,
        fr_member,
        nl_member,
    ):
        """Proof that the mail went through §6.2 and not through some second
        assembly path: the subject is the *registration's* msgid (§4), translated
        per group. Nothing but the builder does that."""
        make_rule(
            make_action(
                recipients=[
                    support.FR_MEMBER["userid"],
                    support.NL_MEMBER["userid"],
                ]
            )
        )

        fire()
        deliver()

        subject = support.registration_subject()
        by_language = {
            support.lang_of(record.message): support.subject_of(record.message)
            for record in mailhost.sent
        }
        assert by_language == {
            "fr": support.translated(subject, "fr"),
            "nl": support.translated(subject, "nl"),
        }

    def test_the_message_has_the_shape_SPEC_6_2_builds(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        """``set_content(text)`` + ``add_alternative(html)``, i.e. plaintext then
        HTML inside a ``multipart/alternative``. The stock mail action sends a
        bare ``text/plain``, so this also distinguishes the two."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        deliver()

        message = support.sole(mailhost.sent).message
        text, html = support.bodies(message)

        assert [part.get_content_type() for part in support.body_parts(message)] == [
            "text/plain",
            "text/html",
        ]
        assert text and html

    def test_the_sender_is_the_site_sender(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        """§6.2: "``From`` defaults to the site's configured sender". The action
        offers no source field, so this is the only ``From`` it can have."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        deliver()

        record = support.sole(mailhost.sent)
        assert support.addresses(record.message, "From") == [
            support.SITE_SENDER_ADDRESS
        ]


class TestTheOwnerRecipientSource:
    """SPEC §8.3's second recipient source, and the only one that is computed."""

    def test_the_owner_receives_the_mail(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        deliver,
        make_member,
        mail_portal,
    ):
        make_member(mail_portal)

        make_rule(make_action(send_to_owner=True))
        fire()
        deliver()

        record = support.sole(mailhost.sent)
        assert support.envelope(record) == [support.MEMBER_EMAIL]

    def test_the_owner_is_resolved_as_a_member_and_not_as_an_address(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        deliver,
        make_member,
        mail_portal,
    ):
        """The reason the executor passes a **userid**: the member adapter then
        supplies the display name and the preferred language, which is what makes
        §6.2's per-language sending work from a rule at all."""
        make_member(mail_portal)

        make_rule(make_action(send_to_owner=True))
        fire()
        deliver()

        message = support.sole(mailhost.sent).message
        assert support.display_names(message, "To") == [support.MEMBER_FULLNAME]

    def test_the_owner_is_added_to_the_explicit_recipients(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        deliver,
        make_member,
        mail_portal,
        set_default_language,
    ):
        set_default_language("en")
        make_member(mail_portal)

        make_rule(make_action(recipients=[support.PLAIN_ADDRESS], send_to_owner=True))
        fire()
        deliver()

        addresses = sorted(
            address for record in mailhost.sent for address in support.envelope(record)
        )
        assert addresses == sorted([support.PLAIN_ADDRESS, support.MEMBER_EMAIL])

    def test_the_owner_is_not_mailed_when_the_box_is_unticked(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        deliver,
        make_member,
        mail_portal,
    ):
        make_member(mail_portal)

        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))
        fire()
        deliver()

        record = support.sole(mailhost.sent)
        assert support.envelope(record) == [support.PLAIN_ADDRESS]


# ---------------------------------------------------------------------------
# Gate 5 -- the styled template, with substituted values
# ---------------------------------------------------------------------------


class TestTheMailIsTheStyledTemplate:
    @pytest.fixture
    def sent_html(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver, fr_member
    ):
        make_rule(make_action(recipients=[support.FR_MEMBER["userid"]]))
        fire()
        deliver()
        return support.html_of(support.sole(mailhost.sent).message)

    def test_no_placeholder_survives_into_either_part(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        """The single most important assertion in this module. Under the zope.tal
        fallback engine ``${...}`` reaches the inbox verbatim and nothing raises,
        so "our marker is in the output" is a test that ships raw placeholders."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        deliver()

        support.assert_message_is_clean(support.sole(mailhost.sent).message)

    def test_the_title_of_the_triggering_object_is_substituted(self, sent_html):
        assert ITEM_TITLE in sent_html, sent_html[:2000]

    def test_the_description_of_the_triggering_object_is_substituted(self, sent_html):
        assert ITEM_DESCRIPTION in sent_html, sent_html[:2000]

    def test_the_link_points_at_the_triggering_object(self, sent_html, folder):
        expected = f"{folder.absolute_url()}/{ITEM_ID}"

        assert f'href="{expected}"' in sent_html, sent_html[:2000]

    def test_it_is_the_kit_template_and_not_a_bare_body(self, sent_html):
        """Styled means the compiled kit output: a real document with inlined
        styles, not the text somebody typed. Counted rather than pattern-matched
        on a class name, because §3 fixes the CSS at build time and the class
        names are not the contract."""
        assert sent_html.lstrip().lower().startswith("<!doctype html")
        assert support.count_inline_styles(sent_html) >= support.MIN_INLINE_STYLES

    def test_the_cta_label_is_translated_per_language_group(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        deliver,
        fr_member,
        nl_member,
    ):
        """The one context value the action supplies as a **msgid** rather than a
        string, and the reason it has to be one: ``.with_context()`` runs once,
        before §6.2 groups by language, so a value translated in the executor
        would reach a Dutch recipient in French.

        Non-vacuous because the two translations are asserted to differ first --
        otherwise both groups would "match" the untranslated default and the test
        would pass with the translation machinery switched off.
        """
        french = support.translated(CTA_LABEL, "fr")
        dutch = support.translated(CTA_LABEL, "nl")
        assert french != dutch, (
            f"the FR and NL catalogs give {CTA_LABEL} the same text ({french!r}), "
            "so this test cannot tell a translated label from an untranslated one"
        )

        make_rule(
            make_action(
                recipients=[
                    support.FR_MEMBER["userid"],
                    support.NL_MEMBER["userid"],
                ]
            )
        )
        fire()
        deliver()

        by_language = {
            support.lang_of(record.message): support.html_of(record.message)
            for record in mailhost.sent
        }
        assert french in by_language["fr"]
        assert dutch in by_language["nl"]
        assert french not in by_language["nl"]

    def test_the_plaintext_part_carries_the_same_values(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        """Half the message, and the half nobody looks at. §4 makes the
        hand-authored ``.txt.pt`` twin the primary plaintext path, and it reads
        the same names -- so a context key the HTML happens to tolerate shows up
        here."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        deliver()

        text, _html = support.bodies(support.sole(mailhost.sent).message)
        assert ITEM_TITLE in text
        assert ITEM_DESCRIPTION in text


# ---------------------------------------------------------------------------
# Gate 6 -- an unresolvable recipient raises, and nothing is sent
# ---------------------------------------------------------------------------


class TestAnUnresolvableRecipientRaises:
    def test_the_executor_raises_recipient_error(
        self, make_action, execute, item, mailhost, site_sender
    ):
        action = make_action(recipients=[support.UNRESOLVABLE])

        with pytest.raises(RecipientError):
            execute(action, item)

    def test_nothing_is_delivered(
        self, make_action, execute, item, mailhost, site_sender, deliver
    ):
        """ "Fail loud, not silent drop" is only half the guarantee; the other half
        is that the mail did not go out to the recipients that *did* resolve."""
        action = make_action(recipients=[support.PLAIN_ADDRESS, support.UNRESOLVABLE])

        with pytest.raises(RecipientError):
            execute(action, item)
        deliver()

        assert mailhost.sent == []

    def test_the_error_names_every_bad_value(
        self, make_action, execute, item, mailhost, site_sender
    ):
        action = make_action(
            recipients=[support.UNRESOLVABLE, support.OTHER_UNRESOLVABLE]
        )

        with pytest.raises(RecipientError) as caught:
            execute(action, item)

        assert len(caught.value.problems) == 2, caught.value.problems

    @pytest.mark.parametrize("recipients", [(), None], ids=["empty", "missing_value"])
    def test_no_recipients_at_all_raises_rather_than_doing_nothing(
        self, make_action, execute, item, mailhost, site_sender, recipients
    ):
        """A rule saved with an empty recipient list and the owner box unticked
        would otherwise be a rule that fires and mails nobody, forever, quietly.
        §6.2 already treats "no recipients" as a ``RecipientError``.

        Both shapes the field can store: ``[]`` from an emptied multi-widget and
        ``None``, the field's ``missing_value``, from one never filled in.
        """
        action = make_action()
        action.recipients = recipients

        with pytest.raises(RecipientError):
            execute(action, item)

    def test_an_unresolvable_owner_raises_rather_than_sending_to_the_rest(
        self, make_action, execute, item, mailhost, site_sender, deliver
    ):
        """The owner is the one recipient the *action* computes, so it is the one
        place a silent drop could be introduced here rather than inherited from
        §6.2. The test user has no email address unless a fixture gives them
        one."""
        action = make_action(recipients=[support.PLAIN_ADDRESS], send_to_owner=True)

        with pytest.raises(RecipientError):
            execute(action, item)
        deliver()

        assert mailhost.sent == []

    def test_the_failure_reaches_the_operation_that_triggered_the_rule(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        """Dispatched for real, not called directly. ``plone.contentrules``
        catches nothing, so a broken rule has to surface on the very operation
        that fired it -- which is what makes it noticeable at all."""
        make_rule(make_action(recipients=[support.UNRESOLVABLE]))

        with pytest.raises(RecipientError):
            fire()
        deliver()

        assert mailhost.sent == []

    def test_the_executor_never_returns_false(
        self,
        make_action,
        execute,
        item,
        mailhost,
        site_sender,
        make_member,
        mail_portal,
    ):
        """``plone.contentrules`` stops a rule when an element returns ``False``,
        which makes ``False`` the quiet way to fail. A problem is an exception
        here; a success is ``True``."""
        make_member(mail_portal)

        assert execute(make_action(send_to_owner=True), item) is True


# ---------------------------------------------------------------------------
# Gate 7 -- a stale template name fails loudly
# ---------------------------------------------------------------------------


class TestAStaleTemplateNameFailsLoudly:
    def test_the_executor_raises_template_not_found(
        self, make_action, execute, item, mailhost, site_sender
    ):
        """The realistic case: the add-on that shipped the template was
        uninstalled and the rule still names it. Skipping would leave a rule
        that looks configured and mails nobody."""
        action = make_action(
            template=STALE_TEMPLATE, recipients=[support.PLAIN_ADDRESS]
        )

        with pytest.raises(TemplateNotFound) as caught:
            execute(action, item)

        assert caught.value.name == STALE_TEMPLATE
        assert TEMPLATE in caught.value.available, (
            "TemplateNotFound must carry the available names (SPEC §4); that "
            "list is what tells a manager whether they have a typo or a missing "
            "add-on"
        )

    def test_nothing_is_delivered(
        self, make_action, execute, item, mailhost, site_sender, deliver
    ):
        action = make_action(
            template=STALE_TEMPLATE, recipients=[support.PLAIN_ADDRESS]
        )

        with pytest.raises(TemplateNotFound):
            execute(action, item)
        deliver()

        assert mailhost.sent == []

    def test_a_template_that_disappears_after_the_rule_was_saved(
        self, make_action, execute, item, mailhost, site_sender, deliver
    ):
        """The same failure, arrived at the way it happens in production: the rule
        names a template that *was* registered when it was saved."""
        with dummyaddons.installed():
            name = dummyaddons.COMPLETE.qualified("convocation")
            action = make_action(template=name, recipients=[support.PLAIN_ADDRESS])

        with pytest.raises(TemplateNotFound):
            execute(action, item)
        deliver()

        assert mailhost.sent == []

    def test_the_failure_reaches_the_operation_that_triggered_the_rule(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        make_rule(
            make_action(template=STALE_TEMPLATE, recipients=[support.PLAIN_ADDRESS])
        )

        with pytest.raises(TemplateNotFound):
            fire()
        deliver()

        assert mailhost.sent == []


# ---------------------------------------------------------------------------
# Gate 8 -- the stock mail action is left untouched
# ---------------------------------------------------------------------------


class TestTheStockMailActionIsUntouched:
    """§8.3, verbatim: "The stock mail action is left untouched"."""

    def test_it_is_still_registered_globally(self, mail_portal):
        # ``mail_portal`` is not used, but it is what sets the layer up: without
        # a layer fixture the ZCML has not been loaded for this test and the
        # global registry is the bare, cleaned-up one, so the assertion below
        # would fail for a reason that has nothing to do with §8.3.
        element = getGlobalSiteManager().queryUtility(
            IRuleAction, name="plone.actions.Mail"
        )

        assert element is not None, "the stock mail action was unregistered"
        assert element.factory is MailAction, (
            "the stock mail action's factory was replaced"
        )
        assert element.addview == "plone.actions.Mail"
        assert element.editview == "edit"

    def test_nothing_shadows_it_on_the_site(self, mail_portal):
        local = getSiteManager(mail_portal).queryUtility(
            IRuleAction, name="plone.actions.Mail"
        )
        globally = getGlobalSiteManager().queryUtility(
            IRuleAction, name="plone.actions.Mail"
        )

        assert local is globally, (
            "a local registration shadows the stock mail action, so this site's "
            "'Send email' is no longer Plone's"
        )

    def test_both_actions_are_offered_side_by_side(self, mail_portal):
        with current_site(mail_portal):
            offered = {
                element.addview for element in allAvailableActions(IObjectAddedEvent)
            }

        assert {"plone.actions.Mail", ELEMENT_NAME} <= offered, sorted(offered)

    def test_it_still_sends(self, folder, item, mailhost, site_sender):
        """Executed for real. §8.3 says untouched, and "the utility is still
        registered" is not the same claim as "it still puts mail on the wire" --
        this package installs a MailHost double and a browser layer, either of
        which could have broken it."""
        action = MailAction()
        action.subject = "Rapport"
        action.source = support.OVERRIDE_SENDER
        action.recipients = support.PLAIN_ADDRESS
        action.message = "Le document a été publié."

        result = getMultiAdapter((folder, action, Triggered(item)), IExecutable)()

        assert result is True
        record = support.sole(mailhost.sent)
        assert support.envelope(record) == [support.PLAIN_ADDRESS]
        assert record.message.get_content_type() == "text/plain", (
            "the stock action's message shape changed, which would mean "
            "something in this package reached into it"
        )

    def test_the_two_actions_are_different_element_names(self):
        assert ELEMENT_NAME != "plone.actions.Mail"
        assert StyledMailAction.element == ELEMENT_NAME
        assert MailAction.element == "plone.actions.Mail"


# ---------------------------------------------------------------------------
# Gate 9 -- transaction abort sends nothing
# ---------------------------------------------------------------------------


class TestTransactionAbortSendsNothing:
    """§6.2's guarantee, checked *through* the executor.

    The builder's own abort test (``tests/test_send_transaction.py``) proves the
    guarantee for a direct caller. It would still be possible for a rule action
    to lose it -- by passing ``immediate=True``, say, to "make sure the mail goes
    out" -- and the failure mode is a mail sent for an operation that was rolled
    back. So the whole triangle is asserted again here: pending, cancelled,
    delivered.
    """

    def test_nothing_is_delivered_before_the_transaction_ends(
        self, make_action, make_rule, fire, mailhost, site_sender
    ):
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()

        assert mailhost.sent == [], (
            "the rule action delivered before the transaction ended, so it is "
            "not using SPEC §6.2's queued send"
        )

    def test_abort_leaves_nothing_delivered(
        self, make_action, make_rule, fire, mailhost, site_sender
    ):
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        transaction.abort()

        assert mailhost.sent == []

    def test_a_delivery_really_was_joined_to_the_transaction(
        self, make_action, make_rule, fire, mailhost, site_sender
    ):
        """The positive half: an empty inbox proves nothing on its own, because a
        rule that never queued anything also has an empty inbox."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        transaction.abort()

        assert mailhost.aborted == 1, (
            "no queued delivery was cancelled by the abort, so none was ever "
            "joined to the transaction: the action dropped the message"
        )

    def test_abort_cancels_every_language_group(
        self,
        make_action,
        make_rule,
        fire,
        mailhost,
        site_sender,
        fr_member,
        nl_member,
    ):
        make_rule(
            make_action(
                recipients=[
                    support.FR_MEMBER["userid"],
                    support.NL_MEMBER["userid"],
                ]
            )
        )

        fire()
        transaction.abort()

        assert mailhost.sent == []
        assert mailhost.aborted == 2


# ---------------------------------------------------------------------------
# The executor stays a caller of SPEC §6.2
# ---------------------------------------------------------------------------


class TestTheExecutorOnlyDelegates:
    def test_it_adds_no_builder_method(self):
        """§6.2 is frozen and ``docs/plans/phase-5.md`` §3 lists "no new builder
        methods" as a non-goal. ``tests/test_builder.py`` keeps the set closed;
        this asserts that importing the content-rule module did not widen it."""
        public = {
            name
            for name in dir(Email)
            if not name.startswith("_") and callable(getattr(Email, name))
        }

        assert public == set(support.BUILDER_METHODS), sorted(public)

    def test_it_does_not_send_immediately(
        self, make_action, execute, item, mailhost, site_sender, deliver
    ):
        """``.send()`` with no argument, i.e. §6.2's default. Restated as an
        assertion because ``immediate=True`` is exactly the shortcut somebody
        reaches for when a rule "does not seem to send"."""
        action = make_action(recipients=[support.PLAIN_ADDRESS])

        execute(action, item)

        assert mailhost.sent == [], ".send(immediate=True) leaked into the executor"

        deliver()
        assert len(mailhost.sent) == 1

    def test_the_executor_is_adapted_from_context_element_event(
        self, folder, item, make_action
    ):
        executor = getMultiAdapter(
            (folder, make_action(), Triggered(item)), IExecutable
        )

        assert isinstance(executor, StyledMailActionExecutor)

    def test_the_render_context_is_the_documented_set(self, item):
        """§8.3 says nothing about what a rule-triggered mail renders against, so
        the action fixes a small set and documents it. Pinned here because
        widening it silently is how a documented contract stops being one, and
        because a template author has nothing else to write against."""
        assert set(render_context(item)) == set(RENDER_CONTEXT_NAMES)
        assert render_context(item)["title"] == ITEM_TITLE
        assert render_context(item)["intro"] == ITEM_DESCRIPTION
        assert render_context(item)["cta_url"] == item.absolute_url()
        assert render_context(item)["item"] is item


class TestTheExecutorLogsEnoughToDiagnose:
    """A rule that fails has to leave a log line naming what it was trying to do.

    The exception reaches the browser of whoever triggered the operation, but the
    person who has to fix a nightly workflow reads a log file -- and "RecipientError"
    on its own says nothing about which rule, which template or which recipients.
    """

    def test_a_successful_send_is_logged_with_template_and_recipients(
        self, make_action, execute, item, mailhost, site_sender, caplog
    ):
        with caplog.at_level(logging.INFO, logger="imio.emailkit.contentrules"):
            execute(make_action(recipients=[support.PLAIN_ADDRESS]), item)

        message = "\n".join(record.getMessage() for record in caplog.records)
        assert TEMPLATE in message, message
        assert support.PLAIN_ADDRESS in message, message
        assert ITEM_ID in message, message

    def test_a_failure_is_logged_before_it_is_re_raised(
        self, make_action, execute, item, mailhost, site_sender, caplog
    ):
        action = make_action(
            template=STALE_TEMPLATE, recipients=[support.PLAIN_ADDRESS]
        )

        with (
            caplog.at_level(logging.ERROR, logger="imio.emailkit.contentrules"),
            pytest.raises(TemplateNotFound),
        ):
            execute(action, item)

        errors = [
            record for record in caplog.records if record.levelno >= logging.ERROR
        ]
        assert errors, "the failure was re-raised with no log line at all"
        message = "\n".join(record.getMessage() for record in errors)
        assert STALE_TEMPLATE in message, message
        assert support.PLAIN_ADDRESS in message, message
        assert ITEM_ID in message, message
        assert errors[0].exc_info is not None, (
            "the log line carries no traceback, so the log says a rule failed "
            "without saying how"
        )


# ---------------------------------------------------------------------------
# SPEC §8.2 level 3 -- a ``:base`` site keeps the action type, deliberately
# ---------------------------------------------------------------------------
#
# Its own class, at the end of the module. `zope.pytestlayer` keeps a layer up for
# the whole *class* and tears it down at the class boundary, and `plone.testing`
# stacks every layer's DemoStorage onto ONE shared stack -- so a layer set up while
# another is still up sees the other's database writes. Mixing `base_portal` and
# `mail_portal` in one class therefore reads a `:base` site with `:default` already
# applied to it (measured, not theorised), and the profile-version control below
# would silently be checking the wrong site. `tests/test_optout.py` gets the same
# isolation by being its own module.


class TestABaseOnlySiteStillHasTheActionType:
    """The registration is plain global ZCML, so ``:base`` has it too.

    This is the intended behaviour and not a leak. §8.2 level 3's opt-out is about
    Plone's **stock transactional mails**: ``:base`` ships "the runtime (API,
    discovery, kit) without the Plone-default overrides". An action type is not an
    override of anything -- it is inert until a Manager creates a rule that uses
    it, and the templates it can send come from §4 discovery either way. Gating it
    would mean a per-site local utility whose stored copy drifts from the ZCML with
    no symptom, which is the silent-failure class this project exists to avoid.
    """

    def test_the_base_profile_is_what_this_site_has(self, base_portal):
        """The control for the whole class: without it, every assertion below
        could be true because the fixture handed back the ``:default`` site."""
        setup_tool = base_portal.portal_setup

        assert setup_tool.getLastVersionForProfile("imio.emailkit:base") not in (
            None,
            "unknown",
        )
        assert setup_tool.getLastVersionForProfile("imio.emailkit:default") in (
            None,
            "unknown",
        ), (
            "imio.emailkit:default leaked into the :base site, so this class is "
            "testing the wrong thing (see the comment above)"
        )

    def test_the_browser_layer_is_still_absent(self, base_portal, layers_of):
        """What ``:base`` *does* opt out of, restated here so the next assertion
        cannot be mistaken for "the opt-out is broken"."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer not in layers_of(base_portal)

    def test_the_action_type_is_available(self, base_portal):
        assert (
            getSiteManager(base_portal).queryUtility(IRuleAction, name=ELEMENT_NAME)
            is not None
        ), (
            "SPEC §8.3's action type is missing on a :base site; it is registered "
            "in ZCML, so it should be there whichever profile was applied"
        )

    def test_the_stock_mail_action_is_still_there(self, base_portal):
        assert (
            getSiteManager(base_portal).queryUtility(
                IRuleAction, name="plone.actions.Mail"
            )
            is not None
        )

    def test_the_vocabulary_still_works(self, base_portal):
        """A ``:base`` site still renders its own templates, so the form's template
        list has to resolve there too."""
        factory = getUtility(IVocabularyFactory, name=TEMPLATES_VOCABULARY)

        assert TEMPLATE in factory(base_portal).by_token
