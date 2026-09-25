"""Recipient resolution and the address headers.

``.to()``/``.cc()``/``.bcc()`` accept an email string, a Plone member, a
userid, or an iterable of those, in any mix. Resolution goes through one
adapter. An unresolvable recipient raises ``RecipientError`` at
``.send()`` time instead of being dropped silently.

Most assertions here read the envelope (``SentMail.recipients``), not
only the ``To``/``Cc`` headers. ``Products.MailHost`` rewrites those
headers from its own arguments, so an address present in a header but
not in the envelope never actually reaches anyone.
"""

import pytest
import support


Email = support.require_builder()
RecipientError, IEmailRecipient = support.require_errors(
    "RecipientError", "IEmailRecipient"
)


@pytest.fixture(autouse=True)
def one_language_group(set_default_language):
    """Pins the site default to the test members' language.

    The builder groups messages by resolved language, and a bare address
    has none. Without this, mixing a French member with a plain address
    sends two messages for a reason unrelated to what each test checks.
    """
    return set_default_language(support.FR_MEMBER["language"])


@pytest.fixture
def one_message(mail, deliver, sent):
    """``one_message(email)`` -> the single delivered message, parsed."""

    def send_and_read(email):
        email.send()
        deliver()
        return support.sole(sent).message

    return send_and_read


@pytest.fixture
def envelope(mail, deliver, sent):
    """``envelope(email)`` -> the addresses the SMTP layer was handed."""

    def send_and_read(email):
        email.send()
        deliver()
        return support.envelope(support.sole(sent))

    return send_and_read


class TestTheAdapterContract:
    """The recipient contract pins ``IEmailRecipient`` itself, not just its effects."""

    def test_the_interface_declares_the_three_attributes(self):
        """``email``, ``fullname``, and ``language`` are the required attributes.

        The address goes in the envelope, the fullname in the display
        name, and the language drives per-language grouping.
        """
        names = set(IEmailRecipient.names())

        assert {"email", "fullname", "language"} <= names, (
            f"IEmailRecipient is missing required attributes: {sorted(names)}"
        )

    def test_a_string_adapts_to_a_recipient(self, mail_portal):
        """A default adapter exists for a ``str`` address."""
        recipient = IEmailRecipient(support.PLAIN_ADDRESS, None)

        assert recipient is not None, (
            "no IEmailRecipient adapter for str; one is required"
        )
        assert recipient.email.lower() == support.PLAIN_ADDRESS

    def test_a_member_adapts_to_a_recipient(self, fr_member):
        recipient = IEmailRecipient(fr_member, None)

        assert recipient is not None, (
            "no IEmailRecipient adapter for a Plone member; one is required"
        )
        assert recipient.email.lower() == support.FR_MEMBER["email"]

    def test_a_member_recipient_carries_its_language(self, fr_member):
        """``.send()`` groups by this attribute. Returning ``None`` here would
        collapse every language group into the site default."""
        assert IEmailRecipient(fr_member, None).language == "fr"


class TestSingleRecipientForms:
    """One form at a time: string, member, userid."""

    def test_an_email_string(self, mail, envelope):
        addresses = envelope(mail().to(support.PLAIN_ADDRESS))

        assert addresses == [support.PLAIN_ADDRESS]

    def test_a_member_object(self, mail, fr_member, envelope):
        addresses = envelope(mail().to(fr_member))

        assert addresses == [support.FR_MEMBER["email"]]

    def test_a_userid(self, mail, fr_member, envelope):
        """A userid must resolve through the member, not as a literal address.

        A userid treated as a literal address produces a bad address that
        MailHost accepts and the MTA bounces later.
        """
        addresses = envelope(mail().to(support.FR_MEMBER["userid"]))

        assert addresses == [support.FR_MEMBER["email"]]

    def test_a_member_contributes_its_display_name(self, mail, fr_member, one_message):
        """The adapter's ``fullname`` must reach the address header's display
        name."""
        message = one_message(mail().to(fr_member))

        assert support.FR_MEMBER["fullname"] in support.display_names(message, "To"), (
            f"the member's fullname is not the display name in To: {message['To']!r}"
        )


class TestIterablesAndMixtures:
    def test_a_list_of_addresses(self, mail, envelope):
        addresses = envelope(mail().to([support.PLAIN_ADDRESS, support.OTHER_ADDRESS]))

        assert addresses == sorted([support.PLAIN_ADDRESS, support.OTHER_ADDRESS])

    def test_a_tuple_is_an_iterable_too(self, mail, envelope):
        addresses = envelope(mail().to((support.PLAIN_ADDRESS, support.OTHER_ADDRESS)))

        assert addresses == sorted([support.PLAIN_ADDRESS, support.OTHER_ADDRESS])

    def test_a_mixed_iterable(self, mail, fr_member, envelope):
        """Accepts a mix of forms in one call."""
        addresses = envelope(
            mail().to([fr_member, support.PLAIN_ADDRESS, support.FR_MEMBER["userid"]])
        )

        assert addresses == sorted([support.FR_MEMBER["email"], support.PLAIN_ADDRESS])

    def test_repeated_calls_accumulate(self, mail, fr_member, envelope):
        """A second ``.to()`` call must add to the first, not replace it."""
        addresses = envelope(
            mail().to(fr_member).to(support.PLAIN_ADDRESS).to(support.OTHER_ADDRESS)
        )

        assert addresses == sorted([
            support.FR_MEMBER["email"],
            support.PLAIN_ADDRESS,
            support.OTHER_ADDRESS,
        ])

    def test_a_generator_is_accepted_and_consumed_once(self, mail, envelope):
        """A generator must be stored, not left to be re-iterated.

        ``.send()`` may render several language groups from the same
        recipient set. An unstored generator is empty by the second group.
        """
        addresses = envelope(
            mail().to(a for a in (support.PLAIN_ADDRESS, support.OTHER_ADDRESS))
        )

        assert addresses == sorted([support.PLAIN_ADDRESS, support.OTHER_ADDRESS])

    def test_a_nested_iterable_loses_nobody(self, mail, deliver, sent):
        """A nested iterable of iterables must not lose entries.

        The builder may flatten it or raise ``RecipientError``, but must
        not send to one branch and drop the rest.
        """
        nested = [[support.PLAIN_ADDRESS], (support.OTHER_ADDRESS,)]
        email = mail().to(nested)

        try:
            email.send()
        except RecipientError:
            return  # fail loud: the other acceptable answer

        deliver()
        addresses = support.envelope(support.sole(sent))

        assert addresses == sorted([support.PLAIN_ADDRESS, support.OTHER_ADDRESS]), (
            "a nested iterable was accepted but not fully resolved: "
            f"{addresses}. Flatten it or raise RecipientError -- do not drop."
        )


class TestDuplicates:
    """The same person named twice counts once.

    A group is a set of distinct people, not a bag of mentions. This can
    happen when a member and their own address both appear in one call.
    """

    def test_the_same_address_twice_is_one_recipient(self, mail, envelope):
        addresses = envelope(mail().to(support.PLAIN_ADDRESS).to(support.PLAIN_ADDRESS))

        assert addresses == [support.PLAIN_ADDRESS], (
            f"duplicate recipient in the envelope: {addresses}"
        )

    def test_a_member_and_their_own_address_are_one_recipient(
        self, mail, fr_member, envelope
    ):
        addresses = envelope(mail().to(fr_member).to(support.FR_MEMBER["email"]))

        assert addresses == [support.FR_MEMBER["email"]], (
            f"a member and their own address resolved to two recipients: {addresses}"
        )

    def test_duplicates_do_not_multiply_messages(self, mail, deliver, sent):
        email = mail().to(support.PLAIN_ADDRESS).to(support.PLAIN_ADDRESS)

        email.send()
        deliver()

        assert len(sent) == 1, f"{len(sent)} messages for one recipient"


class TestCcAndBcc:
    def test_cc_reaches_the_cc_header_and_the_envelope(self, mail, deliver, sent):
        email = mail().to(support.PLAIN_ADDRESS).cc(support.OTHER_ADDRESS)

        email.send()
        deliver()
        record = support.sole(sent)

        assert support.addresses(record.message, "Cc") == [support.OTHER_ADDRESS]
        assert support.OTHER_ADDRESS in support.envelope(record), (
            "the Cc address is in the header but not in the envelope, so nobody "
            "is actually going to receive it"
        )

    def test_cc_is_polymorphic_too(self, mail, fr_member, deliver, sent):
        """``.cc()`` shares the ``.to()`` grammar, including collections."""
        email = mail().to(support.PLAIN_ADDRESS).cc([fr_member, support.OTHER_ADDRESS])

        email.send()
        deliver()

        assert support.addresses(support.sole(sent).message, "Cc") == sorted([
            support.FR_MEMBER["email"],
            support.OTHER_ADDRESS,
        ])

    def test_bcc_reaches_the_envelope_but_no_header(self, mail, deliver, sent):
        """A blind copy must reach the envelope, without a ``Bcc`` header.

        ``Products.MailHost`` strips the header itself, so only the
        envelope half needs checking here.
        """
        email = mail().to(support.PLAIN_ADDRESS).bcc(support.OTHER_ADDRESS)

        email.send()
        deliver()
        record = support.sole(sent)

        assert support.OTHER_ADDRESS in support.envelope(record), (
            "the Bcc recipient is not in the envelope -- a blind copy that goes "
            f"nowhere: {record.recipients}"
        )
        assert record.message["Bcc"] is None, "the Bcc header leaked to recipients"
        assert support.OTHER_ADDRESS not in record.raw.decode("utf-8", "replace"), (
            "the Bcc address appears in the serialised message"
        )


class TestReplyToAndSender:
    def test_reply_to_sets_the_header(self, mail, one_message):
        message = one_message(
            mail().to(support.PLAIN_ADDRESS).reply_to(support.REPLY_TO)
        )

        assert support.addresses(message, "Reply-To") == [support.REPLY_TO]

    def test_from_defaults_to_the_site_sender(self, mail, site_sender, one_message):
        """``From`` defaults to the site's configured sender."""
        message = one_message(mail().to(support.PLAIN_ADDRESS))

        assert support.addresses(message, "From") == [site_sender]

    def test_sender_overrides_the_default(self, mail, site_sender, one_message):
        """``.sender()`` overrides the default ``From``."""
        message = one_message(
            mail().to(support.PLAIN_ADDRESS).sender(support.OVERRIDE_SENDER)
        )

        assert support.addresses(message, "From") == [support.OVERRIDE_SENDER]


class TestUnresolvable:
    """Fail loud, not a silent drop."""

    def test_collecting_an_unresolvable_recipient_does_not_raise(self, mail):
        """Resolution happens at ``.send()`` time, not when collected."""
        mail().to(support.UNRESOLVABLE)  # must not raise

    def test_send_raises_recipient_error(self, mail):
        email = mail().to(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()

    def test_nothing_is_sent_when_a_recipient_is_unresolvable(
        self, mail, deliver, sent
    ):
        """No mail must go out when any recipient is unresolvable.

        Sending the good recipients anyway risks a retry that mails them
        twice.
        """
        email = mail().to(support.PLAIN_ADDRESS).to(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()

        deliver()

        assert sent == [], f"{len(sent)} message(s) sent despite RecipientError"

    def test_the_error_names_the_offending_value(self, mail):
        """The error must name which recipient failed."""
        email = mail().to(support.UNRESOLVABLE)

        with pytest.raises(RecipientError) as exc_info:
            email.send()

        assert support.UNRESOLVABLE in str(exc_info.value)

    def test_all_the_offending_values_surface_together(self, mail):
        """All unresolvable recipients must be reported together, not one
        at a time."""
        email = mail().to([support.UNRESOLVABLE, support.OTHER_UNRESOLVABLE])

        with pytest.raises(RecipientError) as exc_info:
            email.send()

        message = str(exc_info.value)

        assert support.UNRESOLVABLE in message
        assert support.OTHER_UNRESOLVABLE in message, (
            "only the first unresolvable recipient is reported: " + message
        )

    def test_an_unadaptable_object_raises_recipient_error(self, mail):
        """An object with no adapter must raise ``RecipientError``, not a
        ``ComponentLookupError`` or ``TypeError``."""
        email = mail().to(object())

        with pytest.raises(RecipientError):
            email.send()

    def test_a_member_without_an_address_raises_recipient_error(
        self, mail, mail_portal, make_recipient_member
    ):
        """A resolvable member with no ``email`` property must raise, not
        send silently to nobody."""
        make_recipient_member(dict(support.FR_MEMBER, userid="no_address"))
        # addMember validates the address, so it is set then blanked here.
        member = mail_portal.portal_membership.getMemberById("no_address")
        member.setMemberProperties({"email": ""})
        assert member.getProperty("email") == ""

        email = mail().to("no_address")

        with pytest.raises(RecipientError):
            email.send()

    def test_no_recipients_at_all_raises_recipient_error(self, mail):
        """Sending with no recipients must raise ``RecipientError``, not
        ``Products.MailHost``'s own error."""
        email = mail()

        with pytest.raises(RecipientError):
            email.send()

    def test_an_unresolvable_cc_raises_too(self, mail):
        """``.cc()`` shares the same guarantee as ``.to()``."""
        email = mail().to(support.PLAIN_ADDRESS).cc(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()

    def test_an_unresolvable_bcc_raises_too(self, mail):
        email = mail().to(support.PLAIN_ADDRESS).bcc(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()


class TestAMemberWithTwoAddresses:
    """A member ``email`` property holding two addresses must raise.

    ``parseaddr`` turns ``"a@b.be, c@d.be"`` into an empty address, which
    would otherwise vanish from the envelope without error.
    """

    @pytest.fixture
    def two_address_member(self, mail_portal, make_member):
        member = make_member(mail_portal, email="a@commune.be, c@commune.be")
        return member

    def test_it_raises_rather_than_dropping(self, mail, two_address_member):
        email = mail().to(two_address_member)

        with pytest.raises(RecipientError):
            email.send()

    def test_the_error_names_the_member(self, mail, two_address_member):
        email = mail().to(two_address_member)

        with pytest.raises(RecipientError) as exc_info:
            email.send()

        assert two_address_member.getId() in str(exc_info.value)

    def test_the_good_recipients_are_not_sent_either(
        self, mail, two_address_member, deliver, sent
    ):
        """A partial send is worse than none: the caller retries and mails
        the good recipients twice."""
        email = mail().to(support.PLAIN_ADDRESS).to(two_address_member)

        with pytest.raises(RecipientError):
            email.send()

        deliver()

        assert sent == [], f"{len(sent)} message(s) sent despite RecipientError"

    def test_a_display_name_in_the_property_is_parsed_not_nested(
        self, mail_portal, make_member
    ):
        """A display name in the ``email`` property must be parsed out, not
        nested inside another display name."""
        from imio.emailkit.interfaces import IEmailRecipient

        member = make_member(mail_portal, fullname="", email="Zoe <zoe@commune.be>")
        recipient = IEmailRecipient(member, None)

        assert recipient is not None
        assert recipient.email == "zoe@commune.be"
        assert "<" not in recipient.email
