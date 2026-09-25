"""The MIME shape of an assembled message.

``set_content(text)`` then ``add_alternative(html, ...)``: in
``multipart/alternative`` the last part is the one a client prefers, so
reversing the calls makes every client silently show the plaintext.
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
        """No attachments here to wrap it at a higher level."""
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
        """Separate, so a failure names the real symptom, not a list diff."""
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
        """Catches a raw ``${...}`` placeholder before it reaches an inbox."""
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
        """A charset regression turns this into mojibake while every
        structural check still passes."""
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
        """Without it, the first non-8BITMIME mail hop mangles the bytes."""
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
        """``email.message`` appends rather than replaces a header."""
        for header in ("From", "To", "Subject", "MIME-Version"):
            count = len(message.get_all(header) or [])
            assert count == 1, f"{count} {header} headers"

    def test_no_bcc_header_reaches_the_wire(self, message):
        assert message["Bcc"] is None

    def test_the_content_type_carries_a_boundary(self, message):
        """Without it, a client shows the raw MIME source."""
        assert message.get_boundary(), "multipart message with no boundary"


class TestNothingIsHandBuilt:
    """Neither callers nor the builder itself may hand-build message parts."""

    def test_the_body_is_render_output_verbatim(
        self, mail, set_default_language, deliver, sent, notification_context
    ):
        """A builder that post-processed the HTML would break the golden
        files too."""
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
        """A mail gateway can rewrite a message that only parses once."""
        from email import message_from_bytes
        from email import policy

        again = message_from_bytes(message.as_bytes(), policy=policy.default)

        assert again.get_content_type() == message.get_content_type()
        assert support.bodies(again) == support.bodies(message)
