"""SPEC §6.2 -- per-language sending, the headline feature of the builder.

> **Per-language sending:** ``.send()`` groups recipients by resolved language,
> renders once per language group (subject msgid translated accordingly), and
> emits one message per group. FR/NL communes are handled with no caller effort.

Three things have to hold at once, and each fails on its own:

1. **the count** -- one message per *language*, not per recipient and not one
   message for everybody;
2. **the partition** -- every recipient in the group whose language they asked
   for, and in no other;
3. **the content** -- that group's subject translation *and* that group's
   rendered body.

(3) is where this goes wrong quietly. A builder that groups correctly but renders
once and reuses the result sends Dutch recipients a French body under a Dutch
subject, and every count-based assertion still passes. So the body assertions
here compare against ``render(..., language=...)`` -- §6.1's pure function, the
same one §7's golden files pin -- rather than against a marker.
"""

import pytest
import support


Email = support.require_builder()


@pytest.fixture
def by_language(deliver, sent):
    """``by_language(email)`` -> ``{lang: SentMail}`` after a real commit.

    Keyed off the ``lang`` attribute the kit layout emits on ``<html>`` from the
    render language (§3), because that is the one piece of evidence that comes
    from the *body* rather than from the builder's own bookkeeping.
    """

    def send_and_group(email):
        email.send()
        deliver()
        grouped = {}
        for record in sent:
            language = support.lang_of(record.message)
            assert language not in grouped, (
                f"two messages rendered in {language!r}: §6.2 emits one message "
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
            "§6.2 emits one message per language group."
        )

    def test_each_message_goes_only_to_its_own_group(
        self, mail, fr_member, nl_member, by_language
    ):
        """The partition. Cross-contamination here means somebody receives a
        mail in a language they did not ask for while also appearing in a
        stranger's ``To`` header -- a privacy problem on top of an i18n one."""
        grouped = by_language(mail().to(fr_member).to(nl_member))

        assert set(grouped) == {"fr", "nl"}, f"language groups: {sorted(grouped)}"
        assert support.envelope(grouped["fr"]) == [support.FR_MEMBER["email"]]
        assert support.envelope(grouped["nl"]) == [support.NL_MEMBER["email"]]

    def test_each_message_carries_its_own_subject_translation(
        self, mail, fr_member, nl_member, by_language
    ):
        """§6.2: "subject msgid translated accordingly"."""
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
        """The guard on the test above. ``translated()`` returns the bare msgid
        when the catalog has no entry, so comparing against it would pass for a
        builder that never translated anything at all -- as long as it never
        translated *consistently*. These two catalog entries genuinely differ, so
        equal subjects mean the translation step did not happen."""
        grouped = by_language(mail().to(fr_member).to(nl_member))

        assert support.subject_of(grouped["fr"].message) != support.subject_of(
            grouped["nl"].message
        ), "both language groups got the same subject: nothing was translated"

    def test_each_message_carries_its_own_rendered_body(
        self, mail, fr_member, nl_member, by_language, notification_context
    ):
        """The assertion this module exists for: the body is §6.1's ``render()``
        output *for that group's language*, byte for byte.

        Not "contains a French word" -- Phase 0 proved marker assertions coexist
        with raw ``${}`` reaching the inbox, and a reused body coexists with
        every count and header assertion passing.
        """
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
        """Same guard, applied to the body: if both groups got the same HTML the
        render-once-and-reuse bug is present, whatever the subjects say."""
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
        """ "One message per group", not one per person. A builder that emitted
        one message each would work, look fine, and quietly turn a 400-recipient
        convocation into 400 SMTP transactions."""
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
        """A Cc recipient has a language like anybody else. Leaving Cc/Bcc out of
        the grouping would either send them the wrong language or -- worse -- put
        the same Cc address on every group's message, i.e. one copy per
        language."""
        grouped = by_language(mail().to(fr_member).cc(nl_member))

        assert set(grouped) == {"fr", "nl"}, (
            "a Cc recipient with another language did not get their own group: "
            f"{sorted(grouped)}"
        )
        nl_addresses = support.envelope(grouped["nl"])
        assert nl_addresses == [support.NL_MEMBER["email"]]


class TestTheFallbackLanguage:
    """``docs/plans/phase-2.md`` §4: a recipient with no language falls back to
    "the site default"."""

    def test_a_plain_address_renders_in_the_site_default(
        self, mail, set_default_language, by_language
    ):
        """A bare address has no member behind it, so
        ``IEmailRecipient.language`` is ``None`` -- §6.2 says so explicitly
        ("may be ``None``")."""
        set_default_language("nl")

        grouped = by_language(mail().to(support.PLAIN_ADDRESS))

        assert set(grouped) == {"nl"}, (
            "a recipient with no language did not fall back to the site default "
            f"(nl): {sorted(grouped)}"
        )

    def test_the_fallback_follows_the_site(
        self, mail, set_default_language, by_language
    ):
        """The other half: change the site default and the fallback moves with
        it. Without this, a hardcoded ``"en"`` (or ``"fr"``, which would look
        right in Wallonia) passes the test above."""
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
        """Most Plone members never set a preferred language, so this is the
        common case, not the edge one."""
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
        """Grouping is by resolved language, so a recipient whose language *is*
        the site default must land in the same group as one who asked for it
        explicitly -- not in a separate "unknown" group producing two messages
        with identical bodies."""
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
        """§1 lists FR/NL/DE as first-class. Two groups can be produced by an
        accidental binary split; three cannot."""
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
