"""Transaction safety, and the one escape hatch.

Delivery goes through ``IMailHost``'s queue: an aborted transaction sends
nothing. ``.send(immediate=True)`` bypasses the queue.

An empty queue alone proves nothing: a builder that never queued
anything, a swallowed message, or a caught exception all leave the queue
empty too. So every assertion is paired with its opposite: abort cancels
a real queued delivery (``mailer.aborted``), commit delivers it, and
nothing is delivered before either happens.

The MailHost double replaces ``_makeMailer``, not ``_send``, so the real
``Products.MailHost`` and ``zope.sendmail`` code still runs. See
``imio.emailkit.testing.install_recording_mailhost``.
"""

import pytest
import support
import transaction


Email = support.require_builder()


@pytest.fixture
def queued(mail, mailhost, site_sender):
    """A ``.send()`` already done, nothing committed yet."""
    mail().to(support.PLAIN_ADDRESS).send()
    return mailhost


class TestQueuedIsTheDefault:
    def test_nothing_is_delivered_before_the_transaction_ends(self, queued):
        """Queued must mean not yet sent, not merely not yet checked."""
        assert queued.sent == [], (
            f"{len(queued.sent)} message(s) already delivered before commit: "
            "the send was not queued"
        )

    def test_a_delivery_really_was_joined_to_the_transaction(self, queued):
        """Queued must mean joined to the transaction, not dropped.

        ``onAbort`` only fires for a ``MailDataManager`` genuinely joined
        to the transaction, so a non-zero count is evidence the message
        was in flight.
        """
        transaction.abort()

        assert queued.aborted == 1, (
            "no queued delivery was cancelled by the abort, so none was ever "
            "joined to the transaction: .send() dropped the message"
        )


class TestAbortSendsNothing:
    def test_abort_leaves_the_queue_empty(self, queued):
        transaction.abort()

        assert queued.sent == [], (
            f"{len(queued.sent)} message(s) delivered after transaction.abort(); "
            "an aborted transaction sends nothing"
        )

    def test_abort_after_several_language_groups_sends_none_of_them(
        self, mail, mailhost, site_sender, fr_member, nl_member
    ):
        """An abort must cancel every language group's message, not just
        one."""
        mail().to(fr_member).to(nl_member).send()

        transaction.abort()

        assert mailhost.sent == []
        assert mailhost.aborted == 2, (
            "expected one cancelled delivery per language group, got "
            f"{mailhost.aborted}"
        )

    def test_abort_also_cancels_a_mail_with_an_attachment(
        self, mail, mailhost, site_sender
    ):
        """An attachment must not bypass the transaction guarantee."""
        mail().to(support.PLAIN_ADDRESS).attach(b"%PDF-1.7\n", filename="a.pdf").send()

        transaction.abort()

        assert mailhost.sent == []


class TestCommitSends:
    """Confirms a commit delivers, so the abort tests above are meaningful."""

    def test_commit_delivers_exactly_one_message(self, queued):
        transaction.commit()

        assert len(queued.sent) == 1, (
            f"{len(queued.sent)} message(s) after commit: the abort tests above "
            "only mean something if a commit does deliver"
        )

    def test_the_committed_message_is_the_one_that_was_built(self, queued):
        transaction.commit()

        record = support.sole(queued.sent)

        assert support.envelope(record) == [support.PLAIN_ADDRESS]
        support.assert_message_is_clean(record.message)

    def test_commit_delivers_one_message_per_language_group(
        self, mail, mailhost, site_sender, fr_member, nl_member
    ):
        mail().to(fr_member).to(nl_member).send()

        transaction.commit()

        assert len(mailhost.sent) == 2
        assert mailhost.aborted == 0


class TestImmediateIsTheEscapeHatch:
    """``.send(immediate=True)`` is the escape hatch."""

    def test_immediate_delivers_without_a_commit(self, mail, mailhost, site_sender):
        mail().to(support.PLAIN_ADDRESS).send(immediate=True)

        assert len(mailhost.sent) == 1, (
            "immediate=True did not deliver before the transaction ended, so it "
            "is not bypassing the queue"
        )

    def test_immediate_survives_an_abort(self, mail, mailhost, site_sender):
        """An immediate send is not cancelled by a later abort."""
        mail().to(support.PLAIN_ADDRESS).send(immediate=True)

        transaction.abort()

        assert len(mailhost.sent) == 1, (
            "an abort un-sent an immediate message: immediate=True is still "
            "going through the transaction-joined path"
        )

    def test_immediate_joins_nothing_to_the_transaction(
        self, mail, mailhost, site_sender
    ):
        """An immediate send must not also queue a delivery, or commit
        would double-send."""
        mail().to(support.PLAIN_ADDRESS).send(immediate=True)

        transaction.abort()

        assert mailhost.aborted == 0, (
            "immediate=True also queued a delivery, which would double-send on commit"
        )

    def test_immediate_produces_the_same_message_as_queued(
        self, mail, mailhost, set_default_language, site_sender
    ):
        """An immediate send must produce the same message as a queued
        one."""
        set_default_language("fr")

        mail().to(support.PLAIN_ADDRESS).send(immediate=True)
        immediate = support.sole(mailhost.sent).message
        mailhost.reset()

        mail().to(support.PLAIN_ADDRESS).send()
        transaction.commit()
        queued_message = support.sole(mailhost.sent).message

        assert support.bodies(immediate) == support.bodies(queued_message)
        assert support.subject_of(immediate) == support.subject_of(queued_message)
        assert support.addresses(immediate, "To") == support.addresses(
            queued_message, "To"
        )

    def test_immediate_is_not_the_default(self, mail, mailhost, site_sender):
        """``.send()`` with no arguments must queue, not deliver
        immediately."""
        mail().to(support.PLAIN_ADDRESS).send()

        assert mailhost.sent == [], ".send() with no arguments delivered immediately"


class TestNothingIsSentWithoutSend:
    def test_a_builder_that_is_never_sent_queues_nothing(
        self, mail, mailhost, site_sender, fr_member
    ):
        """No builder method does I/O before ``.send()``."""
        (
            mail()
            .to(fr_member)
            .cc(support.PLAIN_ADDRESS)
            .bcc(support.OTHER_ADDRESS)
            .reply_to(support.REPLY_TO)
            .sender(support.OVERRIDE_SENDER)
            .subject(support.LITERAL_SUBJECT)
            .attach(b"%PDF-1.7\n", filename="a.pdf")
        )

        transaction.commit()

        assert mailhost.sent == [], "a builder that was never sent sent something"
        assert mailhost.aborted == 0
