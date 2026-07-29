"""SPEC §6.2/§7 -- transaction safety, and the one escape hatch.

> **Transaction safety by default:** delivery via ``IMailHost`` queued send -- an
> aborted transaction sends nothing. ``.send(immediate=True)`` is the escape
> hatch.

§7 names the test outright: "Transaction abort test: ``.send()`` + abort ->
MailHost queue empty."

**An empty queue proves nothing on its own.** A builder that never queued
anything, a MailHost double that swallows messages, a ``.send()`` that raised and
was caught -- all three leave the queue empty and turn §7's headline test green
for the wrong reason. So every assertion here is paired with its opposite:

* abort -> nothing delivered **and** the queued delivery was actively cancelled
  (``mailer.aborted``, which only increments if a ``MailDataManager`` really was
  joined to the transaction);
* commit -> the message *is* delivered, so the abort case is a difference rather
  than a constant;
* before either -> nothing has been delivered yet, which is what "queued" means.

That triangle is only observable because the MailHost double replaces
``_makeMailer`` rather than ``_send``: the real ``Products.MailHost`` and
``zope.sendmail`` code above it still runs. See
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
        """ "Queued" has to mean *not yet sent*. A builder that opened an SMTP
        connection inside ``.send()`` would pass every content assertion in this
        suite and make §6.2's guarantee unimplementable."""
        assert queued.sent == [], (
            f"{len(queued.sent)} message(s) already delivered before commit: "
            "the send was not queued"
        )

    def test_a_delivery_really_was_joined_to_the_transaction(self, queued):
        """The other half: queued, not *dropped*.

        Proved by aborting and counting the cancellations -- ``onAbort`` only
        fires for a ``MailDataManager`` that was genuinely joined to the current
        transaction, so a non-zero count is positive evidence that the message
        was in flight.
        """
        transaction.abort()

        assert queued.aborted == 1, (
            "no queued delivery was cancelled by the abort, so none was ever "
            "joined to the transaction: .send() dropped the message"
        )


class TestAbortSendsNothing:
    """§7's named test."""

    def test_abort_leaves_the_queue_empty(self, queued):
        transaction.abort()

        assert queued.sent == [], (
            f"{len(queued.sent)} message(s) delivered after transaction.abort(); "
            "SPEC §6.2: 'an aborted transaction sends nothing'"
        )

    def test_abort_after_several_language_groups_sends_none_of_them(
        self, mail, mailhost, site_sender, fr_member, nl_member
    ):
        """Per-language sending emits several messages from one ``.send()``. All
        of them are one transaction's worth, so an abort must take all of them --
        a partial rollback would deliver to the French commune and not the Dutch
        one, from an operation the caller believes failed."""
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
        """Attachments go through ``add_attachment`` at assembly time, which is
        real work; a builder that streamed the file straight to the MTA to avoid
        holding it in memory would lose the guarantee here and nowhere else."""
        mail().to(support.PLAIN_ADDRESS).attach(b"%PDF-1.7\n", filename="a.pdf").send()

        transaction.abort()

        assert mailhost.sent == []


class TestCommitSends:
    """The non-vacuity control for everything above."""

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
    """§6.2: ``.send(immediate=True)`` "is the escape hatch"."""

    def test_immediate_delivers_without_a_commit(self, mail, mailhost, site_sender):
        mail().to(support.PLAIN_ADDRESS).send(immediate=True)

        assert len(mailhost.sent) == 1, (
            "immediate=True did not deliver before the transaction ended, so it "
            "is not bypassing the queue"
        )

    def test_immediate_survives_an_abort(self, mail, mailhost, site_sender):
        """The defining property. "Escape hatch" means the caller has taken the
        transaction guarantee off, deliberately: the mail is gone and a later
        rollback cannot recall it."""
        mail().to(support.PLAIN_ADDRESS).send(immediate=True)

        transaction.abort()

        assert len(mailhost.sent) == 1, (
            "an abort un-sent an immediate message: immediate=True is still "
            "going through the transaction-joined path"
        )

    def test_immediate_joins_nothing_to_the_transaction(
        self, mail, mailhost, site_sender
    ):
        """Nothing to cancel, because nothing was queued. If ``aborted`` were
        non-zero the builder would have queued *and* sent immediately -- a
        duplicate delivery on commit."""
        mail().to(support.PLAIN_ADDRESS).send(immediate=True)

        transaction.abort()

        assert mailhost.aborted == 0, (
            "immediate=True also queued a delivery, which would double-send on commit"
        )

    def test_immediate_produces_the_same_message_as_queued(
        self, mail, mailhost, set_default_language, site_sender
    ):
        """The escape hatch changes *when*, never *what*. A separate assembly
        path for immediate sends would drift, and it would drift on the code path
        used for the mails somebody chose to bypass the queue for."""
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
        """Restating §6.2's word "default" as an assertion, because the two
        behaviours differ only in a flag and a wrong default would be invisible
        until the first failed transaction sent a mail it should not have."""
        mail().to(support.PLAIN_ADDRESS).send()

        assert mailhost.sent == [], ".send() with no arguments delivered immediately"


class TestNothingIsSentWithoutSend:
    def test_a_builder_that_is_never_sent_queues_nothing(
        self, mail, mailhost, site_sender, fr_member
    ):
        """§6.2: the builder "holds data, it does not grow behavior".
        ``docs/plans/phase-2.md`` §6 gate 8: "no method does I/O before
        ``.send()``"."""
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
