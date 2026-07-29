"""SPEC §6.2 -- recipient resolution and the address headers.

> ``.to() / .cc() / .bcc()`` accept, in any mix: an email string, a Plone member
> object, a userid, or an iterable of those. Resolution goes through a single
> adapter [...] Unresolvable recipients raise ``RecipientError`` at ``.send()``
> time (fail loud, not silent drop).

**The guarantee under test is not "an address arrives" -- it is "no address is
lost quietly".** Both halves matter and they fail differently: a recipient the
builder cannot resolve must stop the whole send with a named exception, and a
recipient it *can* resolve must appear in the envelope, not merely in a header
that some later step overwrites.

Which is why almost every assertion here reads the **envelope** --
``SentMail.recipients``, the ``toaddrs`` the SMTP layer was handed -- and not
only the ``To``/``Cc`` headers. ``Products.MailHost`` rewrites those headers from
its own arguments, so a builder that put an address in a header but not in the
recipient list produces a message that *looks* right and reaches nobody. That is
exactly the class of silent failure this project keeps finding.
"""

import pytest
import support


Email = support.require_builder()
RecipientError, IEmailRecipient = support.require_errors(
    "RecipientError", "IEmailRecipient"
)


@pytest.fixture(autouse=True)
def one_language_group(set_default_language):
    """Pin the site default to the test members' language.

    This module is about the *grammar* of ``.to()/.cc()/.bcc()`` -- which forms
    resolve, which fail, who ends up in the envelope. §6.2 groups by resolved
    language, and a bare address has none ("may be ``None``"), so mixing a French
    member with a plain address correctly yields **two** messages. Without this
    fixture every assertion below would quietly become a grouping assertion and
    fail for a reason that has nothing to do with what it is testing.

    Grouping itself is ``tests/test_send_language.py``, where it is the subject
    rather than the background.
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
    """§6.2 pins ``IEmailRecipient`` itself, not just its effects."""

    def test_the_interface_declares_the_three_attributes(self):
        """``email`` / ``fullname`` / ``language``, verbatim from §6.2.

        Named here because the whole polymorphism story rests on them: the
        address goes in the envelope, the fullname in the display name, and the
        language is what ``.send()`` groups by. An interface missing one of the
        three cannot support the feature the spec builds on it.
        """
        names = set(IEmailRecipient.names())

        assert {"email", "fullname", "language"} <= names, (
            f"IEmailRecipient is missing attributes from §6.2: {sorted(names)}"
        )

    def test_a_string_adapts_to_a_recipient(self, mail_portal):
        """§6.2: "Default adapters ship for ``str`` and Plone members"."""
        recipient = IEmailRecipient(support.PLAIN_ADDRESS, None)

        assert recipient is not None, (
            "no IEmailRecipient adapter for str; §6.2 requires one"
        )
        assert recipient.email.lower() == support.PLAIN_ADDRESS

    def test_a_member_adapts_to_a_recipient(self, fr_member):
        recipient = IEmailRecipient(fr_member, None)

        assert recipient is not None, (
            "no IEmailRecipient adapter for a Plone member; §6.2 requires one"
        )
        assert recipient.email.lower() == support.FR_MEMBER["email"]

    def test_a_member_recipient_carries_its_language(self, fr_member):
        """The attribute ``.send()`` groups by. A member adapter that returned
        ``None`` here would collapse every language group into the site default
        and ship French to Dutch communes -- silently, which is precisely what
        §6.2's per-language sending exists to prevent."""
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
        """A ``str`` that is not an address must resolve through the member.

        §6.2 lists "a userid" as an accepted form while shipping default
        adapters for ``str`` and members only -- so the ``str`` adapter carries
        both readings. Getting this wrong is not a crash: a userid treated as a
        literal address produces ``fr_member@`` nothing, accepted by MailHost and
        bounced by the MTA hours later.
        """
        addresses = envelope(mail().to(support.FR_MEMBER["userid"]))

        assert addresses == [support.FR_MEMBER["email"]]

    def test_a_member_contributes_its_display_name(self, mail, fr_member, one_message):
        """§6.2's adapter carries ``fullname`` -- "display name, may be empty".

        The address header is the only thing a display name can be *for*; if the
        builder never uses it the attribute is dead weight in a frozen
        interface. Asserted rather than assumed so that "we decided not to" is a
        conversation, not an omission nobody notices.
        """
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
        """§6.2: "accept, in any mix" -- one call, three different forms."""
        addresses = envelope(
            mail().to([fr_member, support.PLAIN_ADDRESS, support.FR_MEMBER["userid"]])
        )

        assert addresses == sorted([support.FR_MEMBER["email"], support.PLAIN_ADDRESS])

    def test_repeated_calls_accumulate(self, mail, fr_member, envelope):
        """§6.2's own example calls ``.to()`` twice, so the second must not
        replace the first."""
        addresses = envelope(
            mail().to(fr_member).to(support.PLAIN_ADDRESS).to(support.OTHER_ADDRESS)
        )

        assert addresses == sorted([
            support.FR_MEMBER["email"],
            support.PLAIN_ADDRESS,
            support.OTHER_ADDRESS,
        ])

    def test_a_generator_is_accepted_and_consumed_once(self, mail, envelope):
        """§6.2 says "an iterable", and ``.send()`` may render several language
        groups from the same recipient set. A generator stored unflattened is
        empty by the second group -- one message with recipients, the rest
        silently addressed to nobody."""
        addresses = envelope(
            mail().to(a for a in (support.PLAIN_ADDRESS, support.OTHER_ADDRESS))
        )

        assert addresses == sorted([support.PLAIN_ADDRESS, support.OTHER_ADDRESS])

    def test_a_nested_iterable_loses_nobody(self, mail, deliver, sent):
        """Nesting is not in §6.2's grammar -- so the rule that applies is the
        one §6.2 *does* state: never a silent drop.

        ``meeting_managers`` in the spec's own example is whatever the caller
        happens to have, and a list of groups-of-people is the obvious shape to
        pass by accident. Either the builder flattens it or it raises
        ``RecipientError``. What it must not do is send a message to the first
        branch and forget the rest, which is the failure this asserts against.
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
    """The same person named twice is still one person.

    §6.2 emits "one message per group", and a group is a set of people rather
    than a bag of mentions. The realistic way to hit this is not typing an
    address twice: it is ``.to(member)`` in one place and ``.to(SOME_ADDRESS)``
    in another, where both happen to be the same human.
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
        """§6.2 gives ``.to()``, ``.cc()`` and ``.bcc()`` the same grammar; the
        spec's own example passes a *collection* to ``.cc()``."""
        email = mail().to(support.PLAIN_ADDRESS).cc([fr_member, support.OTHER_ADDRESS])

        email.send()
        deliver()

        assert support.addresses(support.sole(sent).message, "Cc") == sorted([
            support.FR_MEMBER["email"],
            support.OTHER_ADDRESS,
        ])

    def test_bcc_reaches_the_envelope_but_no_header(self, mail, deliver, sent):
        """The whole point of a blind copy, and the one recipient class where a
        silent drop is invisible to everyone including the sender.

        ``Products.MailHost`` strips the ``Bcc`` header itself, so the header
        half of this passes for free -- the load-bearing half is the envelope.
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
        """§6.2: "``From`` defaults to the site's configured sender"."""
        message = one_message(mail().to(support.PLAIN_ADDRESS))

        assert support.addresses(message, "From") == [site_sender]

    def test_sender_overrides_the_default(self, mail, site_sender, one_message):
        """§6.2: ".sender(...) overrides"."""
        message = one_message(
            mail().to(support.PLAIN_ADDRESS).sender(support.OVERRIDE_SENDER)
        )

        assert support.addresses(message, "From") == [support.OVERRIDE_SENDER]


class TestUnresolvable:
    """§6.2: "fail loud, not silent drop"."""

    def test_collecting_an_unresolvable_recipient_does_not_raise(self, mail):
        """§6.2 puts the error at ``.send()`` time, and
        ``docs/plans/phase-2.md`` §4 says why: "resolution at ``.send()`` time so
        errors surface together". A builder that validated eagerly would report
        the first bad recipient and hide the rest."""
        mail().to(support.UNRESOLVABLE)  # must not raise

    def test_send_raises_recipient_error(self, mail):
        email = mail().to(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()

    def test_nothing_is_sent_when_a_recipient_is_unresolvable(
        self, mail, deliver, sent
    ):
        """The half that makes "fail loud" mean something.

        A builder that mailed the good recipients and raised about the bad one
        would be *worse* than one that dropped silently: the caller sees an
        exception, retries, and half the list gets the mail twice.
        """
        email = mail().to(support.PLAIN_ADDRESS).to(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()

        deliver()

        assert sent == [], f"{len(sent)} message(s) sent despite RecipientError"

    def test_the_error_names_the_offending_value(self, mail):
        """A traceback that does not say *which* recipient is useless on a list
        of two hundred."""
        email = mail().to(support.UNRESOLVABLE)

        with pytest.raises(RecipientError) as exc_info:
            email.send()

        assert support.UNRESOLVABLE in str(exc_info.value)

    def test_all_the_offending_values_surface_together(self, mail):
        """``docs/plans/phase-2.md`` §4: "resolution at ``.send()`` time so
        errors surface together". Reporting one bad recipient per run turns a
        typo-ridden list into a fix-and-rerun loop."""
        email = mail().to([support.UNRESOLVABLE, support.OTHER_UNRESOLVABLE])

        with pytest.raises(RecipientError) as exc_info:
            email.send()

        message = str(exc_info.value)

        assert support.UNRESOLVABLE in message
        assert support.OTHER_UNRESOLVABLE in message, (
            "only the first unresolvable recipient is reported: " + message
        )

    def test_an_unadaptable_object_raises_recipient_error(self, mail):
        """§6.2 routes everything through one adapter, so "no adapter" is the
        same failure as "adapter could not resolve" and must not surface as a
        ``ComponentLookupError`` or a ``TypeError`` from deep inside assembly."""
        email = mail().to(object())

        with pytest.raises(RecipientError):
            email.send()

    def test_a_member_without_an_address_raises_recipient_error(
        self, mail, mail_portal, make_recipient_member
    ):
        """The classic silent drop: a real member, resolvable, no ``email``
        property. Nothing in the send path notices, and the person simply never
        hears from the application again."""
        make_recipient_member(dict(support.FR_MEMBER, userid="no_address"))
        # Created with an address and then blanked, because ``addMember``
        # validates the address. Blank is the state a member imported from an
        # LDAP branch or a legacy site is routinely in.
        member = mail_portal.portal_membership.getMemberById("no_address")
        member.setMemberProperties({"email": ""})
        assert member.getProperty("email") == ""

        email = mail().to("no_address")

        with pytest.raises(RecipientError):
            email.send()

    def test_no_recipients_at_all_raises_recipient_error(self, mail):
        """``.send()`` with nothing to send to is the same category of mistake,
        and ``Products.MailHost`` would otherwise raise its own
        ``MailHostError('No message recipients designated')`` from three frames
        deeper, naming neither the template nor the builder."""
        email = mail()

        with pytest.raises(RecipientError):
            email.send()

    def test_an_unresolvable_cc_raises_too(self, mail):
        """``.cc()`` and ``.bcc()`` share the grammar, so they share the
        guarantee. A Cc list that quietly shrinks is how a mail stops reaching
        the department that was supposed to be watching."""
        email = mail().to(support.PLAIN_ADDRESS).cc(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()

    def test_an_unresolvable_bcc_raises_too(self, mail):
        email = mail().to(support.PLAIN_ADDRESS).bcc(support.UNRESOLVABLE)

        with pytest.raises(RecipientError):
            email.send()


class TestAMemberWithTwoAddresses:
    """§6.2: "fail loud, not silent drop" -- on the member path too.

    Regression cover for a real defect. The ``str`` adapter refused a
    multi-address value from the start; the member adapter did not, so a member
    whose ``email`` property held ``"a@b.be, c@d.be"`` produced the header
    ``Full Name <>`` (``parseaddr`` returns ``('', '')`` for it) and **vanished
    from the envelope while every other recipient in the same call was
    delivered** -- no error, no warning. The sender believed the mail went out.
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
        """Same reasoning as the unresolvable case above: a partial send is worse
        than none, because the caller retries and half the list is mailed twice."""
        email = mail().to(support.PLAIN_ADDRESS).to(two_address_member)

        with pytest.raises(RecipientError):
            email.send()

        deliver()

        assert sent == [], f"{len(sent)} message(s) sent despite RecipientError"

    def test_a_display_name_in_the_property_is_parsed_not_nested(
        self, mail_portal, make_member
    ):
        """``"Zoe <z@b.be>"`` in the property must yield the address, never end up
        nested inside another display name.

        This is the shape that made ``.sender("Greffe <greffe@commune.be>")``
        produce ``From: "Greffe <greffe"@commune.be`` -- valid syntax, wrong
        mailbox, no error. The member adapter was on the path that had not been
        fixed.
        """
        from imio.emailkit.interfaces import IEmailRecipient

        member = make_member(mail_portal, fullname="", email="Zoe <zoe@commune.be>")
        recipient = IEmailRecipient(member, None)

        assert recipient is not None
        assert recipient.email == "zoe@commune.be"
        assert "<" not in recipient.email
