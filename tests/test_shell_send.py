"""Gate 8 -- sending a shell-rendered body.

> ``Email(...)`` can send a shell-rendered body with no builder change.

The reasoning: ``render_shell`` "returns the same ``(html, text)`` pair and
shares ``render()``'s code path […] so ``Email`` sends its output with no change at
all", and "no new builder methods -- the builder stays frozen" is a non-goal.

**What this module found.** The compatibility claim holds -- shell output goes out
through the builder's own assembly and the real ``MailHost``, and arrives as a correct
message. The literal claim does not: ``Email.send()`` renders from a *template
name* (``render(self.name, …)``), and ``render_shell`` deliberately has no name --
``imio.emailkit.render`` resolves the shell by path and documents why it is not
registered for discovery. So there is no argument, no keyword and no method through
which a caller hands ``Email`` a pre-rendered pair, and:

* :class:`TestTheObviousBuilderPath` states the one reading of gate 8 that would
  need no builder change at all -- ``Email("imio.emailkit:shell")`` -- as a
  **strict xfail**, because that is a real gap in the phase, not a test to drop;
* :class:`TestTheFrozenSurfaceStillCarriesShellOutput` verifies what *is* true, by
  driving the exact assembly function ``Email.send()`` uses and the exact
  ``MailHost`` call, and comparing the result against a message the builder really
  built.

The two together are the honest form of gate 8: the mechanism is proven, the last
mile is named. Closing it is a maintainer decision (register the shell for
discovery, or document a recipe), and either way it is one line of code plus a
decision entry -- not a change to the builder.
"""

import pytest
import support


render_shell = support.require_shell()
Email = support.require_builder()

SHELL_FIXTURE = support.SHELL_FIXTURES[0]


@pytest.fixture
def legacy():
    """``(subject, body_html)`` of the committed PloneMeeting-shaped fixture."""
    return support.load_shell_fixture(SHELL_FIXTURE)


@pytest.fixture
def shell_parts(mail_portal, legacy):
    """What a migrated consumer has in hand: ``render_shell``'s return value."""
    subject, body = legacy
    return render_shell(subject, body, language="fr")


class TestTheObviousBuilderPath:
    """Gate 8 read literally: ``Email(...)`` sends the shell, no builder change.

    With the shell registered like any other template, this is the whole
    migration recipe -- ``.with_context(subject=…, body_html=…)`` and nothing else,
    every builder feature (per-language grouping, attachments, transaction safety,
    ``RecipientError``) included for free. It is also the only reading in which the
    words "``Email(...)`` can send" are literally true.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "gate 8 gap, reported not weakened: render_shell resolves the shell by "
            "path and imio.emailkit.render deliberately does not register it for "
            "discovery, so Email('imio.emailkit:shell') raises TemplateNotFound. "
            "Email.send() renders from a template name and has no way to accept a "
            "pre-rendered (html, text) pair, so no frozen-surface call sends shell "
            "output today. Fixing it is a maintainer decision -- register the shell "
            "(one <emailkit:template> entry, and the subject would then come "
            "from .subject()) or document a recipe that assembles the message "
            "directly. TestTheFrozenSurfaceStillCarriesShellOutput proves the "
            "mechanism either way."
        ),
    )
    def test_the_builder_can_send_the_shell_by_name(
        self, mail_portal, mailhost, site_sender, deliver, sent, legacy
    ):
        subject, body = legacy

        Email(support.qualified("shell")).subject(subject).with_context(
            subject=subject, body_html=body
        ).to(support.PLAIN_ADDRESS).send()
        deliver()

        message = support.sole(sent).message
        _text, html = support.bodies(message)
        assert body in html


class TestTheFrozenSurfaceStillCarriesShellOutput:
    """What gate 8's compatibility claim really asserts, and it does hold.

    ``Email.send()`` does three things with a rendered pair: it hands them to
    :func:`imio.emailkit.email.build_message`, hands the result to ``MailHost``, and
    lets the transaction decide. This drives all three with ``render_shell``'s
    output instead of ``render()``'s -- the same functions, the same call, no new
    code path -- so a shell body that could not survive the builder's assembly
    (wrong types, a body the header machinery mangles, an encoding ``policy.SMTP``
    refuses) fails here.
    """

    def test_render_shell_returns_what_the_builder_consumes(self, shell_parts):
        """The type-level half of "no builder change": two ``str``, html second in
        the pair as ``render()`` returns them."""
        assert isinstance(shell_parts, tuple)
        assert len(shell_parts) == 2
        html, text = shell_parts
        assert isinstance(html, str) and html.strip()
        assert isinstance(text, str) and text.strip()
        assert "<html" in html.lower()
        assert "<html" not in text.lower()

    def test_the_builder_grew_no_shell_method(self, mail_portal):
        """The builder is frozen.

        ``tests/test_builder.py`` already asserts the closed set of nine methods;
        this names the Phase 3 temptations specifically, so a
        ``.body_html()``/``.shell()``/``.html()`` arriving with this phase is
        rejected by a test that says *why*.
        """
        forbidden = ("shell", "render_shell", "body_html", "html", "text", "wrap")

        grew = [name for name in forbidden if hasattr(Email, name)]

        assert grew == [], (
            f"Email grew {grew} for the shell; render_shell is meant to be a "
            "render() sibling precisely so that the builder stays frozen"
        )

    def test_a_shell_body_goes_out_through_the_builders_own_assembly(
        self, mail_portal, mailhost, site_sender, deliver, sent, shell_parts, legacy
    ):
        """End to end on the real delivery path: assemble, queue, commit, read.

        ``build_message`` is the function ``Email.send()`` calls, and
        ``mailhost.send(message)`` without ``immediate`` is the call it makes -- so
        this is the builder's delivery, byte for byte, with a shell-rendered body in it.
        """
        from imio.emailkit.email import build_message
        from imio.emailkit.recipients import resolve
        from Products.MailHost.interfaces import IMailHost
        from zope.component import getUtility

        subject, body = legacy
        html, text = shell_parts

        message = build_message(
            sender=support.SITE_SENDER_ADDRESS,
            fields={"to": resolve([support.PLAIN_ADDRESS])},
            reply_to=[],
            subject=subject,
            html=html,
            text=text,
            attachments=[],
        )
        getUtility(IMailHost).send(message)

        assert sent == [], "the message reached the MTA before the commit"
        deliver()

        record = support.sole(sent)
        assert support.envelope(record) == [support.PLAIN_ADDRESS]
        sent_text, sent_html = support.bodies(record.message)
        assert body in sent_html, "the legacy body did not survive message assembly"
        # ``support.decoded`` normalises the wire's CRLF and trailing newlines,
        # which are transport details rather than values -- so the comparison is
        # against the render output with the same normalisation applied.
        assert sent_html == html.rstrip("\n")
        assert sent_text == text.rstrip("\n")
        support.assert_message_is_clean(record.message)

    def test_the_message_shape_matches_one_the_builder_really_built(
        self,
        mail_portal,
        mailhost,
        site_sender,
        deliver,
        sent,
        mail,
        shell_parts,
        legacy,
    ):
        """The comparison that makes "with no builder change" checkable.

        A shell-bodied message and a real ``Email(...).send()`` message are built
        the same way, so everything except the payload must be the same: MIME
        structure, part order, transfer encodings, header set. If they diverge, the
        shell needs builder support after all -- which is exactly what gate 8
        denies.
        """
        from imio.emailkit.email import build_message
        from imio.emailkit.recipients import resolve
        from Products.MailHost.interfaces import IMailHost
        from zope.component import getUtility

        subject, _body = legacy
        html, text = shell_parts

        mail().to(support.PLAIN_ADDRESS).send()
        getUtility(IMailHost).send(
            build_message(
                sender=support.SITE_SENDER_ADDRESS,
                fields={"to": resolve([support.PLAIN_ADDRESS])},
                reply_to=[],
                subject=subject,
                html=html,
                text=text,
                attachments=[],
            )
        )
        deliver()

        assert len(sent) == 2, f"expected two messages, got {len(sent)}"
        authored, shell = (record.message for record in sent)

        assert shell.get_content_type() == authored.get_content_type()
        assert [part.get_content_type() for part in support.body_parts(shell)] == [
            part.get_content_type() for part in support.body_parts(authored)
        ]
        assert [
            part["Content-Transfer-Encoding"] for part in support.body_parts(shell)
        ] == [
            part["Content-Transfer-Encoding"] for part in support.body_parts(authored)
        ]
        assert set(shell.keys()) == set(authored.keys())
        assert support.addresses(shell, "To") == support.addresses(authored, "To")

    def test_an_aborted_transaction_sends_no_shell_mail(
        self, mail_portal, mailhost, site_sender, sent, shell_parts, legacy
    ):
        """The transaction guarantee is not the builder's, it is the delivery
        path's -- so it has to hold for a shell body too. A notification queued in
        a transaction that then fails must not arrive: the item was never
        published.
        """
        from imio.emailkit.email import build_message
        from imio.emailkit.recipients import resolve
        from Products.MailHost.interfaces import IMailHost
        from zope.component import getUtility

        import transaction

        subject, _body = legacy
        html, text = shell_parts

        getUtility(IMailHost).send(
            build_message(
                sender=support.SITE_SENDER_ADDRESS,
                fields={"to": resolve([support.PLAIN_ADDRESS])},
                reply_to=[],
                subject=subject,
                html=html,
                text=text,
                attachments=[],
            )
        )
        transaction.abort()

        assert sent == []
        assert mailhost.aborted == 1, (
            "no delivery was cancelled: the message was never joined to the "
            "transaction, so this test would pass even with immediate delivery"
        )

    def test_the_subject_and_the_heading_agree(
        self, mail_portal, mailhost, site_sender, deliver, sent, legacy
    ):
        """The one thing a shell caller can get wrong that ``render()`` callers
        cannot: the subject is passed twice -- once to ``render_shell`` for the
        heading, once as the message header -- and a mail whose header and heading
        disagree looks like it was sent to the wrong person.

        Asserted at the level the caller controls: one value in, the same value in
        both places out. This is also the strongest argument for registering the
        shell (see :class:`TestTheObviousBuilderPath`), which would remove the
        duplication entirely.
        """
        from imio.emailkit.email import build_message
        from imio.emailkit.recipients import resolve
        from Products.MailHost.interfaces import IMailHost
        from zope.component import getUtility

        msgid = support.message_id(
            support.OVERRIDE_SUBJECT_MSGID, default="Password reset request"
        )
        expected = support.translated(msgid, "fr")
        html, text = render_shell(msgid, "<p>Corps</p>", language="fr")

        getUtility(IMailHost).send(
            build_message(
                sender=support.SITE_SENDER_ADDRESS,
                fields={"to": resolve([support.PLAIN_ADDRESS])},
                reply_to=[],
                subject=support.translated(msgid, "fr"),
                html=html,
                text=text,
                attachments=[],
            )
        )
        deliver()

        message = support.sole(sent).message

        assert support.subject_of(message) == expected
        assert expected in support.html_of(message)
        assert support.lang_of(message) == "fr"
