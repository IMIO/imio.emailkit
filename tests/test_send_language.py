"""Per-language sending, the headline feature of the builder.

``.send()`` groups recipients by resolved language, renders once per
language group, and emits one message per group.

Three things must hold: the count (one message per language), the
partition (every recipient in their own language's group), and the
content (that group's translated subject and rendered body).

Body assertions compare against ``render(..., language=...)`` rather
than a marker. A builder that renders once and reuses the result would
still pass count- and header-based checks alone.
"""

import pytest
import support


Email = support.require_builder()


@pytest.fixture
def by_language(deliver, sent):
    """``by_language(email)`` returns ``{lang: SentMail}`` after a real commit.

    Keyed off the ``lang`` attribute the kit layout emits on ``<html>``,
    since that comes from the rendered body, not the builder's own
    bookkeeping.
    """

    def send_and_group(email):
        email.send()
        deliver()
        grouped = {}
        for record in sent:
            language = support.lang_of(record.message)
            assert language not in grouped, (
                f"two messages rendered in {language!r}: the builder emits one message "
                "per language group"
            )
            grouped[language] = record
        return grouped

    return send_and_group


class TestTwoLanguagesTwoMessages:
    def test_fr_plus_nl_yields_exactly_two_messages(
        self, mail, fr_member, nl_member, deliver, sent
    ):
        email = mail().to(fr_member).to(nl_member)

        email.send()
        deliver()

        assert len(sent) == 2, (
            f"one FR and one NL recipient produced {len(sent)} message(s). "
            "The builder emits one message per language group."
        )

    def test_each_message_goes_only_to_its_own_group(
        self, mail, fr_member, nl_member, by_language
    ):
        """Each recipient must land only in their own language group, not in
        another recipient's message."""
        grouped = by_language(mail().to(fr_member).to(nl_member))

        assert set(grouped) == {"fr", "nl"}, f"language groups: {sorted(grouped)}"
        assert support.envelope(grouped["fr"]) == [support.FR_MEMBER["email"]]
        assert support.envelope(grouped["nl"]) == [support.NL_MEMBER["email"]]

    def test_each_message_carries_its_own_subject_translation(
        self, mail, fr_member, nl_member, by_language
    ):
        """The subject msgid is translated accordingly."""
        msgid = support.registration_subject()
        grouped = by_language(mail().to(fr_member).to(nl_member))

        assert support.subject_of(grouped["fr"].message) == support.translated(
            msgid, "fr"
        )
        assert support.subject_of(grouped["nl"].message) == support.translated(
            msgid, "nl"
        )

    def test_the_two_subjects_actually_differ(
        self, mail, fr_member, nl_member, by_language
    ):
        """Guards the test above: the two catalog entries genuinely differ,
        so equal subjects mean no translation happened."""
        grouped = by_language(mail().to(fr_member).to(nl_member))

        assert support.subject_of(grouped["fr"].message) != support.subject_of(
            grouped["nl"].message
        ), "both language groups got the same subject: nothing was translated"

    def test_each_message_carries_its_own_rendered_body(
        self, mail, fr_member, nl_member, by_language, notification_context
    ):
        """Each group's body must equal ``render()``'s output for that
        language, byte for byte, not just contain a word of it."""
        from imio.emailkit import render

        grouped = by_language(mail().to(fr_member).to(nl_member))

        for language in ("fr", "nl"):
            html, text = render(
                support.qualified(support.NOTIFICATION),
                context=dict(notification_context),
                language=language,
            )
            sent_text, sent_html = support.bodies(grouped[language].message)

            assert sent_html.strip() == html.strip(), (
                f"the {language} html part is not render(..., language={language!r})"
            )
            assert sent_text.strip() == text.strip(), (
                f"the {language} text part is not render(..., language={language!r})"
            )

    def test_the_two_bodies_differ(self, mail, fr_member, nl_member, by_language):
        """The two groups' bodies must differ, whatever the subjects say."""
        grouped = by_language(mail().to(fr_member).to(nl_member))

        assert support.html_of(grouped["fr"].message) != support.html_of(
            grouped["nl"].message
        ), "both language groups got the same body: render() ran once, not per group"

    def test_neither_body_has_an_unresolved_placeholder(
        self, mail, fr_member, nl_member, by_language
    ):
        grouped = by_language(mail().to(fr_member).to(nl_member))

        for record in grouped.values():
            support.assert_message_is_clean(record.message)


class TestGroupingIsByLanguageNotByRecipient:
    def test_two_recipients_of_one_language_share_one_message(
        self, mail, fr_member, make_recipient_member, deliver, sent
    ):
        """One message per language group, not one per person."""
        second = make_recipient_member(
            dict(
                support.FR_MEMBER,
                userid="fr_member_2",
                email="fr.deux@commune.example.be",
                fullname="Fabienne Namuroise",
            )
        )

        email = mail().to(fr_member).to(second)
        email.send()
        deliver()

        record = support.sole(sent, "message for two FR recipients")

        assert support.envelope(record) == sorted([
            support.FR_MEMBER["email"],
            "fr.deux@commune.example.be",
        ])

    def test_cc_and_bcc_are_grouped_too(self, mail, fr_member, nl_member, by_language):
        """A Cc recipient is grouped by language too, not left out or
        duplicated across every group's message."""
        grouped = by_language(mail().to(fr_member).cc(nl_member))

        assert set(grouped) == {"fr", "nl"}, (
            "a Cc recipient with another language did not get their own group: "
            f"{sorted(grouped)}"
        )
        nl_addresses = support.envelope(grouped["nl"])
        assert nl_addresses == [support.NL_MEMBER["email"]]


class TestTheFallbackLanguage:
    """A recipient with no language falls back to the site default."""

    def test_a_plain_address_renders_in_the_site_default(
        self, mail, set_default_language, by_language
    ):
        """A bare address has no member, so ``IEmailRecipient.language`` is
        ``None``."""
        set_default_language("nl")

        grouped = by_language(mail().to(support.PLAIN_ADDRESS))

        assert set(grouped) == {"nl"}, (
            "a recipient with no language did not fall back to the site default "
            f"(nl): {sorted(grouped)}"
        )

    def test_the_fallback_follows_the_site(
        self, mail, set_default_language, by_language
    ):
        """The fallback must follow the site default, not a hardcoded
        language."""
        set_default_language("de")

        grouped = by_language(mail().to(support.PLAIN_ADDRESS))

        assert set(grouped) == {"de"}, sorted(grouped)

    def test_a_member_with_no_language_falls_back_too(
        self,
        mail,
        make_recipient_member,
        mail_portal,
        set_default_language,
        by_language,
    ):
        """Most Plone members never set a preferred language, so this is
        common, not an edge case."""
        set_default_language("nl")
        make_recipient_member(dict(support.FR_MEMBER, userid="no_lang"))
        mail_portal.portal_membership.getMemberById("no_lang").setMemberProperties({
            "language": ""
        })

        grouped = by_language(mail().to("no_lang"))

        assert set(grouped) == {"nl"}, sorted(grouped)

    def test_an_address_and_a_member_of_the_default_language_share_a_group(
        self, mail, set_default_language, fr_member, deliver, sent
    ):
        """A recipient whose language is the site default must share a group
        with one who asked for it explicitly, not get a separate group."""
        set_default_language("fr")

        email = mail().to(support.PLAIN_ADDRESS).to(fr_member)
        email.send()
        deliver()

        record = support.sole(sent, "message for two fr-resolving recipients")

        assert support.envelope(record) == sorted([
            support.PLAIN_ADDRESS,
            support.FR_MEMBER["email"],
        ])


class TestThreeLanguages:
    def test_fr_nl_de_yields_three_messages(
        self, mail, fr_member, nl_member, make_recipient_member, by_language
    ):
        """FR, NL, and DE are each their own group, not a binary split."""
        de_member = make_recipient_member(
            dict(
                support.NL_MEMBER,
                userid="de_member",
                email="de.mitglied@gemeinde.example.be",
                fullname="Dieter Ostbelgier",
                language="de",
            )
        )

        grouped = by_language(mail().to([fr_member, nl_member, de_member]))

        assert set(grouped) == {"fr", "nl", "de"}, sorted(grouped)
        assert len({support.html_of(r.message) for r in grouped.values()}) == 3, (
            "three language groups but fewer than three distinct bodies"
        )
