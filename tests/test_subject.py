"""Where the subject comes from.

The subject defaults to the template registration's msgid, translated
per language group. ``.subject(...)`` overrides it, and accepts either a
msgid, still translated per group, or a literal string, which reaches
every group untouched.

Expected values are computed with ``zope.i18n.translate`` rather than
typed out, so a catalog edit cannot silently break these tests.
"""

import pytest
import support


Email = support.require_builder()


@pytest.fixture
def subject_of(deliver, sent):
    """``subject_of(email)`` -> the ``Subject`` of the one delivered message."""

    def send_and_read(email):
        email.send()
        deliver()
        return support.subject_of(support.sole(sent).message)

    return send_and_read


@pytest.fixture
def subjects_by_language(deliver, sent):
    """``subjects_by_language(email)`` -> ``{lang: subject}``."""

    def send_and_read(email):
        email.send()
        deliver()
        return {
            support.lang_of(record.message): support.subject_of(record.message)
            for record in sent
        }

    return send_and_read


class TestTheDefaultSubject:
    def test_it_comes_from_the_registration(
        self, mail, set_default_language, subject_of
    ):
        """Reads the expected subject out of discovery, so the registration
        and the expectation cannot drift apart."""
        set_default_language("fr")

        subject = subject_of(mail().to(support.PLAIN_ADDRESS))

        assert subject == support.translated(support.registration_subject(), "fr")

    def test_it_is_not_the_bare_msgid(self, mail, set_default_language, subject_of):
        """The subject is stored as an i18n msgid. A bare msgid like
        ``email_subject_notification`` reaching the inbox means translation
        was skipped."""
        set_default_language("fr")

        subject = subject_of(mail().to(support.PLAIN_ADDRESS))

        assert subject != str(support.registration_subject()), (
            f"the subject shipped as the raw msgid: {subject!r}"
        )
        assert not subject.startswith("email_subject_"), (
            f"the subject looks like an untranslated msgid: {subject!r}"
        )

    def test_it_is_never_empty_or_a_placeholder(
        self, mail, set_default_language, subject_of
    ):
        """``Products.MailHost`` substitutes ``[No Subject]`` when no
        ``Subject`` header is set, so a missing subject produces a
        plausible mail, not an error."""
        set_default_language("fr")

        subject = subject_of(mail().to(support.PLAIN_ADDRESS))

        assert subject.strip()
        assert subject != "[No Subject]", (
            "no Subject header was set; MailHost filled in its placeholder"
        )
        support.assert_render_is_clean(subject, "subject")


class TestOverrideWithAMsgid:
    """A msgid override goes through the same per-group translation as the
    default subject."""

    def test_a_msgid_override_is_translated(
        self, mail, set_default_language, subject_of
    ):
        set_default_language("fr")
        msgid = support.message_id(support.OVERRIDE_SUBJECT_MSGID)

        subject = subject_of(mail().to(support.PLAIN_ADDRESS).subject(msgid))

        assert subject == support.translated(msgid, "fr")
        assert subject != support.OVERRIDE_SUBJECT_MSGID

    def test_a_msgid_override_replaces_the_registration_subject(
        self, mail, set_default_language, subject_of
    ):
        """Otherwise ``.subject()`` is decoration."""
        set_default_language("fr")
        msgid = support.message_id(support.OVERRIDE_SUBJECT_MSGID)

        subject = subject_of(mail().to(support.PLAIN_ADDRESS).subject(msgid))

        assert subject != support.translated(support.registration_subject(), "fr")

    def test_a_msgid_override_is_translated_per_language_group(
        self, mail, fr_member, nl_member, subjects_by_language
    ):
        """The override must not skip per-language translation, or it would
        ship one language to everybody."""
        msgid = support.message_id(support.OVERRIDE_SUBJECT_MSGID)

        subjects = subjects_by_language(
            mail().to(fr_member).to(nl_member).subject(msgid)
        )

        assert subjects == {
            "fr": support.translated(msgid, "fr"),
            "nl": support.translated(msgid, "nl"),
        }
        assert subjects["fr"] != subjects["nl"], (
            "the msgid override was not translated per group"
        )


class TestOverrideWithALiteral:
    """A literal is not a msgid and must survive unchanged."""

    def test_a_literal_override_reaches_the_header_unchanged(self, mail, subject_of):
        subject = subject_of(
            mail().to(support.PLAIN_ADDRESS).subject(support.LITERAL_SUBJECT)
        )

        assert subject == support.LITERAL_SUBJECT

    def test_a_literal_is_identical_in_every_language_group(
        self, mail, fr_member, nl_member, subjects_by_language
    ):
        """A literal must reach every language group unchanged, not diverge
        as if it were a msgid."""
        subjects = subjects_by_language(
            mail().to(fr_member).to(nl_member).subject(support.LITERAL_SUBJECT)
        )

        assert set(subjects) == {"fr", "nl"}
        assert set(subjects.values()) == {support.LITERAL_SUBJECT}

    def test_a_non_ascii_literal_survives_the_headers(self, mail, subject_of):
        """Non-ASCII subjects must not break header encoding."""
        literal = "Séance du conseil communal du 12 août"

        subject = subject_of(mail().to(support.PLAIN_ADDRESS).subject(literal))

        assert subject == literal


class TestTheOverrideDoesNotLeak:
    def test_the_last_call_wins(self, mail, subject_of):
        """A second ``.subject()`` call must replace the first, not add a
        second header."""
        subject = subject_of(
            mail().to(support.PLAIN_ADDRESS).subject("First").subject("Second")
        )

        assert subject == "Second"

    def test_only_one_subject_header_is_emitted(self, mail, deliver, sent):
        email = mail().to(support.PLAIN_ADDRESS).subject(support.LITERAL_SUBJECT)

        email.send()
        deliver()
        message = support.sole(sent).message

        assert len(message.get_all("Subject") or []) == 1, (
            f"{len(message.get_all('Subject'))} Subject headers in one message"
        )
