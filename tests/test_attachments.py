"""``.attach(source, filename=None, mimetype=None)``.

``source`` accepts raw bytes, a filesystem path, an open binary file, a
``NamedBlobFile``/``NamedFile`` value, or a Plone File/Image object.
Missing or unguessable metadata raises ``AttachmentError`` at ``.send()``
time, not at ``.attach()`` time. Every test reads the decoded attachment's
filename, content type, and bytes, not just its presence.
"""

from pathlib import Path

import pytest
import support


Email = support.require_builder()
(AttachmentError,) = support.require_errors("AttachmentError")


#: Non-ASCII bytes. A source read as text, or re-encoded, becomes visibly
#: corrupt instead of silently passing.
PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Cafe (caf\xc3\xa9) >>\n%%EOF\n"
PDF_NAME = "convocation.pdf"

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
    b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
PNG_NAME = "logo.png"


@pytest.fixture
def pdf_on_disk(tmp_path):
    path = tmp_path / PDF_NAME
    path.write_bytes(PDF_BYTES)
    return path


@pytest.fixture
def one_attachment(mail, deliver, sent):
    """``one_attachment(email)`` -> the single attachment part of the mail."""

    def send_and_read(email):
        email.send()
        deliver()
        parts = support.attachments(support.sole(sent).message)
        assert len(parts) == 1, (
            f"expected exactly one attachment, got {len(parts)}: "
            f"{[p.get_filename() for p in parts]}"
        )
        return parts[0]

    return send_and_read


def assert_is_the_pdf(part, filename=PDF_NAME):
    """Check the filename, content type, and payload together."""
    assert part.get_filename() == filename, (
        f"attachment filename is {part.get_filename()!r}, expected {filename!r}"
    )
    assert part.get_content_type() == "application/pdf", (
        f"attachment content type is {part.get_content_type()!r}; "
        "mimetypes.guess_type('.pdf') is application/pdf"
    )
    assert part.get_payload(decode=True) == PDF_BYTES, (
        "the attachment payload is not the bytes that went in"
    )


class TestBytes:
    """Raw bytes carry no filename, so ``filename`` is required."""

    def test_bytes_with_a_filename(self, mail, one_attachment):
        part = one_attachment(
            mail().to(support.PLAIN_ADDRESS).attach(PDF_BYTES, filename=PDF_NAME)
        )

        assert_is_the_pdf(part)

    def test_bytes_without_a_filename_raise(self, mail):
        email = mail().to(support.PLAIN_ADDRESS).attach(PDF_BYTES)

        with pytest.raises(AttachmentError):
            email.send()

    def test_the_error_is_raised_at_send_not_at_attach(self, mail):
        """``.attach()`` does not raise."""
        mail().to(support.PLAIN_ADDRESS).attach(PDF_BYTES)  # must not raise

    def test_an_explicit_mimetype_wins(self, mail, one_attachment):
        """``mimetype=`` overrides guessing."""
        part = one_attachment(
            mail()
            .to(support.PLAIN_ADDRESS)
            .attach(PDF_BYTES, filename="convocation.dat", mimetype="application/pdf")
        )

        assert part.get_content_type() == "application/pdf"
        assert part.get_payload(decode=True) == PDF_BYTES

    def test_an_unguessable_mimetype_raises(self, mail):
        """Must raise, not fall back to ``application/octet-stream``."""
        email = (
            mail()
            .to(support.PLAIN_ADDRESS)
            .attach(PDF_BYTES, filename="notes.emailkitx")
        )

        with pytest.raises(AttachmentError):
            email.send()


class TestFilesystemPath:
    """The source may be a ``str`` or a ``Path``."""

    def test_a_path_object(self, mail, pdf_on_disk, one_attachment):
        part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(pdf_on_disk))

        assert_is_the_pdf(part)

    def test_a_string_path(self, mail, pdf_on_disk, one_attachment):
        """A recipient is also a ``str``; confusing the two would attach
        the path text itself."""
        part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(str(pdf_on_disk)))

        assert_is_the_pdf(part)

    def test_the_filename_can_be_overridden(self, mail, pdf_on_disk, one_attachment):
        """The inferred filename is a default, not fixed."""
        part = one_attachment(
            mail()
            .to(support.PLAIN_ADDRESS)
            .attach(pdf_on_disk, filename="Convocation du 12 aout.pdf")
        )

        assert_is_the_pdf(part, filename="Convocation du 12 aout.pdf")

    def test_a_missing_path_raises(self, mail, tmp_path):
        email = mail().to(support.PLAIN_ADDRESS).attach(tmp_path / "nope.pdf")

        with pytest.raises(AttachmentError):
            email.send()

    def test_a_directory_raises(self, mail, tmp_path):
        """A directory has no content to attach."""
        email = mail().to(support.PLAIN_ADDRESS).attach(tmp_path)

        with pytest.raises(AttachmentError):
            email.send()

    def test_a_path_with_an_unguessable_extension_raises(self, mail, tmp_path):
        path = tmp_path / "export.emailkitx"
        path.write_bytes(PDF_BYTES)
        email = mail().to(support.PLAIN_ADDRESS).attach(path)

        with pytest.raises(AttachmentError):
            email.send()


class TestFileObject:
    """The source may be an open binary file object."""

    def test_an_open_binary_file(self, mail, pdf_on_disk, one_attachment):
        with pdf_on_disk.open("rb") as handle:
            part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(handle))

        assert_is_the_pdf(part)

    def test_a_file_object_without_a_name_needs_a_filename(self, mail):
        """A ``BytesIO`` has no name to infer from."""
        import io

        email = mail().to(support.PLAIN_ADDRESS).attach(io.BytesIO(PDF_BYTES))

        with pytest.raises(AttachmentError):
            email.send()

    def test_a_nameless_file_object_with_a_filename_works(self, mail, one_attachment):
        import io

        part = one_attachment(
            mail()
            .to(support.PLAIN_ADDRESS)
            .attach(io.BytesIO(PDF_BYTES), filename=PDF_NAME)
        )

        assert_is_the_pdf(part)

    def test_a_text_mode_file_raises(self, mail, tmp_path):
        """The source must be binary; a text handle yields ``str`` and
        corrupts the file on re-encoding."""
        path = tmp_path / "notes.txt"
        path.write_text("Séance du 12 août", encoding="utf-8")

        with path.open("r", encoding="utf-8") as handle:
            email = mail().to(support.PLAIN_ADDRESS).attach(handle)

            with pytest.raises(AttachmentError):
                email.send()


class TestNamedFileValues:
    """``NamedBlobFile``/``NamedFile`` carry their own ``filename`` and
    ``contentType``, so no extra argument is needed."""

    def test_a_named_file(self, mail, one_attachment):
        from plone.namedfile.file import NamedFile

        value = NamedFile(
            data=PDF_BYTES, filename=PDF_NAME, contentType="application/pdf"
        )

        part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(value))

        assert_is_the_pdf(part)

    def test_a_named_blob_file(self, mail, one_attachment):
        from plone.namedfile.file import NamedBlobFile

        value = NamedBlobFile(
            data=PDF_BYTES, filename=PDF_NAME, contentType="application/pdf"
        )

        part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(value))

        assert_is_the_pdf(part)

    def test_the_value_carries_its_own_content_type(self, mail, one_attachment):
        """Used as is, not guessed from the extension."""
        from plone.namedfile.file import NamedBlobFile

        value = NamedBlobFile(
            data=PDF_BYTES,
            filename="convocation.bin",
            contentType="application/pdf",
        )

        part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(value))

        assert part.get_content_type() == "application/pdf"
        assert part.get_filename() == "convocation.bin"

    def test_a_value_without_a_filename_raises(self, mail):
        from plone.namedfile.file import NamedBlobFile

        value = NamedBlobFile(data=PDF_BYTES, contentType="application/pdf")

        email = mail().to(support.PLAIN_ADDRESS).attach(value)

        with pytest.raises(AttachmentError):
            email.send()


class TestContentObject:
    """A Plone File or Image object, attached directly."""

    @pytest.fixture
    def as_manager(self, mail_portal, grant_roles):
        from plone.app.testing import TEST_USER_ID

        grant_roles(mail_portal, ["Manager"])
        return TEST_USER_ID

    @pytest.fixture
    def file_object(self, mail_portal, as_manager):
        from plone import api
        from plone.namedfile.file import NamedBlobFile

        return api.content.create(
            container=mail_portal,
            type="File",
            id="convocation",
            title="Convocation",
            file=NamedBlobFile(
                data=PDF_BYTES, filename=PDF_NAME, contentType="application/pdf"
            ),
        )

    @pytest.fixture
    def image_object(self, mail_portal, as_manager):
        from plone import api
        from plone.namedfile.file import NamedBlobImage

        return api.content.create(
            container=mail_portal,
            type="Image",
            id="logo",
            title="Logo",
            image=NamedBlobImage(
                data=PNG_BYTES, filename=PNG_NAME, contentType="image/png"
            ),
        )

    def test_a_file_content_object(self, mail, file_object, one_attachment):
        part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(file_object))

        assert_is_the_pdf(part)

    def test_an_image_content_object(self, mail, image_object, one_attachment):
        part = one_attachment(mail().to(support.PLAIN_ADDRESS).attach(image_object))

        assert part.get_filename() == PNG_NAME
        assert part.get_content_type() == "image/png"
        assert part.get_payload(decode=True) == PNG_BYTES

    def test_a_content_object_with_no_file_raises(self, mail, mail_portal, as_manager):
        """A ``Document`` has no file field; only File and Image are
        supported."""
        from plone import api

        document = api.content.create(
            container=mail_portal, type="Document", id="page", title="Page"
        )

        email = mail().to(support.PLAIN_ADDRESS).attach(document)

        with pytest.raises(AttachmentError):
            email.send()

    def test_an_empty_file_field_raises(self, mail, mail_portal, as_manager):
        """Must not attach a zero-byte PDF."""
        from plone import api

        empty = api.content.create(
            container=mail_portal, type="File", id="empty", title="Empty"
        )

        email = mail().to(support.PLAIN_ADDRESS).attach(empty)

        with pytest.raises(AttachmentError):
            email.send()


class TestUnsupportedSources:
    def test_an_arbitrary_object_raises(self, mail):
        email = mail().to(support.PLAIN_ADDRESS).attach(object())

        with pytest.raises(AttachmentError):
            email.send()

    def test_a_number_raises(self, mail):
        email = mail().to(support.PLAIN_ADDRESS).attach(42)

        with pytest.raises(AttachmentError):
            email.send()

    def test_none_raises(self, mail):
        """Covers ``.attach(maybe_pdf)`` where the lookup found nothing."""
        email = mail().to(support.PLAIN_ADDRESS).attach(None)

        with pytest.raises(AttachmentError):
            email.send()

    def test_nothing_is_sent_when_an_attachment_fails(self, mail, deliver, sent):
        """A mail without the document it exists to deliver is worse than none."""
        email = (
            mail()
            .to(support.PLAIN_ADDRESS)
            .attach(PDF_BYTES, filename=PDF_NAME)
            .attach(object())
        )

        with pytest.raises(AttachmentError):
            email.send()

        deliver()

        assert sent == [], f"{len(sent)} message(s) sent despite AttachmentError"


class TestMultipleAttachments:
    def test_attach_is_callable_multiple_times(self, mail, deliver, sent):
        email = (
            mail()
            .to(support.PLAIN_ADDRESS)
            .attach(PDF_BYTES, filename=PDF_NAME)
            .attach(PNG_BYTES, filename=PNG_NAME)
        )

        email.send()
        deliver()
        parts = support.attachments(support.sole(sent).message)

        assert [p.get_filename() for p in parts] == [PDF_NAME, PNG_NAME]
        assert [p.get_content_type() for p in parts] == [
            "application/pdf",
            "image/png",
        ]

    def test_the_body_survives_alongside_attachments(self, mail, deliver, sent):
        """``add_attachment`` nests the alternative part in ``multipart/mixed``."""
        email = mail().to(support.PLAIN_ADDRESS).attach(PDF_BYTES, filename=PDF_NAME)

        email.send()
        deliver()
        message = support.sole(sent).message

        text, html = support.bodies(message)

        assert "<html" in html.lower()
        assert "<html" not in text.lower()
        support.assert_message_is_clean(message)


class TestAcrossLanguageGroups:
    """Attachments ride the same message, identical across language groups."""

    def test_every_language_group_carries_the_attachment(
        self, mail, fr_member, nl_member, deliver, sent
    ):
        email = mail().to(fr_member).to(nl_member).attach(PDF_BYTES, filename=PDF_NAME)

        email.send()
        deliver()

        assert len(sent) == 2, (
            f"FR + NL recipients produced {len(sent)} message(s), expected 2"
        )
        for record in sent:
            parts = support.attachments(record.message)
            assert [p.get_filename() for p in parts] == [PDF_NAME], (
                f"the {support.lang_of(record.message)} message lost the "
                f"attachment: {[p.get_filename() for p in parts]}"
            )
            assert parts[0].get_payload(decode=True) == PDF_BYTES

    def test_the_attachment_is_byte_identical_in_both(
        self, mail, fr_member, nl_member, deliver, sent
    ):
        """A source consumed by the first group would leave the second empty."""
        email = mail().to(fr_member).to(nl_member).attach(PDF_BYTES, filename=PDF_NAME)

        email.send()
        deliver()

        payloads = {
            support.attachments(r.message)[0].get_payload(decode=True) for r in sent
        }

        assert payloads == {PDF_BYTES}, (
            "the attachment differs between language groups (a source consumed "
            "by the first render?)"
        )


class TestFileHandlesAreReadAtSendTime:
    """No method reads a file before ``.send()`` is called."""

    def test_a_path_that_appears_between_attach_and_send_still_works(
        self, mail, tmp_path, one_attachment
    ):
        """The file does not exist yet when attached."""
        path = Path(tmp_path) / PDF_NAME
        email = mail().to(support.PLAIN_ADDRESS).attach(path)

        path.write_bytes(PDF_BYTES)

        assert_is_the_pdf(one_attachment(email))

    def test_a_path_that_disappears_before_send_raises(self, mail, tmp_path):
        """The bytes must not be cached at ``.attach()`` time."""
        path = Path(tmp_path) / PDF_NAME
        path.write_bytes(PDF_BYTES)
        email = mail().to(support.PLAIN_ADDRESS).attach(path)

        path.unlink()

        with pytest.raises(AttachmentError):
            email.send()
