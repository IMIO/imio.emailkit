"""Sending a shell-rendered body.

``Email(...)`` can send a shell-rendered body with no change to the
builder, in the sense that matters: shell output goes through the
builder's own assembly and the real ``MailHost``.

``Email.send()`` renders from a template name, and ``render_shell`` has
no name registered for discovery, so no argument or method lets a caller
hand ``Email`` a pre-rendered pair directly.

* :class:`TestTheObviousBuilderPath` marks that direct reading as a
  strict xfail: a real gap, not a test to drop.
* :class:`TestTheFrozenSurfaceStillCarriesShellOutput` checks what does
  hold, using the same assembly function and ``MailHost`` call
  ``Email.send()`` uses.
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
    """``render_shell``'s return value."""
    subject, body = legacy
    return render_shell(subject, body, language="fr")


class TestTheObviousBuilderPath:
    """``Email(...)`` sends the shell with no builder change, read literally."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "render_shell resolves the shell by path, and imio.emailkit.render "
            "does not register it for discovery, so Email('imio.emailkit:shell') "
            "raises TemplateNotFound. Email.send() renders from a template name "
            "and cannot accept a pre-rendered (html, text) pair, so no "
            "frozen-surface call sends shell output today. Fixing it is a "
            "maintainer decision: register the shell (one <emailkit:template> "
            "entry, and the subject would then come from .subject()) or document "
            "a recipe that assembles the message directly. "
            "TestTheFrozenSurfaceStillCarriesShellOutput proves the mechanism "
            "either way."
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
    """The compatibility claim holds: the same assembly and ``MailHost``
    call ``Email.send()`` uses also carry ``render_shell``'s output."""

    def test_render_shell_returns_what_the_builder_consumes(self, shell_parts):
        """Returns two ``str``, html second, like ``render()``."""
        assert isinstance(shell_parts, tuple)
        assert len(shell_parts) == 2
        html, text = shell_parts
        assert isinstance(html, str) and html.strip()
        assert isinstance(text, str) and text.strip()
        assert "<html" in html.lower()
        assert "<html" not in text.lower()

    def test_the_builder_grew_no_shell_method(self, mail_portal):
        """The builder is frozen: it must not gain a shell-specific method
        like ``.body_html()``, ``.shell()``, or ``.html()``."""
        forbidden = ("shell", "render_shell", "body_html", "html", "text", "wrap")

        grew = [name for name in forbidden if hasattr(Email, name)]

        assert grew == [], (
            f"Email grew {grew} for the shell; render_shell is meant to be a "
            "render() sibling precisely so that the builder stays frozen"
        )

    def test_a_shell_body_goes_out_through_the_builders_own_assembly(
        self, mail_portal, mailhost, site_sender, deliver, sent, shell_parts, legacy
    ):
        """Drives the real delivery path with ``build_message`` and
        ``mailhost.send()``, the same calls ``Email.send()`` makes."""
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
        # The trailing newline is a transport artifact, not a value, so it
        # is stripped before comparing to the render output.
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
        """A shell-bodied message must share its MIME shape with a real
        ``Email(...).send()`` message. Only the payload should differ."""
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
        """The transaction guarantee belongs to the delivery path, not the
        builder, so it must hold for a shell body too."""
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
        """The subject, passed once to ``render_shell`` and once as the
        header, must agree in both places."""
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
