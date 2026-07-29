"""SPEC §6.2 -- where the subject comes from.

> **Subject** comes from the template registration; ``.subject(...)`` exists as
> an override for edge cases and accepts a msgid or literal string.

Two rules, and the second has two halves. The default is the registration's
msgid, translated per language group (§6.2's per-language sending). The override
accepts *either* a msgid -- which must still be translated per group -- *or* a
literal, which must reach every group untouched. A builder that translated
literals would mangle "Convocation - seance du 12 aout" into itself in some
languages and into a msgid-shaped miss in others; a builder that did not
translate msgids would ship ``email_subject_notification`` to citizens.

Expected values are computed with ``zope.i18n.translate`` rather than typed out,
for the reason in ``support.translated``: a hardcoded French string turns every
catalog edit into a test failure *and* passes for a builder that ships the bare
msgid whenever the catalog has no entry.
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
        """§6.2: "comes from the template registration". Read out of discovery,
        so the registration and the expectation cannot drift apart."""
        set_default_language("fr")

        subject = subject_of(mail().to(support.PLAIN_ADDRESS))

        assert subject == support.translated(support.registration_subject(), "fr")

    def test_it_is_not_the_bare_msgid(self, mail, set_default_language, subject_of):
        """The failure that looks like success. §4 stores the subject as an i18n
        msgid, and ``email_subject_notification`` in an inbox is the visible tip
        of a missing ``target_language`` -- exactly the bug ``DECISIONS.md``
        records ``render()`` injecting ``target_language`` to avoid."""
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
        """``Products.MailHost`` substitutes ``[No Subject]`` for a message with
        no ``Subject`` header, so a builder that forgot the subject entirely
        produces a *plausible* mail rather than an error."""
        set_default_language("fr")

        subject = subject_of(mail().to(support.PLAIN_ADDRESS))

        assert subject.strip()
        assert subject != "[No Subject]", (
            "no Subject header was set; MailHost filled in its placeholder"
        )
        support.assert_render_is_clean(subject, "subject")


class TestOverrideWithAMsgid:
    """ "accepts a msgid" -- so it goes through the same per-group translation."""

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
        """The override must not opt out of §6.2's per-language sending -- that
        would make ``.subject(msgid)`` a trap: it looks i18n-aware and ships one
        language to everybody."""
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
    """ "or literal string" -- a literal is not a msgid and must survive."""

    def test_a_literal_override_reaches_the_header_unchanged(self, mail, subject_of):
        subject = subject_of(
            mail().to(support.PLAIN_ADDRESS).subject(support.LITERAL_SUBJECT)
        )

        assert subject == support.LITERAL_SUBJECT

    def test_a_literal_is_identical_in_every_language_group(
        self, mail, fr_member, nl_member, subjects_by_language
    ):
        """A literal has no catalog entry, so a builder that ran it through
        ``translate`` would return it unchanged *by accident* here -- which is
        fine. What must not happen is per-group divergence, which would mean the
        literal was being treated as a msgid and resolved against something."""
        subjects = subjects_by_language(
            mail().to(fr_member).to(nl_member).subject(support.LITERAL_SUBJECT)
        )

        assert set(subjects) == {"fr", "nl"}
        assert set(subjects.values()) == {support.LITERAL_SUBJECT}

    def test_a_non_ascii_literal_survives_the_headers(self, mail, subject_of):
        """Subjects are the one header a French or Dutch mail is guaranteed to
        put non-ASCII in. Broken header encoding shows up as ``=?utf-8?...?=`` in
        the recipient's inbox, and only in some clients."""
        literal = "Séance du conseil communal du 12 août"

        subject = subject_of(mail().to(support.PLAIN_ADDRESS).subject(literal))

        assert subject == literal


class TestTheOverrideDoesNotLeak:
    def test_the_last_call_wins(self, mail, subject_of):
        """§6.2 makes every method a plain accumulating setter; a subject is
        singular, so a second call replaces rather than appends. The failure
        worth catching is a header set twice -- ``Products.MailHost`` keeps both
        and clients show whichever they read first."""
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
