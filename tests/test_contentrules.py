"""The "Send styled email" content-rule action.

Adds a content-rule action type: its edit form offers registered template
names and recipient sources, and its executor sends through ``Email(...)``.
The stock mail action stays unchanged. Assertions check substituted values,
not marker strings, since an unresolved ``${...}`` would still pass a
marker check under the zope.tal fallback engine.
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

#: The one template this package registers, which is what a rule points at.
TEMPLATE = support.qualified(support.NOTIFICATION)

#: A name nothing is registered under; must raise, not skip silently.
STALE_TEMPLATE = "imio.emailkit:template_that_was_removed"

RULE_ID = "styled-mail-rule"
FOLDER_ID = "dossiers"

#: Accented, so a charset bug becomes visible.
ITEM_ID = "urb-2026-0417"
ITEM_TITLE = "Permis d'urbanisme URB-2026-0417"
ITEM_DESCRIPTION = "L'enquête publique est clôturée; le dossier passe au collège."


@implementer(IObjectEvent)
class Triggered:
    """The minimal object event a rule executor reads."""

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
    """Created before any rule exists, so its own add event cannot trigger
    the rule under test."""
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
    """-> a rule holding ``action``, assigned to ``folder``, traversed
    through ``++rule++`` since storage itself is not traversable."""

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
    """The triggering object, with no rule assigned: for tests that call
    the executor directly."""
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
    """``rule_view(rule)`` -> the ``@@manage-elements`` view of a rule."""

    def make(rule):
        return ManageElements(rule, mail_request)

    return make


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

    def test_it_is_titled_send_styled_email(self, mail_portal):
        """The title is the exact text a Manager sees in the panel list.
        It is fixed, not a free label."""
        element = getUtility(IRuleAction, name=ELEMENT_NAME)

        assert element.title == "Send styled email"
        assert element.description

    def test_it_is_registered_in_zcml_like_every_other_plone_action(self, mail_portal):
        """Checked in both the global and the site registry, since a
        per-site copy could drift from ZCML unnoticed."""
        globally = getGlobalSiteManager().queryUtility(IRuleAction, name=ELEMENT_NAME)
        locally = getSiteManager(mail_portal).queryUtility(
            IRuleAction, name=ELEMENT_NAME
        )

        assert globally is not None, (
            f"no global IRuleAction utility named {ELEMENT_NAME!r}; the "
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
        """Matched on ``addview``: ``allAvailableActions`` returns plain
        instances that carry no name."""
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
        """``ManageElements`` looks up the element by name, so this fails
        if the stored ``element`` attribute disagrees."""
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
        """The summary must always say when the owner is mailed."""
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
        """Registered globally, so a rule stays editable even on a site
        that opts out of ``:default``."""
        make_rule(make_action())
        rule = mail_portal.restrictedTraverse(f"++rule++{RULE_ID}")

        adding = getMultiAdapter((rule, mail_request), name="+action")
        addview = getMultiAdapter((adding, mail_request), name=ELEMENT_NAME)
        editview = getMultiAdapter((rule.actions[0], mail_request), name=EDIT_VIEW_NAME)

        assert isinstance(addview, StyledMailAddFormView)
        assert isinstance(editview, StyledMailEditFormView)


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
        """The vocabulary reads discovery, not a fixed list, so a template
        from another add-on appears here too."""
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
        """The vocabulary must not cache. A cache could keep listing a
        template after its add-on is uninstalled."""
        with dummyaddons.installed():
            assert (
                dummyaddons.COMPLETE.qualified("convocation") in vocabulary().by_token
            )

        assert (
            dummyaddons.COMPLETE.qualified("convocation") not in vocabulary().by_token
        )


class TestTheAddAndEditForms:
    """Reached by traversal, not ``getMultiAdapter``: these ``plone.z3cform``
    wrappers need the acquisition-wrapped context only traversal gives."""

    @pytest.fixture
    def empty_rule(self, mail_portal, storage, as_manager):
        """A rule with no elements yet, what the add form is reached from."""
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
        """Rendered, not just constructed: a ``Choice`` or ``List`` widget
        can fail only at render time."""
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
        """Leaving ``recipients`` blank stores ``None``, not ``[]``."""
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
        """The subject comes from the template registration instead."""
        names = set(IStyledMailAction.names())

        assert names == {"template", "recipients", "send_to_owner"}, sorted(names)


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
        """Assigning a rule must not send mail by itself."""
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
        """Recipients are userids, not bare addresses, so each carries a
        preferred language for grouping."""
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
            "languages; the builder emits one message per language group"
        )
        # Keyed by language, not position: queued deliveries are separate
        # transaction data managers, and tpc_finish does not visit them in
        # queue order.
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
        """The subject is the registered msgid, translated per language."""
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

    def test_the_message_has_the_shape_the_builder_builds(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        """The builder's ``multipart/alternative`` shape, unlike the stock
        action's plain ``text/plain``."""
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
        """No source field: ``From`` is always the site's configured
        sender."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        deliver()

        record = support.sole(mailhost.sent)
        assert support.addresses(record.message, "From") == [
            support.SITE_SENDER_ADDRESS
        ]


class TestTheOwnerRecipientSource:
    """The only recipient source that is computed, not stored."""

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
        """A userid, not an address, so the member adapter can supply the
        display name and preferred language."""
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
        """Under the zope.tal fallback engine, ``${...}`` reaches the inbox
        unresolved and nothing raises."""
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
        """Counted by inline styles, not a CSS class name, since class
        names can change."""
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
        """The label is a msgid, not translated text, since
        ``.with_context()`` runs before recipients are grouped by language.
        Checks first that FR and NL differ, so this cannot pass untranslated.
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
        """The plaintext ``.txt.pt`` twin uses the same context values."""
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()
        deliver()

        text, _html = support.bodies(support.sole(mailhost.sent).message)
        assert ITEM_TITLE in text
        assert ITEM_DESCRIPTION in text


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
        """No mail goes to recipients that did resolve, when another fails."""
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
        """Must raise, not fire silently. Checks both stored shapes: ``[]``
        and ``None``."""
        action = make_action()
        action.recipients = recipients

        with pytest.raises(RecipientError):
            execute(action, item)

    def test_an_unresolvable_owner_raises_rather_than_sending_to_the_rest(
        self, make_action, execute, item, mailhost, site_sender, deliver
    ):
        """The owner is computed by the action itself, not the builder."""
        action = make_action(recipients=[support.PLAIN_ADDRESS], send_to_owner=True)

        with pytest.raises(RecipientError):
            execute(action, item)
        deliver()

        assert mailhost.sent == []

    def test_the_failure_reaches_the_operation_that_triggered_the_rule(
        self, make_action, make_rule, fire, mailhost, site_sender, deliver
    ):
        """Dispatched through the real rule: ``plone.contentrules`` catches
        nothing, so the error reaches the caller."""
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
        """A ``False`` return silently stops a rule, so this executor must
        raise on failure and always return ``True`` on success."""
        make_member(mail_portal)

        assert execute(make_action(send_to_owner=True), item) is True


class TestAStaleTemplateNameFailsLoudly:
    def test_the_executor_raises_template_not_found(
        self, make_action, execute, item, mailhost, site_sender
    ):
        """The template's add-on was uninstalled; this must raise, not
        skip silently."""
        action = make_action(
            template=STALE_TEMPLATE, recipients=[support.PLAIN_ADDRESS]
        )

        with pytest.raises(TemplateNotFound) as caught:
            execute(action, item)

        assert caught.value.name == STALE_TEMPLATE
        assert TEMPLATE in caught.value.available, (
            "TemplateNotFound must carry the available names; that "
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
        """Registered when the rule was saved, but not registered now."""
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


class TestTheStockMailActionIsUntouched:
    def test_it_is_still_registered_globally(self, mail_portal):
        # mail_portal loads the ZCML layer; without it the registry is empty.
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
        """Executed for real: the stock action must still send mail."""
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


class TestTransactionAbortSendsNothing:
    """Nothing is sent before commit; an abort cancels everything queued."""

    def test_nothing_is_delivered_before_the_transaction_ends(
        self, make_action, make_rule, fire, mailhost, site_sender
    ):
        make_rule(make_action(recipients=[support.PLAIN_ADDRESS]))

        fire()

        assert mailhost.sent == [], (
            "the rule action delivered before the transaction ended, so it is "
            "not using the builder's queued send"
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
        """An empty inbox alone proves nothing; checks the abort really
        cancelled a queued delivery."""
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


class TestTheExecutorOnlyDelegates:
    def test_it_adds_no_builder_method(self):
        """Importing the content-rule module adds no public method to
        ``Email``."""
        public = {
            name
            for name in dir(Email)
            if not name.startswith("_") and callable(getattr(Email, name))
        }

        assert public == set(support.BUILDER_METHODS), sorted(public)

    def test_it_does_not_send_immediately(
        self, make_action, execute, item, mailhost, site_sender, deliver
    ):
        """The executor uses the builder's default queued send, not
        ``immediate=True``."""
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
        """A template author writes against this fixed set of context
        names, so it must not change silently."""
        assert set(render_context(item)) == set(RENDER_CONTEXT_NAMES)
        assert render_context(item)["title"] == ITEM_TITLE
        assert render_context(item)["intro"] == ITEM_DESCRIPTION
        assert render_context(item)["cta_url"] == item.absolute_url()
        assert render_context(item)["item"] is item


class TestTheExecutorLogsEnoughToDiagnose:
    """A failed rule must log its template and recipients: the exception
    message alone is not enough to diagnose it."""

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


# This class stays separate: mixing `base_portal` and `mail_portal` in one
# class would stack a `:default` site on top of a `:base` one.


class TestABaseOnlySiteStillHasTheActionType:
    """A ``:base`` site keeps the action type too: it is plain global ZCML,
    and the ``:base`` profile only opts out of Plone's mail overrides."""

    def test_the_base_profile_is_what_this_site_has(self, base_portal):
        """Checks the fixture gave a ``:base`` site, not a ``:default`` one."""
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
        """Confirms what ``:base`` does opt out of."""
        from imio.emailkit.interfaces import IEmailkitLayer

        assert IEmailkitLayer not in layers_of(base_portal)

    def test_the_action_type_is_available(self, base_portal):
        assert (
            getSiteManager(base_portal).queryUtility(IRuleAction, name=ELEMENT_NAME)
            is not None
        ), (
            "the action type is missing on a :base site; it is registered "
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
        """A ``:base`` site still renders templates, so the vocabulary
        must resolve there too."""
        factory = getUtility(IVocabularyFactory, name=TEMPLATES_VOCABULARY)

        assert TEMPLATE in factory(base_portal).by_token
