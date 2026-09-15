"""The MIME shape of an assembled message.

> Message assembly: ``email.message.EmailMessage``, ``set_content(text)`` +
> ``add_alternative(html, subtype="html")``, correct headers and encoding.
> Nothing hand-built by callers, ever.

That sentence pins an *order*, not just a set of parts. In
``multipart/alternative`` the **last** part is the one a client prefers, which is
why the two calls are in that order: ``set_content(text)`` puts plaintext
first and ``add_alternative(html, ...)`` appends the HTML. Reverse them and every
modern client shows the plaintext -- a mail that is technically valid, passes any
"has both parts" assertion, and looks like the styling silently stopped working.

This also parks a Phase 0 question here: "the stock mails'
``Content-Type`` question from Phase 0 resurfaces [...] settle the MIME shape with
a real queued message as evidence". These are that evidence.
"""

import pytest
import support


Email = support.require_builder()


@pytest.fixture
def message(mail, set_default_language, deliver, sent):
    """One plain message -- one recipient, no attachments, no overrides."""
    set_default_language("fr")
    mail().to(support.PLAIN_ADDRESS).send()
    deliver()
    return support.sole(sent).message


class TestTheAlternativeStructure:
    def test_the_message_is_multipart_alternative(self, message):
        """Top level, because there are no attachments to wrap it."""
        assert message.get_content_type() == "multipart/alternative", (
            f"the message is {message.get_content_type()!r}; "
            "set_content + add_alternative produces multipart/alternative"
        )

    def test_it_has_exactly_two_parts(self, message):
        parts = support.body_parts(message)

        assert [p.get_content_type() for p in parts] == [
            "text/plain",
            "text/html",
        ], (
            "The two calls produce text/plain then text/html, in that "
            f"order: got {[p.get_content_type() for p in parts]}"
        )

    def test_the_html_part_is_last(self, message):
        """The load-bearing half of the order. Stated separately so a failure
        reads as "the client will show plaintext" rather than as a list diff."""
        parts = support.body_parts(message)

        assert parts[-1].get_content_type() == "text/html", (
            "the HTML part is not last, so mail clients will prefer the "
            "plaintext alternative and no recipient will ever see the design"
        )

    def test_neither_part_is_empty(self, message):
        text, html = support.bodies(message)

        assert text.strip()
        assert html.strip()

    def test_the_html_part_is_html_and_the_text_part_is_not(self, message):
        text, html = support.bodies(message)

        assert "<html" in html.lower()
        assert "<html" not in text.lower(), (
            "the text/plain part contains markup: a plaintext alternative that "
            "is HTML is worse than none, because clients that use it show tags"
        )

    def test_both_parts_are_substituted(self, message):
        """Phase 0's standing rule, applied to the wire format. Without the
        ``IPageTemplateEngine`` utility ``${...}`` passes through verbatim and
        raises nothing, so this is the assertion that stands between a green
        suite and raw placeholders in a citizen's inbox."""
        support.assert_message_is_clean(message)


class TestEncoding:
    def test_the_parts_declare_utf_8(self, message):
        parts = support.body_parts(message)

        for part in parts:
            assert (part.get_content_charset() or "").lower() in {
                "utf-8",
                "us-ascii",
            }, (
                f"{part.get_content_type()} declares charset "
                f"{part.get_content_charset()!r}"
            )

    def test_non_ascii_survives_the_round_trip(self, message, notification_context):
        """The fixture's title is "Séance du conseil communal du 12 août" for
        exactly this: a charset regression anywhere between ``render()`` and the
        MTA turns it into mojibake, and every structural assertion still passes."""
        _text, html = support.bodies(message)

        assert notification_context["title"] in html, (
            "the accented fixture title did not survive into the html part"
        )

    def test_non_ascii_survives_into_the_text_part(self, message, notification_context):
        text, _html = support.bodies(message)
        longest = max(
            (v for v in notification_context.values() if isinstance(v, str)), key=len
        )

        assert longest in text

    def test_every_part_declares_a_transfer_encoding(self, message):
        """A part carrying raw 8-bit bytes with no ``Content-Transfer-Encoding``
        is at the mercy of the first non-8BITMIME hop, which mangles it."""
        for part in support.body_parts(message):
            assert part["Content-Transfer-Encoding"], (
                f"{part.get_content_type()} has no Content-Transfer-Encoding"
            )


class TestHeaders:
    def test_mime_version_is_declared(self, message):
        assert message["MIME-Version"] == "1.0"

    def test_the_essential_headers_are_present(self, message, site_sender):
        for header in ("From", "To", "Subject", "Date"):
            assert message[header], f"no {header} header"

    def test_to_holds_the_recipient(self, message):
        assert support.addresses(message, "To") == [support.PLAIN_ADDRESS]

    def test_there_is_exactly_one_of_each_single_valued_header(self, message):
        """``email.message`` appends rather than replaces, so a builder that set
        a header twice emits it twice. Clients disagree about which one wins."""
        for header in ("From", "To", "Subject", "MIME-Version"):
            count = len(message.get_all(header) or [])
            assert count == 1, f"{count} {header} headers"

    def test_no_bcc_header_reaches_the_wire(self, message):
        assert message["Bcc"] is None

    def test_the_content_type_carries_a_boundary(self, message):
        """A ``multipart/*`` without a boundary parameter is unparseable, and the
        symptom is a client showing the raw MIME source."""
        assert message.get_boundary(), "multipart message with no boundary"


class TestNothingIsHandBuilt:
    """Nothing hand-built by callers, ever -- and, by the same token,
    nothing hand-built inside the builder either."""

    def test_the_body_is_render_output_verbatim(
        self, mail, set_default_language, deliver, sent, notification_context
    ):
        """The strongest statement of the seam: the parts are ``render()``'s
        output, unedited.

        A builder that post-processed the HTML -- to inline something, to rewrite
        a URL, to append a footer -- would break ``render()``'s purity guarantee
        and, with it, the golden files: the snapshots would then pin something no
        mail actually contains.
        """
        from imio.emailkit import render

        set_default_language("fr")
        mail().to(support.PLAIN_ADDRESS).send()
        deliver()

        html, text = render(
            support.qualified(support.NOTIFICATION),
            context=dict(notification_context),
            language="fr",
        )
        sent_text, sent_html = support.bodies(support.sole(sent).message)

        assert sent_html.strip() == html.strip()
        assert sent_text.strip() == text.strip()

    def test_the_message_survives_a_parse_reserialise_round_trip(self, message):
        """A message that only parses once is a message some gateway will
        rewrite into something broken."""
        from email import message_from_bytes
        from email import policy

        again = message_from_bytes(message.as_bytes(), policy=policy.default)

        assert again.get_content_type() == message.get_content_type()
        assert support.bodies(again) == support.bodies(message)
